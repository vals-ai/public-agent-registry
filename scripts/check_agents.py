#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

import yaml

ROOT = Path(__file__).resolve().parent.parent

GITHUB = "https://github.com"
HEX40 = re.compile(r"[0-9a-f]{40}")
TAG_FORBIDDEN = re.compile(r"[\s*?\[\]\\]")
CHECKSUM_LINE = re.compile(r"([0-9a-fA-F]{64})\s+\*?(.+)")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
GITHUB_URL = re.compile(re.escape(GITHUB) + "/" + REPO.pattern)
FORBIDDEN_CONTRACT_FIELDS = ("secrets", "ingest_lambda")
GIT_TIMEOUT = 60


def checksum_entry(line: str) -> tuple[str, str] | None:
    match = CHECKSUM_LINE.fullmatch(line.strip())
    if not match:
        return None
    return match.group(1).lower(), match.group(2).strip().removeprefix("./")


def _is_str(value: object) -> bool:
    return isinstance(value, str) and value != ""


def _is_relative_path(value: object) -> bool:
    if not _is_str(value):
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts


def check_contract(agent_dir: Path) -> list[str]:
    name = agent_dir.name
    path = agent_dir / "contract.yaml"
    if not path.is_file():
        return [f"{name}: contract.yaml is missing"]
    try:
        contract = yaml.safe_load(path.read_text())
    except yaml.YAMLError as error:
        return [f"{name}: contract.yaml is not valid YAML: {' '.join(str(error).split())}"]
    if not isinstance(contract, dict):
        return [f"{name}: contract.yaml must be a mapping"]

    problems = []
    if "name" not in contract:
        problems.append(f"{name}: contract has no name")
    elif contract["name"] != name:
        problems.append(f"{name}: contract name '{contract['name']}' does not match folder")
    for field in FORBIDDEN_CONTRACT_FIELDS:
        if field in contract:
            problems.append(f"{name}: contract must not set {field}")
    return problems


def load_upstream(agent_dir: Path) -> tuple[dict | None, list[str]]:
    name = agent_dir.name
    path = agent_dir / "upstream.json"
    if not path.is_file():
        return None, [f"{name}: upstream.json is missing"]
    try:
        upstream = json.loads(path.read_text())
    except json.JSONDecodeError as error:
        return None, [f"{name}: upstream.json is not valid JSON: {error}"]
    if not isinstance(upstream, dict):
        return None, [f"{name}: upstream.json must be a JSON object"]

    prefix = f"{name}: upstream.json"
    problems = []
    repo = upstream.get("repo")
    if not (isinstance(repo, str) and REPO.fullmatch(repo)):
        problems.append(f"{prefix} 'repo' must be 'owner/name'")
    tag = upstream.get("tag")
    if not (_is_str(tag) and not TAG_FORBIDDEN.search(tag)):
        problems.append(f"{prefix} 'tag' must be a non-empty string without spaces or wildcards")
    commit = upstream.get("commit")
    if not (isinstance(commit, str) and HEX40.fullmatch(commit)):
        problems.append(f"{prefix} 'commit' must be a 40-character lowercase hex SHA")
    if not _is_relative_path(upstream.get("submodule")):
        problems.append(f"{prefix} 'submodule' must be a relative path inside the agent folder")
    if "track" in upstream and not isinstance(upstream["track"], str):
        problems.append(f"{prefix} 'track' must be a string")
    if "assets" in upstream:
        assets = upstream["assets"]
        if not (isinstance(assets, list) and all(_is_str(asset) for asset in assets)):
            problems.append(f"{prefix} 'assets' must be a list of file names")
    return (None, problems) if problems else (upstream, [])


def check_checksums(agent_dir: Path, assets: list[str]) -> list[str]:
    name = agent_dir.name
    if not assets:
        return []
    path = agent_dir / "checksums.txt"
    if not path.is_file():
        return [f"{name}: checksums.txt is missing"]
    present = {entry[1] for line in path.read_text().splitlines() if (entry := checksum_entry(line))}
    return [f"{name}: checksums.txt has no sha256 for {asset}" for asset in assets if asset not in present]


def check_agent(
    agent_dir: Path,
    *,
    gitlink: str | None,
    submodule_url: str | None,
    tag_commit: str | None,
) -> list[str]:
    name = agent_dir.name
    problems = check_contract(agent_dir)
    upstream, upstream_problems = load_upstream(agent_dir)
    problems += upstream_problems
    if upstream is None:
        return problems

    submodule = PurePosixPath(upstream["submodule"]).as_posix()
    if gitlink is None:
        problems.append(f"{name}: submodule {submodule} is missing")
    else:
        if gitlink != upstream["commit"]:
            problems.append(
                f"{name}: submodule {submodule} is at {gitlink[:12]}, "
                f"upstream.json says {upstream['commit'][:12]}"
            )
        expected = f"{GITHUB}/{upstream['repo']}"
        if submodule_url is None:
            problems.append(f"{name}: submodule {submodule} has no URL in .gitmodules")
        elif submodule_url not in (f"{expected}.git", expected):
            problems.append(f"{name}: submodule URL {submodule_url} is not {expected}.git")

    if tag_commit is not None and tag_commit != upstream["commit"]:
        problems.append(
            f"{name}: tag {upstream['tag']} points at {tag_commit[:12]}, not {upstream['commit'][:12]}"
        )

    problems += check_checksums(agent_dir, upstream.get("assets", []))
    return problems


