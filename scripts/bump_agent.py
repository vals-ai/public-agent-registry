#!/usr/bin/env python3
"""Pick or set the pinned upstream release of an agent under agents/.

Each agents/<name>/ wraps an unmodified upstream repo, pinned as a git submodule, and records
the pin in upstream.json (``repo``, ``tag``, ``commit``, ``submodule``, and optionally ``track``
and ``assets``). This script moves that pin:

* without --pin it picks the newest GitHub release that is at least seven days old and on the
  tracked line (the tag starts with ``track`` if set, else it has the same major version as the
  current tag). Drafts and prereleases never count,
* with --pin TAG it pins that tag, whatever its age. This is how the first pin is set right after
  ``git submodule add``, when upstream.json still has an empty ``tag`` and ``commit``.

Pinning checks the tag out in the submodule, rewrites upstream.json, and, when ``assets`` is set,
rewrites checksums.txt with the release's sha256 for each asset. It stages nothing: the caller
runs ``git add`` and commits.

Usage: python scripts/bump_agent.py AGENT_DIR [--pin TAG] [--dry-run]
Prints one JSON line: {"agent", "from", "to", "newer_major"}. ``to`` is the tag picked (or given
with --pin) and ``newer_major`` the newest old-enough release on a higher major version, both
null when there is none. --pin does not look up releases, so its ``newer_major`` is null.
Exits 1 with a message on stderr when something goes wrong.

Set GITHUB_TOKEN to authenticate the GitHub API calls (higher rate limits).
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

GITHUB = "https://github.com"
API = "https://api.github.com"
PER_PAGE = 100
HTTP_TIMEOUT = 60
GIT_TIMEOUT = 300
MIN_AGE = timedelta(days=7)
USER_AGENT = "public-agent-registry-bump-agent"

VERSION = re.compile(r"\d+(\.\d+)*", re.ASCII)
HEX40 = re.compile(r"[0-9a-f]{40}")
TAG_FORBIDDEN = re.compile(r"[\s*?\[\]\\]")
CHECKSUM_LINE = re.compile(r"([0-9a-fA-F]{64})\s+\*?(.+)")
SUMS_FILES = ("SHA256SUMS", "sha256sum.txt")


@dataclass(frozen=True)
class Release:
    tag: str
    published_at: datetime


def parse_version(tag: str) -> tuple[int, ...] | None:
    """``v1.19.5`` -> ``(1, 19, 5)``. None unless the tag is an optional ``v`` and a dotted number."""
    number = tag.removeprefix("v")
    if not VERSION.fullmatch(number):
        return None
    return tuple(int(part) for part in number.split("."))


def _current_version(current_tag: str) -> tuple[int, ...]:
    version = parse_version(current_tag)
    if version is None:
        raise ValueError(
            f"current tag {current_tag!r} is not a plain version like v1.2.3, "
            "so newer releases cannot be compared with it; set the pin by hand with --pin"
        )
    return version


def _old_enough(releases: list[Release], now: datetime, min_age: timedelta) -> list[tuple[tuple[int, ...], Release]]:
    """(version, release) for every release with a plain version tag that is at least ``min_age`` old."""
    found = []
    for release in releases:
        version = parse_version(release.tag)
        if version is not None and now - release.published_at >= min_age:
            found.append((version, release))
    return found


def pick_release(
    releases: list[Release],
    current_tag: str,
    *,
    track: str | None,
    now: datetime,
    min_age: timedelta = MIN_AGE,
) -> Release | None:
    """The highest-version release newer than ``current_tag`` and old enough, on the tracked line.

    The line is the tags starting with ``track`` when it is set, else the current tag's major version.
    """
    current = _current_version(current_tag)
    candidates = [
        (version, release)
        for version, release in _old_enough(releases, now, min_age)
        if version > current and (release.tag.startswith(track) if track else version[0] == current[0])
    ]
    return max(candidates, key=lambda pair: pair[0])[1] if candidates else None


def newer_major(
    releases: list[Release],
    current_tag: str,
    *,
    now: datetime,
    min_age: timedelta = MIN_AGE,
) -> Release | None:
    """The highest-version old-enough release whose major version is above ``current_tag``'s."""
    current = _current_version(current_tag)
    candidates = [(version, release) for version, release in _old_enough(releases, now, min_age) if version[0] > current[0]]
    return max(candidates, key=lambda pair: pair[0])[1] if candidates else None


def fetch_releases(repo: str) -> list[Release]:
    """Every published, non-prerelease GitHub release of ``repo`` (owner/name), newest first."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    releases = []
    page = 1
    while True:
        request = urllib.request.Request(f"{API}/repos/{repo}/releases?per_page={PER_PAGE}&page={page}", headers=headers)
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            batch = json.load(response)
        for item in batch:
            if item.get("draft") or item.get("prerelease") or not item.get("published_at"):
                continue
            releases.append(Release(item["tag_name"], datetime.fromisoformat(item["published_at"])))
        if len(batch) < PER_PAGE:
            return releases
        page += 1


def download_bytes(url: str) -> bytes:
    """GET ``url`` (following redirects). Raises ``urllib.error.HTTPError`` on a bad status."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        return response.read()


