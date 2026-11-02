import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_agents.py"
_spec = importlib.util.spec_from_file_location("check_agents", SCRIPT)
check_agents = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_agents)
check_agent = check_agents.check_agent

A = "a" * 40
URL = "https://github.com/o/r.git"


def test_valid_agent_has_no_problems(make_agent):
    assert check_agent(make_agent(), gitlink=A, submodule_url=URL, tag_commit=A) == []


def test_contract_name_must_match_folder(make_agent):
    agent = make_agent(contract={"name": "y"})
    assert check_agent(agent, gitlink=A, submodule_url=URL, tag_commit=A) == [
        "x: contract name 'y' does not match folder"
    ]


def test_gitlink_must_match_upstream_commit(make_agent):
    assert check_agent(make_agent(), gitlink="b" * 40, submodule_url=URL, tag_commit=A) == [
        "x: submodule r is at bbbbbbbbbbbb, upstream.json says aaaaaaaaaaaa"
    ]


def test_missing_submodule(make_agent):
    assert check_agent(make_agent(), gitlink=None, submodule_url=URL, tag_commit=A) == ["x: submodule r is missing"]


@pytest.mark.parametrize("url", ["git@github.com:o/r.git", "https://gitlab.com/o/r.git", "https://github.com/o/other.git"])
def test_submodule_url_must_be_upstream_https(make_agent, url):
    assert check_agent(make_agent(), gitlink=A, submodule_url=url, tag_commit=A) == [
        f"x: submodule URL {url} is not https://github.com/o/r.git"
    ]


def test_tag_must_resolve_to_commit(make_agent):
    assert check_agent(make_agent(), gitlink=A, submodule_url=URL, tag_commit="c" * 40) == [
        "x: tag v1.0.0 points at cccccccccccc, not aaaaaaaaaaaa"
    ]


def test_asset_needs_checksum_line(make_agent):
    agent = make_agent(upstream={"assets": ["tool-linux.tar.gz"]}, checksums="")
    assert check_agent(agent, gitlink=A, submodule_url=URL, tag_commit=A) == [
        "x: checksums.txt has no sha256 for tool-linux.tar.gz"
    ]


@pytest.mark.parametrize("field", ["secrets", "ingest_lambda"])
def test_contract_must_not_carry_vals_fields(make_agent, field):
    agent = make_agent(contract={field: {"K": "v"}})
    assert check_agent(agent, gitlink=A, submodule_url=URL, tag_commit=A) == [f"x: contract must not set {field}"]


# Beyond the brief: URL forms, skipped tag check, file and field validation.


def test_submodule_url_without_dot_git_is_accepted(make_agent):
    assert check_agent(make_agent(), gitlink=A, submodule_url="https://github.com/o/r", tag_commit=A) == []


def test_tag_check_is_skipped_when_tag_commit_is_none(make_agent):
    assert check_agent(make_agent(), gitlink=A, submodule_url=URL, tag_commit=None) == []


def test_asset_checksum_line_is_accepted(make_agent):
    sums = f"{'1' * 64}  jq-linux-amd64\n{'2' * 64} *tool-linux.tar.gz\n{'3' * 64}  ./tool-arm.tar.gz\n"
    agent = make_agent(upstream={"assets": ["tool-linux.tar.gz", "tool-arm.tar.gz"]}, checksums=sums)
    assert check_agent(agent, gitlink=A, submodule_url=URL, tag_commit=A) == []


def test_checksum_line_needs_a_real_digest(make_agent):
    agent = make_agent(upstream={"assets": ["tool.tar.gz"]}, checksums="deadbeef  tool.tar.gz\n")
    assert check_agent(agent, gitlink=A, submodule_url=URL, tag_commit=A) == [
        "x: checksums.txt has no sha256 for tool.tar.gz"
    ]


def test_assets_need_a_checksums_file(make_agent):
    agent = make_agent(upstream={"assets": ["tool.tar.gz"]})
    assert check_agent(agent, gitlink=A, submodule_url=URL, tag_commit=A) == ["x: checksums.txt is missing"]


def test_optional_upstream_fields_are_accepted(make_agent):
    agent = make_agent(upstream={"track": "v1."})
    assert check_agent(agent, gitlink=A, submodule_url=URL, tag_commit=A) == []


