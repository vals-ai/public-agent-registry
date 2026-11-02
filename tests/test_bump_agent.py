import hashlib
import importlib.util
import io
import json
import subprocess
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "bump_agent.py"
_spec = importlib.util.spec_from_file_location("bump_agent", SCRIPT)
bump_agent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bump_agent)
Release = bump_agent.Release
parse_version = bump_agent.parse_version
pick_release = bump_agent.pick_release
newer_major = bump_agent.newer_major
fetch_releases = bump_agent.fetch_releases
refresh_checksums = bump_agent.refresh_checksums
pin = bump_agent.pin
main = bump_agent.main
run_git = bump_agent.run_git

NOW = datetime(2026, 11, 1, tzinfo=UTC)


def rel(tag, day, month=10):
    return Release(tag, datetime(2026, month, day, tzinfo=UTC))


def not_found(url):
    return urllib.error.HTTPError(url, 404, "Not Found", {}, None)


# ---- parse_version -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v1.19.5", (1, 19, 5)),
        ("1.4.0", (1, 4, 0)),
        ("v0.25.0", (0, 25, 0)),
        ("v7", (7,)),
        ("process-daemon-v0.4.0", None),
        ("jq-1.8.2", None),
        ("v1.2.3-rc1", None),
        ("vv1.2.3", None),
        ("v", None),
        ("", None),
        ("v1..2", None),
        ("v1.2.", None),
    ],
)
def test_parse_version(tag, expected):
    assert parse_version(tag) == expected


# ---- pick_release / newer_major --------------------------------------------------------------


def test_pick_release_takes_newest_old_enough():
    releases = [rel("v1.19.5", 28), rel("v1.19.4", 22), rel("v1.19.3", 16)]
    assert pick_release(releases, "v1.19.3", track=None, now=NOW).tag == "v1.19.4"


def test_pick_release_compares_versions_numerically():
    releases = [rel("v1.19.9", 10), rel("v1.19.10", 11), rel("v1.19.2", 12)]
    assert pick_release(releases, "v1.19.1", track=None, now=NOW).tag == "v1.19.10"


def test_pick_release_ignores_listing_order():
    releases = [rel("v1.19.4", 22), rel("v1.19.6", 20), rel("v1.19.5", 21)]
    assert pick_release(releases, "v1.19.3", track=None, now=NOW).tag == "v1.19.6"


def test_pick_release_min_age_is_inclusive():
    exactly_seven_days = Release("v1.0.1", NOW - timedelta(days=7))
    just_under = Release("v1.0.2", NOW - timedelta(days=7) + timedelta(seconds=1))
    assert pick_release([exactly_seven_days, just_under], "v1.0.0", track=None, now=NOW).tag == "v1.0.1"
    assert pick_release([just_under], "v1.0.0", track=None, now=NOW) is None


def test_pick_release_respects_custom_min_age():
    releases = [rel("v1.0.1", 30)]
    assert pick_release(releases, "v1.0.0", track=None, now=NOW) is None
    assert pick_release(releases, "v1.0.0", track=None, now=NOW, min_age=timedelta(days=1)).tag == "v1.0.1"


def test_pick_release_stays_on_major_and_reports_newer_major():
    releases = [rel("v2.2.5", 1), rel("v1.19.4", 22)]
    assert pick_release(releases, "v1.19.4", track=None, now=NOW) is None
    assert newer_major(releases, "v1.19.4", now=NOW).tag == "v2.2.5"


def test_pick_release_honors_track():
    releases = [rel("v2.0.0", 1), rel("v1.20.0", 2)]
    assert pick_release(releases, "v1.19.4", track="v1.", now=NOW).tag == "v1.20.0"


def test_pick_release_track_replaces_the_major_rule():
    releases = [rel("v2.0.0", 1), rel("v2.1.0", 2)]
    assert pick_release(releases, "v1.19.4", track="v2.", now=NOW).tag == "v2.1.0"