def _git(*args: str, cwd: Path, allow_exit_1: bool = False) -> str | None:
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
    if result.returncode == 1 and allow_exit_1:
        return None
    if result.returncode != 0:
        raise RuntimeError(" ".join(result.stderr.split()) or f"git {args[0]} exited {result.returncode}")
    return result.stdout


def read_gitlinks(root: Path) -> dict[str, str | None]:
    out = _git("ls-files", "--stage", "-z", cwd=root)
    gitlinks: dict[str, str | None] = {}
    for entry in out.split("\0"):
        meta, _, path = entry.partition("\t")
        if path and meta.split()[0] == "160000":
            _, sha, stage = meta.split()
            gitlinks[path] = sha if stage == "0" else None
    return gitlinks


def read_gitmodules(root: Path) -> dict[str, dict[str, str]]:
    out = _git("config", "-f", ".gitmodules", "-z", "--get-regexp", r"^submodule\.", cwd=root, allow_exit_1=True)
    modules: dict[str, dict[str, str]] = {}
    for entry in (out or "").split("\0"):
        key, _, value = entry.partition("\n")
        name, dot, field = key.removeprefix("submodule.").rpartition(".")
        if dot:
            modules.setdefault(name, {})[field] = value
    return modules


def check_repo(
    gitlinks: Iterable[str],
    modules: dict[str, dict[str, str]],
    agent_submodules: set[str],
    broken_agents: set[str] = frozenset(),
) -> list[str]:
    problems = [
        f"{path}: submodule does not belong to an agent "
        "(each submodule must be agents/<agent>/<submodule> from that agent's upstream.json)"
        for path in gitlinks
        if path not in agent_submodules and not any(path.startswith(f"{folder}/") for folder in broken_agents)
    ]
    owners: dict[str, str] = {}
    for name, fields in modules.items():
        path = fields.get("path")
        if path is not None:
            if path in owners:
                problems.append(f".gitmodules: submodules {owners[path]} and {name} both use path {path}")
            else:
                owners[path] = name
        url = fields.get("url")
        if url is None or (path in agent_submodules and name == path):
            continue
        if not GITHUB_URL.fullmatch(url):
            problems.append(f".gitmodules: submodule {name} URL {url} is not https://github.com/<owner>/<repo>")
    return problems


def parse_tag_commit(ls_remote_output: str, tag: str) -> str | None:
    refs = {}
    for line in ls_remote_output.splitlines():
        sha, _, ref = line.partition("\t")
        refs[ref.strip()] = sha.strip()
    return refs.get(f"refs/tags/{tag}^{{}}") or refs.get(f"refs/tags/{tag}")


def fetch_tag_commit(repo: str, tag: str) -> str | None:
    out = _git("ls-remote", f"{GITHUB}/{repo}.git", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}", cwd=ROOT)
    return parse_tag_commit(out, tag)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check every agent folder under agents/.")
    parser.add_argument("--offline", action="store_true", help="skip resolving upstream tags over the network")
    args = parser.parse_args(argv)

    gitlinks: dict[str, str | None] = {}
    modules: dict[str, dict[str, str]] = {}
    list_error = None
    try:
        gitlinks = read_gitlinks(ROOT)
        modules = read_gitmodules(ROOT)
    except RuntimeError as error:
        list_error = error

    problems = []
    agent_submodules: set[str] = set()
    broken_agents: set[str] = set()
    for contract in sorted((ROOT / "agents").glob("*/contract.yaml")):
        agent_dir = contract.parent
        name = agent_dir.name
        upstream, _ = load_upstream(agent_dir)

        gitlink = submodule_url = tag_commit = None
        lookup_problems = []
        if upstream is not None:
            repo, tag = upstream["repo"], upstream["tag"]
            path = f"agents/{name}/{PurePosixPath(upstream['submodule']).as_posix()}"
            agent_submodules.add(path)
            gitlink = gitlinks.get(path)
            submodule_url = modules.get(path, {}).get("url")
            if list_error is not None:
                lookup_problems.append(f"{name}: could not read submodule {path} from git: {list_error}")
            if not args.offline:
                try:
                    tag_commit = fetch_tag_commit(repo, tag)
                except RuntimeError as error:
                    lookup_problems.append(f"{name}: could not look up tag {tag} in {repo}: {error}")
                else:
                    if tag_commit is None:
                        lookup_problems.append(f"{name}: tag {tag} not found in {repo}")
        else:
            broken_agents.add(f"agents/{name}")

        problems += check_agent(agent_dir, gitlink=gitlink, submodule_url=submodule_url, tag_commit=tag_commit)
        problems += lookup_problems

    if list_error is not None:
        problems.append(f"could not list the submodules from git: {list_error}")
    else:
        problems += check_repo(gitlinks, modules, agent_submodules, broken_agents)

    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