def test_missing_contract(make_agent):
    agent = make_agent()
    (agent / "contract.yaml").unlink()
    assert check_agent(agent, gitlink=A, submodule_url=URL, tag_commit=A) == ["x: contract.yaml is missing"]


def test_invalid_contract_yaml(make_agent):
    agent = make_agent()
    (agent / "contract.yaml").write_text("name: [unclosed\n")
    problems = check_agent(agent, gitlink=A, submodule_url=URL, tag_commit=A)
    assert len(problems) == 1 and problems[0].startswith("x: contract.yaml is not valid YAML")


def test_contract_must_be_a_mapping(make_agent):
    agent = make_agent()
    (agent / "contract.yaml").write_text("- name\n")
    assert check_agent(agent, gitlink=A, submodule_url=URL, tag_commit=A) == ["x: contract.yaml must be a mapping"]


def test_contract_needs_a_name(make_agent):
    agent = make_agent()
    (agent / "contract.yaml").write_text("install_cmd: bash setup.sh\n")
    assert check_agent(agent, gitlink=A, submodule_url=URL, tag_commit=A) == ["x: contract has no name"]


def test_missing_upstream_json(make_agent):
    agent = make_agent()
    (agent / "upstream.json").unlink()
    assert check_agent(agent, gitlink=A, submodule_url=URL, tag_commit=A) == ["x: upstream.json is missing"]


def test_invalid_upstream_json(make_agent):
    agent = make_agent()
    (agent / "upstream.json").write_text("{nope")
    problems = check_agent(agent, gitlink=A, submodule_url=URL, tag_commit=A)
    assert len(problems) == 1 and problems[0].startswith("x: upstream.json is not valid JSON")


def test_upstream_json_must_be_an_object(make_agent):
    agent = make_agent()
    (agent / "upstream.json").write_text("[]")
    assert check_agent(agent, gitlink=A, submodule_url=URL, tag_commit=A) == ["x: upstream.json must be a JSON object"]


@pytest.mark.parametrize(
    "override, message",
    [
        ({"repo": "just-a-name"}, "x: upstream.json 'repo' must be 'owner/name'"),
        ({"repo": 3}, "x: upstream.json 'repo' must be 'owner/name'"),
        ({"tag": ""}, "x: upstream.json 'tag' must be a non-empty string without spaces or wildcards"),
        ({"tag": "v1.*"}, "x: upstream.json 'tag' must be a non-empty string without spaces or wildcards"),
        ({"commit": "abc123"}, "x: upstream.json 'commit' must be a 40-character lowercase hex SHA"),
        ({"commit": "A" * 40}, "x: upstream.json 'commit' must be a 40-character lowercase hex SHA"),
        ({"submodule": ""}, "x: upstream.json 'submodule' must be a relative path inside the agent folder"),
        ({"submodule": "../r"}, "x: upstream.json 'submodule' must be a relative path inside the agent folder"),
        ({"submodule": "/r"}, "x: upstream.json 'submodule' must be a relative path inside the agent folder"),
        ({"track": 1}, "x: upstream.json 'track' must be a string"),
        ({"assets": "tool.tar.gz"}, "x: upstream.json 'assets' must be a list of file names"),
        ({"assets": [""]}, "x: upstream.json 'assets' must be a list of file names"),
    ],
)
def test_upstream_json_field_validation(make_agent, override, message):
    agent = make_agent(upstream=override)
    assert check_agent(agent, gitlink=A, submodule_url=URL, tag_commit=A) == [message]


@pytest.mark.parametrize("field", ["repo", "tag", "commit", "submodule"])
def test_upstream_json_requires_core_fields(make_agent, field):
    agent = make_agent()
    data = json.loads((agent / "upstream.json").read_text())
    del data[field]
    (agent / "upstream.json").write_text(json.dumps(data))
    problems = check_agent(agent, gitlink=A, submodule_url=URL, tag_commit=A)
    assert len(problems) == 1 and problems[0].startswith(f"x: upstream.json '{field}' must be")


def test_submodule_without_url(make_agent):
    assert check_agent(make_agent(), gitlink=A, submodule_url=None, tag_commit=A) == [
        "x: submodule r has no URL in .gitmodules"
    ]