def test_pick_release_skips_unparseable_tags():
    releases = [rel("v1.20.0-rc1", 1), rel("process-daemon-v1.20.0", 1), rel("v1.19.5", 2)]
    assert pick_release(releases, "v1.19.4", track=None, now=NOW).tag == "v1.19.5"


def test_pick_release_none_when_up_to_date():
    assert pick_release([rel("v2.4.6", 1, 7)], "v2.4.6", track=None, now=NOW) is None


def test_pick_release_never_goes_backwards():
    assert pick_release([rel("v1.0.0", 1, 6)], "v1.1.0", track=None, now=NOW) is None


def test_pick_release_rejects_unparseable_current_tag():
    with pytest.raises(ValueError, match="current-tag"):
        pick_release([rel("v1.0.0", 1)], "current-tag", track=None, now=NOW)
    with pytest.raises(ValueError):
        pick_release([rel("v1.0.0", 1)], "", track=None, now=NOW)


def test_newer_major_takes_highest_old_enough_and_ignores_same_major():
    releases = [rel("v3.0.0", 30), rel("v2.2.5", 1), rel("v2.10.0", 2), rel("v1.20.0", 3)]
    assert newer_major(releases, "v1.19.4", now=NOW).tag == "v2.10.0"


def test_newer_major_none_when_nothing_newer():
    assert newer_major([rel("v1.20.0", 1)], "v1.19.4", now=NOW) is None


def test_newer_major_rejects_unparseable_current_tag():
    with pytest.raises(ValueError):
        newer_major([rel("v2.0.0", 1)], "", now=NOW)


# ---- fetch_releases ---------------------------------------------------------------------------


class FakeResponse(io.BytesIO):
    pass


def fake_urlopen(pages, requests):
    def urlopen(request, timeout=None):
        requests.append(request)
        page = int(parse_qs(urlsplit(request.full_url).query)["page"][0])
        return FakeResponse(json.dumps(pages[page - 1] if page <= len(pages) else []).encode())

    return urlopen


def api_release(tag, published_at="2026-10-01T12:00:00Z", *, draft=False, prerelease=False):
    return {"tag_name": tag, "published_at": published_at, "draft": draft, "prerelease": prerelease}


def test_fetch_releases_paginates_and_skips_drafts_and_prereleases(monkeypatch):
    monkeypatch.setattr(bump_agent, "PER_PAGE", 2)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    pages = [
        [api_release("v2.0.0"), api_release("v2.1.0-beta.1", prerelease=True)],
        [api_release("v1.0.0", "2026-09-15T08:30:00Z"), api_release("v1.1.0", None, draft=True)],
        [api_release("v0.9.0")],
    ]
    requests = []
    monkeypatch.setattr(bump_agent.urllib.request, "urlopen", fake_urlopen(pages, requests))

    assert fetch_releases("o/r") == [
        Release("v2.0.0", datetime(2026, 10, 1, 12, 0, tzinfo=UTC)),
        Release("v1.0.0", datetime(2026, 9, 15, 8, 30, tzinfo=UTC)),
        Release("v0.9.0", datetime(2026, 10, 1, 12, 0, tzinfo=UTC)),
    ]
    assert [r.full_url for r in requests] == [
        f"https://api.github.com/repos/o/r/releases?per_page=2&page={n}" for n in (1, 2, 3)
    ]


def test_fetch_releases_sends_token_only_when_set(monkeypatch):
    requests = []
    monkeypatch.setattr(bump_agent.urllib.request, "urlopen", fake_urlopen([[]], requests))

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert fetch_releases("o/r") == []
    assert requests[-1].get_header("Authorization") is None

    monkeypatch.setenv("GITHUB_TOKEN", "t0k3n")
    assert fetch_releases("o/r") == []
    assert requests[-1].get_header("Authorization") == "Bearer t0k3n"


# ---- refresh_checksums ------------------------------------------------------------------------


