import json
import os
import subprocess
from pathlib import Path

import pytest

FINISH = Path(__file__).resolve().parents[2] / "agents" / "opencode" / "finish.sh"
UPSTREAM = {"repo": "anomalyco/opencode", "tag": "v1.19.4", "commit": "a" * 40, "submodule": "opencode"}


def finish(tmp_path, *, events, rc, with_error_path=True, env=None, upstream_text=None):
    """Run finish.sh on a JSONL events file and check that it left a well-formed summary.json.

    ``events`` items are dicts (one JSON line each) or raw strings; None passes a path that does not
    exist. ``upstream_text`` replaces the contents of upstream.json (None keeps the default, False
    writes no upstream.json at all).
    """
    events_file = tmp_path / "events.jsonl"
    if events is not None:
        events_file.write_text("".join((e if isinstance(e, str) else json.dumps(e)) + "\n" for e in events))
    upstream = tmp_path / "upstream.json"
    if upstream_text is not False:
        upstream.write_text(json.dumps(UPSTREAM) if upstream_text is None else upstream_text)
    base = {k: v for k, v in os.environ.items() if k not in ("JQ", "VALKYRIE_ERROR_PATH")}
    if with_error_path:
        base["VALKYRIE_ERROR_PATH"] = str(tmp_path / "err")
    result = subprocess.run(
        ["bash", str(FINISH), str(events_file), str(rc), str(upstream), str(tmp_path / "out")],
        env={**base, **(env or {})},
        capture_output=True,
        text=True,
    )
    data = summary(tmp_path)
    assert set(data) == {"agent", "upstream", "outcome", "stop_reason", "agent_exit_code"}
    assert data["agent"] == "opencode"
    assert not (tmp_path / "out" / "summary.json.tmp").exists()
    return result


def summary(tmp_path):
    return json.loads((tmp_path / "out" / "summary.json").read_text())


def error_event(name, message="SECRET PROMPT"):
    """The event ``opencode run --format json`` prints for a session.error (run.ts ``emit("error", ...)``)."""
    return {
        "type": "error",
        "timestamp": 1790000000000,
        "sessionID": "ses_1",
        "error": {"name": name, "data": {"providerID": "anthropic", "message": message}},
    }


def test_success(tmp_path):
    r = finish(
        tmp_path,
        events=[{"type": "step_start", "sessionID": "ses_1"}, {"type": "step_finish", "sessionID": "ses_1"}],
        rc=0,
    )
    assert r.returncode == 0
    assert summary(tmp_path) == {
        "agent": "opencode",
        "upstream": UPSTREAM,
        "outcome": "completed",
        "stop_reason": "completed",
        "agent_exit_code": 0,
    }
    assert not (tmp_path / "err").exists()


def test_error_event_names_error_without_its_message(tmp_path):
    r = finish(tmp_path, events=[error_event("ProviderAuthError")], rc=1)
    assert r.returncode == 1
    assert (tmp_path / "err").read_text() == "AgentError: opencode exited with code 1 (ProviderAuthError)\n"
    assert summary(tmp_path) == {
        "agent": "opencode",
        "upstream": UPSTREAM,
        "outcome": "error",
        "stop_reason": "error",
        "agent_exit_code": 1,
    }
    assert "SECRET PROMPT" not in r.stdout + r.stderr + (tmp_path / "out" / "summary.json").read_text()


def test_last_error_event_wins(tmp_path):
    events = [error_event("APIError"), {"type": "step_start", "sessionID": "ses_1"}, error_event("MessageAbortedError")]
    finish(tmp_path, events=events, rc=1)
    assert (tmp_path / "err").read_text() == "AgentError: opencode exited with code 1 (MessageAbortedError)\n"


def test_crash_before_any_event(tmp_path):
    r = finish(tmp_path, events=[], rc=2)
    assert r.returncode == 2
    assert (tmp_path / "err").read_text() == "AgentError: opencode exited with code 2\n"
    assert summary(tmp_path)["outcome"] == "error"
    assert summary(tmp_path)["agent_exit_code"] == 2


def test_missing_events_file(tmp_path):
    r = finish(tmp_path, events=None, rc=1)
    assert r.returncode == 1
    assert (tmp_path / "err").read_text() == "AgentError: opencode exited with code 1\n"
    assert summary(tmp_path)["outcome"] == "error"


def test_wholly_non_json_events_file(tmp_path):
    r = finish(tmp_path, events=["SECRET PROMPT", "not json at all", "{"], rc=1)
    assert r.returncode == 1
    assert (tmp_path / "err").read_text() == "AgentError: opencode exited with code 1\n"
    assert summary(tmp_path) == {
        "agent": "opencode",
        "upstream": UPSTREAM,
        "outcome": "error",
        "stop_reason": "error",
        "agent_exit_code": 1,
    }
    assert "SECRET PROMPT" not in r.stdout + r.stderr + (tmp_path / "out" / "summary.json").read_text()


def test_non_json_events_file_after_a_clean_exit(tmp_path):
    r = finish(tmp_path, events=["not json at all"], rc=0)
    assert r.returncode == 0
    assert summary(tmp_path)["outcome"] == "completed"
    assert not (tmp_path / "err").exists()