def test_problems_accumulate_in_a_stable_order(make_agent):
    agent = make_agent(contract={"name": "y", "secrets": {"K": "v"}})
    assert check_agent(agent, gitlink="b" * 40, submodule_url="git@github.com:o/r.git", tag_commit="c" * 40) == [
        "x: contract name 'y' does not match folder",
        "x: contract must not set secrets",
        "x: submodule r is at bbbbbbbbbbbb, upstream.json says aaaaaaaaaaaa",
        "x: submodule URL git@github.com:o/r.git is not https://github.com/o/r.git",
        "x: tag v1.0.0 points at cccccccccccc, not aaaaaaaaaaaa",
    ]


# Tag resolution.


def test_parse_tag_commit_prefers_peeled_line():
    out = f"{'1' * 40}\trefs/tags/v1.0.0\n{'2' * 40}\trefs/tags/v1.0.0^{{}}\n"
    assert check_agents.parse_tag_commit(out, "v1.0.0") == "2" * 40


def test_parse_tag_commit_peeled_line_wins_in_any_order():
    out = f"{'2' * 40}\trefs/tags/v1.0.0^{{}}\n{'1' * 40}\trefs/tags/v1.0.0\n"
    assert check_agents.parse_tag_commit(out, "v1.0.0") == "2" * 40


def test_parse_tag_commit_falls_back_to_lightweight_tag():
    assert check_agents.parse_tag_commit(f"{'1' * 40}\trefs/tags/v1.0.0\n", "v1.0.0") == "1" * 40


def test_parse_tag_commit_ignores_other_refs():
    out = f"{'1' * 40}\trefs/tags/v1.0.0-rc1\n{'2' * 40}\trefs/tags/other/v1.0.0\n"
    assert check_agents.parse_tag_commit(out, "v1.0.0") is None


def test_parse_tag_commit_empty_output():
    assert check_agents.parse_tag_commit("", "v1.0.0") is None


def git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def test_fetch_tag_commit_returns_the_commit_behind_an_annotated_tag(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    git(work, "init", "-q")
    (work / "f").write_text("1")
    git(work, "add", "f")
    git(work, "commit", "-q", "-m", "one")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=work, check=True, capture_output=True, text=True
    ).stdout.strip()
    git(work, "tag", "-a", "v1.0.0", "-m", "annotated")
    git(work, "tag", "light")
    (tmp_path / "o").mkdir()
    git(tmp_path, "clone", "-q", "--bare", str(work), str(tmp_path / "o" / "r.git"))
    monkeypatch.setattr(check_agents, "GITHUB", f"file://{tmp_path}")

    assert check_agents.fetch_tag_commit("o/r", "v1.0.0") == commit
    assert check_agents.fetch_tag_commit("o/r", "light") == commit
    assert check_agents.fetch_tag_commit("o/r", "nope") is None


def test_fetch_tag_commit_raises_when_the_remote_cannot_be_read(tmp_path, monkeypatch):
    monkeypatch.setattr(check_agents, "GITHUB", f"file://{tmp_path}")
    with pytest.raises(RuntimeError):
        check_agents.fetch_tag_commit("o/missing", "v1.0.0")


# Reading gitlinks from the index.


def test_read_gitlink_sees_a_staged_gitlink_before_any_commit(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "update-index", "--add", "--cacheinfo", f"160000,{A},agents/x/r")
    assert check_agents.read_gitlink(tmp_path, "agents/x/r") == A


def test_read_gitlink_is_none_without_an_entry(tmp_path):
    git(tmp_path, "init", "-q")
    assert check_agents.read_gitlink(tmp_path, "agents/x/r") is None


def test_read_gitlink_is_none_for_a_plain_directory(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "agents" / "x" / "r").mkdir(parents=True)
    (tmp_path / "agents" / "x" / "r" / "f").write_text("1")
    git(tmp_path, "add", "agents/x/r/f")
    assert check_agents.read_gitlink(tmp_path, "agents/x/r") is None


# main() against a throwaway git repository.


@pytest.fixture
def registry(tmp_path, monkeypatch, make_agent):
    """A git repo at tmp_path whose agents/x submodule r is pinned to A."""

    def build(*, gitlink: str | None = A, url: str | None = URL, **agent_overrides) -> Path:
        agent = make_agent(**agent_overrides)
        git(tmp_path, "init", "-q")
        if gitlink is not None:
            git(tmp_path, "update-index", "--add", "--cacheinfo", f"160000,{gitlink},agents/x/r")
        if url is not None:
            git(tmp_path, "config", "-f", ".gitmodules", "submodule.agents/x/r.path", "agents/x/r")
            git(tmp_path, "config", "-f", ".gitmodules", "submodule.agents/x/r.url", url)
            git(tmp_path, "add", ".gitmodules")
        git(tmp_path, "commit", "-q", "--allow-empty", "-m", "init")
        monkeypatch.setattr(check_agents, "ROOT", tmp_path)
        return agent

    return build