def test_refresh_checksums_prefers_sha256sums(tmp_path):
    (tmp_path / "checksums.txt").write_text(f"{'1'*64}  jq-linux-amd64\n{'0'*64}  pi-linux-x64.tar.gz\n")
    sums = f"{'2'*64}  pi-linux-x64.tar.gz\n{'3'*64}  pi-linux-arm64.tar.gz\n{'4'*64}  pi-darwin-arm64.tar.gz\n"
    upstream = {"repo": "earendil-works/pi", "tag": "v1.4.0", "assets": ["pi-linux-x64.tar.gz", "pi-linux-arm64.tar.gz"]}
    refresh_checksums(tmp_path, upstream, download=lambda url: sums.encode() if url.endswith("/SHA256SUMS") else pytest.fail(url))
    assert (tmp_path / "checksums.txt").read_text() == (
        f"{'1'*64}  jq-linux-amd64\n{'2'*64}  pi-linux-x64.tar.gz\n{'3'*64}  pi-linux-arm64.tar.gz\n"
    )


def test_refresh_checksums_hashes_assets_without_sums_file(tmp_path):
    requested = []

    def download(url):
        requested.append(url)
        if url.endswith("/SHA256SUMS") or url.endswith("/sha256sum.txt"):
            raise not_found(url)
        return b"abc"

    upstream = {"repo": "anomalyco/opencode", "tag": "v1.19.4", "assets": ["opencode-linux-x64.tar.gz"]}
    refresh_checksums(tmp_path, upstream, download=download)
    assert (tmp_path / "checksums.txt").read_text() == f"{hashlib.sha256(b'abc').hexdigest()}  opencode-linux-x64.tar.gz\n"
    base = "https://github.com/anomalyco/opencode/releases/download/v1.19.4"
    assert requested == [f"{base}/SHA256SUMS", f"{base}/sha256sum.txt", f"{base}/opencode-linux-x64.tar.gz"]


def test_refresh_checksums_falls_back_to_sha256sum_txt(tmp_path):
    sums = f"{'a'*64} *asset-one.zip\n{'b'*64}  ./asset-two.zip\n"

    def download(url):
        if url.endswith("/SHA256SUMS"):
            raise not_found(url)
        if url.endswith("/sha256sum.txt"):
            return sums.encode()
        pytest.fail(url)

    refresh_checksums(tmp_path, {"repo": "o/r", "tag": "v1", "assets": ["asset-two.zip", "asset-one.zip"]}, download=download)
    assert (tmp_path / "checksums.txt").read_text() == f"{'b'*64}  asset-two.zip\n{'a'*64}  asset-one.zip\n"


def test_refresh_checksums_hashes_assets_a_sums_file_leaves_out(tmp_path):
    def download(url):
        if url.endswith("/SHA256SUMS"):
            return f"{'a'*64}  listed.zip\n".encode()
        if url.endswith("/sha256sum.txt"):
            raise not_found(url)
        assert url.endswith("/unlisted.zip")
        return b"abc"

    refresh_checksums(tmp_path, {"repo": "o/r", "tag": "v1", "assets": ["listed.zip", "unlisted.zip"]}, download=download)
    assert (tmp_path / "checksums.txt").read_text() == (
        f"{'a'*64}  listed.zip\n{hashlib.sha256(b'abc').hexdigest()}  unlisted.zip\n"
    )


def test_refresh_checksums_missing_asset_raises_and_keeps_existing_file(tmp_path):
    original = f"{'1'*64}  jq-linux-amd64\n"
    (tmp_path / "checksums.txt").write_text(original)

    def download(url):
        raise not_found(url)

    with pytest.raises(urllib.error.HTTPError):
        refresh_checksums(tmp_path, {"repo": "o/r", "tag": "v1", "assets": ["gone.zip"]}, download=download)
    assert (tmp_path / "checksums.txt").read_text() == original


def test_refresh_checksums_other_http_errors_are_not_swallowed(tmp_path):
    def download(url):
        raise urllib.error.HTTPError(url, 500, "Server Error", {}, None)

    with pytest.raises(urllib.error.HTTPError):
        refresh_checksums(tmp_path, {"repo": "o/r", "tag": "v1", "assets": ["a.zip"]}, download=download)