def test_killed_passes_137_through(tmp_path):
    r = finish(tmp_path, events=[], rc=137)
    assert r.returncode == 137
    assert summary(tmp_path) == {
        "agent": "opencode",
        "upstream": UPSTREAM,
        "outcome": "killed",
        "stop_reason": "killed",
        "agent_exit_code": 137,
    }
    assert not (tmp_path / "err").exists()


def test_killed_ignores_error_events(tmp_path):
    r = finish(tmp_path, events=[error_event("APIError")], rc=137)
    assert r.returncode == 137
    assert not (tmp_path / "err").exists()


def test_truncated_last_line_is_ignored(tmp_path):
    """A kill can cut the last event short; the events before it still count."""
    events = [error_event("APIError"), '{"type": "step_start", "sessio']
    r = finish(tmp_path, events=events, rc=1)
    assert r.returncode == 1
    assert (tmp_path / "err").read_text() == "AgentError: opencode exited with code 1 (APIError)\n"


def test_error_without_a_name_is_reported_by_exit_code_only(tmp_path):
    events = [
        {"type": "error", "sessionID": "ses_1", "error": "SECRET PROMPT"},
        {"type": "error", "sessionID": "ses_1", "error": {"data": {"message": "SECRET PROMPT"}}},
    ]
    r = finish(tmp_path, events=events, rc=1)
    assert r.returncode == 1
    assert (tmp_path / "err").read_text() == "AgentError: opencode exited with code 1\n"


def test_error_name_is_never_free_text(tmp_path):
    finish(tmp_path, events=[error_event("SECRET PROMPT with spaces")], rc=1)
    assert (tmp_path / "err").read_text() == "AgentError: opencode exited with code 1\n"


def test_error_line_is_one_short_line(tmp_path):
    finish(tmp_path, events=[error_event("E" * 5000)], rc=1)
    line = (tmp_path / "err").read_text()
    assert line == "AgentError: opencode exited with code 1\n"
    assert len(line) <= 513


def test_without_error_path_still_writes_summary(tmp_path):
    r = finish(tmp_path, events=[error_event("APIError")], rc=1, with_error_path=False)
    assert r.returncode == 1
    assert summary(tmp_path)["outcome"] == "error"


def test_exit_code_that_is_not_a_number_counts_as_1(tmp_path):
    r = finish(tmp_path, events=[error_event("APIError")], rc="oops")
    assert r.returncode == 1
    assert summary(tmp_path)["agent_exit_code"] == 1
    assert (tmp_path / "err").read_text() == "AgentError: opencode exited with code 1 (APIError)\n"


def test_exit_code_above_255_counts_as_1(tmp_path):
    # exit 256 would wrap to 0 and look like success.
    r = finish(tmp_path, events=[], rc=256)
    assert r.returncode == 1
    assert summary(tmp_path)["outcome"] == "error"


# summary.json and the error line are written best effort: the mapped exit code always wins.

CODES = [(0, "completed", None), (1, "error", "AgentError: opencode exited with code 1\n"), (137, "killed", None)]


@pytest.mark.parametrize(("rc", "outcome", "line"), CODES)
@pytest.mark.parametrize("upstream_text", ["{ not json", False], ids=["invalid", "missing"])
def test_unreadable_upstream_json_keeps_the_exit_code(tmp_path, rc, outcome, line, upstream_text):
    r = finish(tmp_path, events=[], rc=rc, upstream_text=upstream_text)
    assert r.returncode == rc
    assert summary(tmp_path) == {
        "agent": "opencode",
        "upstream": None,
        "outcome": outcome,
        "stop_reason": outcome,
        "agent_exit_code": rc,
    }
    if line is None:
        assert not (tmp_path / "err").exists()
    else:
        assert (tmp_path / "err").read_text() == line


@pytest.mark.parametrize(("rc", "outcome", "line"), CODES)
def test_broken_jq_keeps_the_exit_code(tmp_path, rc, outcome, line):
    r = finish(tmp_path, events=[error_event("APIError")], rc=rc, env={"JQ": str(tmp_path / "no-such-jq")})
    assert r.returncode == rc
    assert summary(tmp_path) == {
        "agent": "opencode",
        "upstream": None,
        "outcome": outcome,
        "stop_reason": outcome,
        "agent_exit_code": rc,
    }
    if line is None:
        assert not (tmp_path / "err").exists()
    else:
        assert (tmp_path / "err").read_text() == line


@pytest.mark.parametrize("rc", [0, 1, 137])
def test_summary_that_cannot_be_written_keeps_the_exit_code(tmp_path, rc):
    (tmp_path / "out").write_text("a file where the output folder should be")
    (tmp_path / "events.jsonl").write_text("")
    (tmp_path / "upstream.json").write_text(json.dumps(UPSTREAM))
    env = {k: v for k, v in os.environ.items() if k not in ("JQ", "VALKYRIE_ERROR_PATH")}
    env["VALKYRIE_ERROR_PATH"] = str(tmp_path / "no-such-dir" / "err")
    r = subprocess.run(
        ["bash", str(FINISH), str(tmp_path / "events.jsonl"), str(rc), str(tmp_path / "upstream.json"), str(tmp_path / "out")],
        env=env,
        capture_output=True,
        text=True,
    )
    assert r.returncode == rc
    assert f"finish.sh: could not write {tmp_path / 'out'}/summary.json" in r.stderr
    assert ("finish.sh: could not write the error line" in r.stderr) == (rc == 1)