def test_main_with_no_agents_is_silent(tmp_path, monkeypatch, capsys):
    git(tmp_path, "init", "-q")
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / ".gitkeep").write_text("")
    monkeypatch.setattr(check_agents, "ROOT", tmp_path)
    assert check_agents.main(["--offline"]) == 0
    assert capsys.readouterr().out == ""


def test_main_passes_a_valid_agent_offline(registry, capsys):
    registry()
    assert check_agents.main(["--offline"]) == 0
    assert capsys.readouterr().out == ""


def test_main_reports_a_gitlink_mismatch(registry, capsys):
    registry(gitlink="b" * 40)
    assert check_agents.main(["--offline"]) == 1
    assert capsys.readouterr().out == "x: submodule r is at bbbbbbbbbbbb, upstream.json says aaaaaaaaaaaa\n"


def test_main_reports_a_missing_submodule(registry, capsys):
    registry(gitlink=None, url=None)
    assert check_agents.main(["--offline"]) == 1
    assert capsys.readouterr().out == "x: submodule r is missing\n"


def test_main_reports_when_git_cannot_read_the_submodule(registry, tmp_path, capsys):
    registry()
    (tmp_path / ".git" / "index").write_text("not an index")  # `git ls-files` fails
    assert check_agents.main(["--offline"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("x: submodule r is missing\nx: could not read submodule agents/x/r from git: ")


def test_main_reads_the_gitlink_from_the_index_not_head(registry, tmp_path, capsys):
    registry()  # HEAD pins agents/x/r to A
    git(tmp_path, "update-index", "--cacheinfo", f"160000,{'b' * 40},agents/x/r")  # staged bump, not committed
    assert check_agents.main(["--offline"]) == 1
    assert capsys.readouterr().out == "x: submodule r is at bbbbbbbbbbbb, upstream.json says aaaaaaaaaaaa\n"

    (tmp_path / "agents" / "x" / "upstream.json").write_text(
        json.dumps({"repo": "o/r", "tag": "v1.0.0", "commit": "b" * 40, "submodule": "r"})
    )
    assert check_agents.main(["--offline"]) == 0
    assert capsys.readouterr().out == ""


def test_main_reports_a_bad_submodule_url(registry, capsys):
    registry(url="git@github.com:o/r.git")
    assert check_agents.main(["--offline"]) == 1
    assert capsys.readouterr().out == "x: submodule URL git@github.com:o/r.git is not https://github.com/o/r.git\n"


def test_main_reports_a_bad_contract_name(registry, capsys):
    registry(contract={"name": "y"})
    assert check_agents.main(["--offline"]) == 1
    assert capsys.readouterr().out == "x: contract name 'y' does not match folder\n"


def test_main_checks_the_tag_unless_offline(registry, monkeypatch, capsys):
    registry()
    calls = []

    def fake_fetch(repo, tag):
        calls.append((repo, tag))
        return "c" * 40

    monkeypatch.setattr(check_agents, "fetch_tag_commit", fake_fetch)
    assert check_agents.main([]) == 1
    assert calls == [("o/r", "v1.0.0")]
    assert capsys.readouterr().out == "x: tag v1.0.0 points at cccccccccccc, not aaaaaaaaaaaa\n"

    calls.clear()
    assert check_agents.main(["--offline"]) == 0
    assert calls == []


def test_main_passes_when_the_tag_matches(registry, monkeypatch, capsys):
    registry()
    monkeypatch.setattr(check_agents, "fetch_tag_commit", lambda repo, tag: A)
    assert check_agents.main([]) == 0
    assert capsys.readouterr().out == ""


def test_main_reports_a_tag_that_does_not_exist_upstream(registry, monkeypatch, capsys):
    registry()
    monkeypatch.setattr(check_agents, "fetch_tag_commit", lambda repo, tag: None)
    assert check_agents.main([]) == 1
    assert capsys.readouterr().out == "x: tag v1.0.0 not found in o/r\n"


def test_main_reports_a_failed_tag_lookup(registry, monkeypatch, capsys):
    registry()

    def boom(repo, tag):
        raise RuntimeError("network down")

    monkeypatch.setattr(check_agents, "fetch_tag_commit", boom)
    assert check_agents.main([]) == 1
    assert capsys.readouterr().out == "x: could not look up tag v1.0.0 in o/r: network down\n"


def test_main_reports_a_broken_upstream_json_once(registry, capsys):
    agent = registry()
    (agent / "upstream.json").write_text("[]")
    assert check_agents.main(["--offline"]) == 1
    assert capsys.readouterr().out == "x: upstream.json must be a JSON object\n"


def test_main_checks_every_agent(tmp_path, monkeypatch, make_agent, capsys):
    make_agent(folder="a1")
    make_agent(folder="a2", contract={"name": "zzz"})
    git(tmp_path, "init", "-q")
    for name in ("a1", "a2"):
        git(tmp_path, "update-index", "--add", "--cacheinfo", f"160000,{A},agents/{name}/r")
        git(tmp_path, "config", "-f", ".gitmodules", f"submodule.agents/{name}/r.path", f"agents/{name}/r")
        git(tmp_path, "config", "-f", ".gitmodules", f"submodule.agents/{name}/r.url", URL)
    git(tmp_path, "add", ".gitmodules")
    git(tmp_path, "commit", "-q", "-m", "init")
    monkeypatch.setattr(check_agents, "ROOT", tmp_path)
    assert check_agents.main(["--offline"]) == 1
    assert capsys.readouterr().out == "a2: contract name 'zzz' does not match folder\n"


# Submodules across the whole repository.


def test_check_repo_accepts_agent_submodules_and_https_urls():
    modules = {
        "agents/x/r": {"path": "agents/x/r", "url": "https://github.com/o/r.git"},
        "examples/e": {"path": "examples/e", "url": "https://github.com/o/e"},  # .gitmodules entry, no gitlink
    }
    assert check_agents.check_repo(["agents/x/r"], modules, {"agents/x/r"}) == []


@pytest.mark.parametrize("path", ["examples/x", "agents/foo/r", "agents/x/other", "r"])
def test_check_repo_reports_a_stray_gitlink(path):
    assert check_agents.check_repo(["agents/x/r", path], {}, {"agents/x/r"}) == [
        f"{path}: submodule does not belong to an agent "
        "(each submodule must be agents/<agent>/<submodule> from that agent's upstream.json)"
    ]


@pytest.mark.parametrize(
    "url",
    [
        "git@github.com:o/r.git",
        "http://github.com/o/r.git",
        "ssh://git@github.com/o/r.git",
        "https://gitlab.com/o/r.git",
        "https://github.com/o",
        "https://github.com/o/r/",
        "https://github.com/o/r/tree/main",
        "file:///tmp/r",
        "../r",
    ],
)
def test_check_repo_reports_a_url_that_is_not_https_github(url):
    modules = {"examples/e": {"path": "examples/e", "url": url}}
    assert check_agents.check_repo([], modules, {"agents/x/r"}) == [
        f".gitmodules: submodule examples/e URL {url} is not https://github.com/<owner>/<repo>"
    ]


def test_check_repo_leaves_an_agents_own_url_to_the_agent_check():
    modules = {"agents/x/r": {"path": "agents/x/r", "url": "git@github.com:o/r.git"}}
    assert check_agents.check_repo(["agents/x/r"], modules, {"agents/x/r"}) == []


def test_check_repo_reports_a_second_entry_for_an_agents_path():
    # The agent check reads submodule.<path>.url, but git fetches with whichever entry it picks.
    modules = {
        "agents/x/r": {"path": "agents/x/r", "url": "https://github.com/o/r.git"},
        "other": {"path": "agents/x/r", "url": "git@evil.example:o/r.git"},
    }
    assert check_agents.check_repo(["agents/x/r"], modules, {"agents/x/r"}) == [
        ".gitmodules: submodules agents/x/r and other both use path agents/x/r",
        ".gitmodules: submodule other URL git@evil.example:o/r.git is not https://github.com/<owner>/<repo>",
    ]


def test_check_repo_reports_a_duplicate_path_even_with_https_urls():
    modules = {
        "examples/e": {"path": "examples/e", "url": "https://github.com/o/e"},
        "e2": {"path": "examples/e", "url": "https://github.com/o/e2"},
    }
    assert check_agents.check_repo([], modules, {"agents/x/r"}) == [
        ".gitmodules: submodules examples/e and e2 both use path examples/e"
    ]


def test_read_gitlinks_and_gitmodules(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "update-index", "--add", "--cacheinfo", f"160000,{A},agents/x/r")
    git(tmp_path, "update-index", "--add", "--cacheinfo", f"160000,{A},dir with space/s")
    (tmp_path / "f").write_text("1")
    git(tmp_path, "add", "f")
    git(tmp_path, "config", "-f", ".gitmodules", "submodule.a.b/c.path", "a.b/c")
    git(tmp_path, "config", "-f", ".gitmodules", "submodule.a.b/c.url", "git@github.com:o/r.git")
    assert check_agents.read_gitlinks(tmp_path) == ["agents/x/r", "dir with space/s"]
    assert check_agents.read_gitmodules(tmp_path) == {"a.b/c": {"path": "a.b/c", "url": "git@github.com:o/r.git"}}


def test_read_gitmodules_without_a_file(tmp_path):
    git(tmp_path, "init", "-q")
    assert check_agents.read_gitmodules(tmp_path) == {}


def add_submodule(root, path, url, commit=A):
    git(root, "update-index", "--add", "--cacheinfo", f"160000,{commit},{path}")
    git(root, "config", "-f", ".gitmodules", f"submodule.{path}.path", path)
    git(root, "config", "-f", ".gitmodules", f"submodule.{path}.url", url)
    git(root, "add", ".gitmodules")


@pytest.mark.parametrize("path", ["examples/x", "agents/foo/r"])
def test_main_reports_a_stray_submodule(registry, tmp_path, capsys, path):
    registry()
    (tmp_path / "agents" / "foo").mkdir()  # a folder with no contract.yaml, so no agent checks it
    add_submodule(tmp_path, path, f"https://github.com/o/{path.replace('/', '-')}.git")
    assert check_agents.main(["--offline"]) == 1
    assert capsys.readouterr().out == (
        f"{path}: submodule does not belong to an agent "
        "(each submodule must be agents/<agent>/<submodule> from that agent's upstream.json)\n"
    )


def test_main_reports_a_gitmodules_url_that_is_not_https(registry, tmp_path, capsys):
    registry()
    git(tmp_path, "config", "-f", ".gitmodules", "submodule.examples/x.path", "examples/x")
    git(tmp_path, "config", "-f", ".gitmodules", "submodule.examples/x.url", "git@github.com:o/x.git")
    assert check_agents.main(["--offline"]) == 1
    assert capsys.readouterr().out == (
        ".gitmodules: submodule examples/x URL git@github.com:o/x.git is not https://github.com/<owner>/<repo>\n"
    )


def test_main_reports_a_stray_submodule_with_a_bad_url_twice(registry, tmp_path, capsys):
    registry()
    add_submodule(tmp_path, "examples/x", "git@github.com:o/x.git")
    assert check_agents.main(["--offline"]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "examples/x: submodule does not belong to an agent "
        "(each submodule must be agents/<agent>/<submodule> from that agent's upstream.json)",
        ".gitmodules: submodule examples/x URL git@github.com:o/x.git is not https://github.com/<owner>/<repo>",
    ]


def test_main_reports_an_agents_bad_url_once(registry, capsys):
    registry(url="http://github.com/o/r.git")
    assert check_agents.main(["--offline"]) == 1
    assert capsys.readouterr().out == "x: submodule URL http://github.com/o/r.git is not https://github.com/o/r.git\n"


def test_check_repo_leaves_a_broken_agents_submodules_to_the_agent_check():
    assert check_agents.check_repo(["agents/x/r", "agents/xy/r"], {}, set(), {"agents/x"}) == [
        "agents/xy/r: submodule does not belong to an agent "
        "(each submodule must be agents/<agent>/<submodule> from that agent's upstream.json)"
    ]


def test_main_reports_when_git_cannot_list_the_submodules(tmp_path, monkeypatch, capsys):
    (tmp_path / "agents").mkdir()  # not a git repository
    monkeypatch.setattr(check_agents, "ROOT", tmp_path)
    assert check_agents.main(["--offline"]) == 1
    assert capsys.readouterr().out.startswith("could not list the submodules from git: ")