def test_refresh_checksums_keeps_foreign_lines_first_in_order(tmp_path):
    (tmp_path / "checksums.txt").write_text(
        f"{'1'*64}  jq-linux-amd64\n"
        f"{'0'*64}  old-asset.tar.gz\n"
        f"{'2'*64} *jq-linux-arm64\n"
        f"{'0'*64}  other-asset.tar.gz\n"
    )
    sums = f"{'3'*64}  other-asset.tar.gz\n{'4'*64}  old-asset.tar.gz\n"
    upstream = {"repo": "o/r", "tag": "v1", "assets": ["old-asset.tar.gz", "other-asset.tar.gz"]}
    refresh_checksums(tmp_path, upstream, download=lambda url: sums.encode())
    assert (tmp_path / "checksums.txt").read_text() == (
        f"{'1'*64}  jq-linux-amd64\n"
        f"{'2'*64} *jq-linux-arm64\n"
        f"{'4'*64}  old-asset.tar.gz\n"
        f"{'3'*64}  other-asset.tar.gz\n"
    )


# ---- pin --------------------------------------------------------------------------------------


def make_upstream(agent_dir, **extra):
    upstream = {"repo": "o/r", "tag": "v1.0.0", "commit": "a" * 40, "submodule": "r", "track": "v1.", **extra}
    (agent_dir / "upstream.json").write_text(json.dumps(upstream, indent=2) + "\n")
    return upstream


class FakeGit:
    def __init__(self, head="f" * 40):
        self.head = head
        self.calls = []

    def __call__(self, *args, cwd):
        self.calls.append((args, cwd))
        return f"{self.head}\n" if args == ("rev-parse", "HEAD") else ""


def test_pin_rewrites_upstream_json(tmp_path):
    make_upstream(tmp_path)
    git = FakeGit()
    result = pin(tmp_path, "v1.1.0", git=git, download=pytest.fail)
    assert json.loads((tmp_path / "upstream.json").read_text()) == {
        "repo": "o/r", "tag": "v1.1.0", "commit": "f" * 40, "submodule": "r", "track": "v1."
    }
    assert result == {"repo": "o/r", "tag": "v1.1.0", "commit": "f" * 40, "submodule": "r", "track": "v1."}
    # exactly these git commands, in the submodule, and nothing that stages or commits
    assert git.calls == [
        (("fetch", "--depth", "1", "origin", "tag", "v1.1.0"), tmp_path / "r"),
        (("checkout", "--detach", "v1.1.0"), tmp_path / "r"),
        (("rev-parse", "HEAD"), tmp_path / "r"),
    ]


def test_pin_keeps_key_order_and_formats_json(tmp_path):
    (tmp_path / "upstream.json").write_text(
        '{"repo": "o/r", "tag": "v1.0.0", "commit": "' + "a" * 40 + '", "submodule": "r", "assets": []}'
    )
    pin(tmp_path, "v1.1.0", git=FakeGit(), download=pytest.fail)
    assert (tmp_path / "upstream.json").read_text() == (
        "{\n"
        '  "repo": "o/r",\n'
        '  "tag": "v1.1.0",\n'
        f'  "commit": "{"f" * 40}",\n'
        '  "submodule": "r",\n'
        '  "assets": []\n'
        "}\n"
    )


def test_pin_first_pin_from_empty_tag_and_commit(tmp_path):
    make_upstream(tmp_path, tag="", commit="")
    result = pin(tmp_path, "v1.1.0", git=FakeGit(head="b" * 40), download=pytest.fail)
    assert (result["tag"], result["commit"]) == ("v1.1.0", "b" * 40)