def run_git(*args: str, cwd: Path) -> str:
    """Run git in ``cwd`` (a submodule checkout) and return stdout."""
    if not (cwd / ".git").exists():
        raise RuntimeError(f"{cwd} is not a git checkout; run 'git submodule update --init' first")
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"git {args[0]} timed out after {GIT_TIMEOUT}s") from error
    if result.returncode != 0:
        raise RuntimeError(" ".join(result.stderr.split()) or f"git {args[0]} exited {result.returncode}")
    return result.stdout


def _checksum_entry(line: str) -> tuple[str, str] | None:
    """(lowercase sha256, file name) of a ``sha256sum`` line (``*`` and ``./`` tolerated), else None."""
    match = CHECKSUM_LINE.fullmatch(line.strip())
    if not match:
        return None
    return match.group(1).lower(), match.group(2).strip().removeprefix("./")


def refresh_checksums(agent_dir: Path, upstream: dict, *, download: Callable[[str], bytes]) -> None:
    """Rewrite checksums.txt with the release's sha256 for each of ``upstream["assets"]``.

    The digests come from the release's SHA256SUMS, then sha256sum.txt, and any asset neither
    file lists is downloaded and hashed. Lines for other files (jq) stay first, in their order,
    then come the assets, in ``assets`` order. Nothing is written if a download fails.
    """
    assets = upstream.get("assets") or []
    if not assets:
        return
    base = f"{GITHUB}/{upstream['repo']}/releases/download/{upstream['tag']}"

    digests: dict[str, str] = {}
    for sums_name in SUMS_FILES:
        if all(asset in digests for asset in assets):
            break
        try:
            text = download(f"{base}/{sums_name}").decode()
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            continue
        for line in text.splitlines():
            entry = _checksum_entry(line)
            if entry and entry[1] in assets:
                digests.setdefault(entry[1], entry[0])
    for asset in assets:
        if asset not in digests:
            digests[asset] = hashlib.sha256(download(f"{base}/{asset}")).hexdigest()

    path = agent_dir / "checksums.txt"
    kept = []
    if path.is_file():
        for line in path.read_text().splitlines():
            entry = _checksum_entry(line)
            if line.strip() and not (entry and entry[1] in assets):
                kept.append(line.rstrip())
    lines = kept + [f"{digests[asset]}  {asset}" for asset in assets]
    path.write_text("\n".join(lines) + "\n")


def pin(agent_dir: Path, tag: str, *, git: Callable[..., str], download: Callable[[str], bytes]) -> dict:
    """Check ``tag`` out in the agent's submodule and record it in upstream.json (and checksums.txt).

    ``git(*args, cwd=...)`` runs git and returns stdout. Returns the new upstream dict. Nothing is
    staged or committed, and upstream.json is left alone if the checkout or checksums fail.
    """
    if not tag or tag.startswith("-") or TAG_FORBIDDEN.search(tag):
        raise ValueError(f"{tag!r} is not a usable tag name")
    path = agent_dir / "upstream.json"
    upstream = json.loads(path.read_text())
    submodule = agent_dir / upstream["submodule"]

    git("fetch", "--depth", "1", "origin", "tag", tag, cwd=submodule)
    git("checkout", "--detach", tag, cwd=submodule)
    commit = git("rev-parse", "HEAD", cwd=submodule).strip()
    if not HEX40.fullmatch(commit):
        raise RuntimeError(f"git rev-parse HEAD did not return a commit SHA: {commit!r}")

    upstream = {**upstream, "tag": tag, "commit": commit}
    if upstream.get("assets"):
        refresh_checksums(agent_dir, upstream, download=download)
    path.write_text(json.dumps(upstream, indent=2) + "\n")
    return upstream


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pick or set the pinned upstream release of an agent.")
    parser.add_argument("agent_dir", type=Path, metavar="AGENT_DIR", help="an agents/<name> folder")
    parser.add_argument("--pin", metavar="TAG", help="pin this tag instead of picking the newest eligible release")
    parser.add_argument("--dry-run", action="store_true", help="report the pick without changing anything")
    args = parser.parse_args(argv)

    agent_dir: Path = args.agent_dir
    try:
        upstream = json.loads((agent_dir / "upstream.json").read_text())
        current = upstream.get("tag", "")
        target = args.pin
        newer = None
        if target is None:
            releases = fetch_releases(upstream["repo"])
            now = datetime.now(UTC)
            track = upstream.get("track") or None
            picked = pick_release(releases, current, track=track, now=now)
            target = picked.tag if picked else None
            major = newer_major(releases, current, now=now)
            newer = major.tag if major else None
        if target is not None and not args.dry_run:
            pin(agent_dir, target, git=run_git, download=download_bytes)
    except (RuntimeError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(json.dumps({"agent": agent_dir.resolve().name, "from": current, "to": target, "newer_major": newer}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