def test_pin_refreshes_checksums_when_assets_are_set(tmp_path):
    make_upstream(tmp_path, assets=["tool.tar.gz"])
    (tmp_path / "checksums.txt").write_text(f"{'1'*64}  jq-linux-amd64\n{'0'*64}  tool.tar.gz\n")
    sums = f"{'9'*64}  tool.tar.gz\n"
    requested = []

    def download(url):
        requested.append(url)
        return sums.encode()

    result = pin(tmp_path, "v1.1.0", git=FakeGit(), download=download)
    assert requested == ["https://github.com/o/r/releases/download/v1.1.0/SHA256SUMS"]
    assert result["assets"] == ["tool.tar.gz"]
    assert (tmp_path / "checksums.txt").read_text() == f"{'1'*64}  jq-linux-amd64\n{'9'*64}  tool.tar.gz\n"


def test_pin_leaves_upstream_json_alone_when_git_fails(tmp_path):
    make_upstream(tmp_path)
    before = (tmp_path / "upstream.json").read_text()

    def failing_git(*args, cwd):
        raise RuntimeError("fatal: couldn't find remote ref refs/tags/v9.9.9")

    with pytest.raises(RuntimeError):
        pin(tmp_path, "v9.9.9", git=failing_git, download=pytest.fail)
    assert (tmp_path / "upstream.json").read_text() == before


def test_pin_leaves_upstream_json_alone_when_checksums_fail(tmp_path):
    make_upstream(tmp_path, assets=["tool.tar.gz"])
    before = (tmp_path / "upstream.json").read_text()

    def download(url):
        raise not_found(url)

    with pytest.raises(urllib.error.HTTPError):
        pin(tmp_path, "v1.1.0", git=FakeGit(), download=download)
    assert (tmp_path / "upstream.json").read_text() == before


@pytest.mark.parametrize("tag", ["", "-v1.0.0", "--upload-pack=x", "v1 .0"])
def test_pin_rejects_tags_that_are_not_plain_refs(tmp_path, tag):
    make_upstream(tmp_path)
    git = FakeGit()
    with pytest.raises(ValueError):
        pin(tmp_path, tag, git=git, download=pytest.fail)
    assert git.calls == []


def test_pin_rejects_a_head_that_is_not_a_commit_sha(tmp_path):
    make_upstream(tmp_path)
    before = (tmp_path / "upstream.json").read_text()
    with pytest.raises(RuntimeError, match="commit"):
        pin(tmp_path, "v1.1.0", git=FakeGit(head="not-a-sha"), download=pytest.fail)
    assert (tmp_path / "upstream.json").read_text() == before


def test_pin_with_real_git_checks_out_the_tag_commit(tmp_path):
    def git(*args, cwd):
        env = ["-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "init.defaultBranch=main"]
        out = subprocess.run(["git", *env, *args], cwd=cwd, check=True, capture_output=True, text=True)
        return out.stdout

    upstream_repo = tmp_path / "upstream"
    upstream_repo.mkdir()
    git("init", "-q", cwd=upstream_repo)
    (upstream_repo / "f").write_text("one")
    git("add", "f", cwd=upstream_repo)
    git("commit", "-qm", "one", cwd=upstream_repo)
    git("tag", "-a", "v1.0.0", "-m", "v1.0.0", cwd=upstream_repo)
    tagged = git("rev-parse", "HEAD", cwd=upstream_repo).strip()
    (upstream_repo / "f").write_text("two")
    git("commit", "-qam", "two", cwd=upstream_repo)

    agent = tmp_path / "agent"
    agent.mkdir()
    git("clone", "-q", str(upstream_repo), "r", cwd=agent)
    make_upstream(agent, tag="", commit="")

    result = pin(agent, "v1.0.0", git=run_git, download=pytest.fail)
    assert result["commit"] == tagged
    assert git("rev-parse", "HEAD", cwd=agent / "r").strip() == tagged
    assert json.loads((agent / "upstream.json").read_text())["commit"] == tagged


def test_run_git_refuses_a_directory_that_is_not_a_checkout(tmp_path):
    # An uninitialised submodule is an empty folder, and git would otherwise act on the parent repo.
    with pytest.raises(RuntimeError, match="submodule update --init"):
        run_git("checkout", "--detach", "v1.0.0", cwd=tmp_path)


# ---- main -------------------------------------------------------------------------------------


def _days_ago(days):
    return datetime.now(UTC) - timedelta(days=days)


@pytest.fixture
def pins(monkeypatch):
    """Record pin() calls instead of running git."""
    calls = []

    def fake_pin(agent_dir, tag, *, git, download):
        calls.append((agent_dir, tag))
        return {}

    monkeypatch.setattr(bump_agent, "pin", fake_pin)
    return calls


def test_main_picks_and_pins(tmp_path, monkeypatch, capsys, pins):
    agent = tmp_path / "myagent"
    agent.mkdir()
    make_upstream(agent)
    releases = [
        Release("v2.0.0", _days_ago(30)),
        Release("v1.0.2", _days_ago(2)),
        Release("v1.0.1", _days_ago(20)),
    ]
    monkeypatch.setattr(bump_agent, "fetch_releases", lambda repo: releases if repo == "o/r" else pytest.fail(repo))

    assert main([str(agent)]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "agent": "myagent", "from": "v1.0.0", "to": "v1.0.1", "newer_major": "v2.0.0"
    }
    assert pins == [(agent, "v1.0.1")]


def test_main_prints_one_json_line_with_nulls_when_up_to_date(tmp_path, monkeypatch, capsys, pins):
    agent = tmp_path / "myagent"
    agent.mkdir()
    make_upstream(agent, track="")
    monkeypatch.setattr(bump_agent, "fetch_releases", lambda repo: [Release("v1.0.0", _days_ago(30))])

    assert main([str(agent)]) == 0
    out = capsys.readouterr().out
    assert out.count("\n") == 1
    assert json.loads(out) == {"agent": "myagent", "from": "v1.0.0", "to": None, "newer_major": None}
    assert pins == []


def test_main_dry_run_reports_without_pinning(tmp_path, monkeypatch, capsys, pins):
    agent = tmp_path / "myagent"
    agent.mkdir()
    make_upstream(agent)
    monkeypatch.setattr(bump_agent, "fetch_releases", lambda repo: [Release("v1.0.1", _days_ago(20))])

    assert main([str(agent), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "agent": "myagent", "from": "v1.0.0", "to": "v1.0.1", "newer_major": None
    }
    assert pins == []


def test_main_pin_flag_works_from_empty_tag_without_the_network(tmp_path, monkeypatch, capsys, pins):
    agent = tmp_path / "myagent"
    agent.mkdir()
    make_upstream(agent, tag="", commit="")
    monkeypatch.setattr(bump_agent, "fetch_releases", lambda repo: pytest.fail("--pin must not list releases"))

    assert main([str(agent), "--pin", "v1.4.0"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "agent": "myagent", "from": "", "to": "v1.4.0", "newer_major": None
    }
    assert pins == [(agent, "v1.4.0")]


def test_main_pin_flag_with_dry_run_skips_pin(tmp_path, capsys, pins):
    agent = tmp_path / "myagent"
    agent.mkdir()
    make_upstream(agent)
    assert main([str(agent), "--pin", "v1.4.0", "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["to"] == "v1.4.0"
    assert pins == []


def test_main_fails_cleanly_when_the_current_tag_cannot_be_compared(tmp_path, monkeypatch, capsys, pins):
    agent = tmp_path / "myagent"
    agent.mkdir()
    make_upstream(agent, tag="", commit="")
    monkeypatch.setattr(bump_agent, "fetch_releases", lambda repo: [Release("v1.0.0", _days_ago(30))])

    assert main([str(agent)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--pin" in captured.err
    assert pins == []


def test_main_reports_pin_failures_on_stderr(tmp_path, monkeypatch, capsys):
    agent = tmp_path / "myagent"
    agent.mkdir()
    make_upstream(agent)

    def failing_pin(agent_dir, tag, *, git, download):
        raise RuntimeError("fatal: couldn't find remote ref refs/tags/v9.9.9")

    monkeypatch.setattr(bump_agent, "pin", failing_pin)
    assert main([str(agent), "--pin", "v9.9.9"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "couldn't find remote ref" in captured.err
