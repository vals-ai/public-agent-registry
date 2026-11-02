import json
import os
import subprocess
from pathlib import Path

FINISH = Path(__file__).resolve().parents[2] / "agents" / "opencode" / "finish.sh"
UPSTREAM = {"repo": "anomalyco/opencode", "tag": "v1.19.4", "commit": "a" * 40, "submodule": "opencode"}


def finish(tmp_path, *, events, rc, with_error_path=True):
    """Run finish.sh on a JSONL events file. ``events`` items are dicts (one JSON line each) or raw strings."""
    events_file = tmp_path / "events.jsonl"
    events_file.write_text("".join((e if isinstance(e, str) else json.dumps(e)) + "\n" for e in events))
    upstream = tmp_path / "upstream.json"
    upstream.write_text(json.dumps(UPSTREAM))
    env = {k: v for k, v in os.environ.items() if k not in ("JQ", "VALKYRIE_ERROR_PATH")}
    if with_error_path:
        env["VALKYRIE_ERROR_PATH"] = str(tmp_path / "err")
    return subprocess.run(
        ["bash", str(FINISH), str(events_file), str(rc), str(upstream), str(tmp_path / "out")],
        env=env,
        capture_output=True,
        text=True,
    )


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
    upstream = tmp_path / "upstream.json"
    upstream.write_text(json.dumps(UPSTREAM))
    env = {**os.environ, "VALKYRIE_ERROR_PATH": str(tmp_path / "err")}
    env.pop("JQ", None)
    r = subprocess.run(
        ["bash", str(FINISH), str(tmp_path / "nope.jsonl"), "1", str(upstream), str(tmp_path / "out")],
        env=env,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1
    assert (tmp_path / "err").read_text() == "AgentError: opencode exited with code 1\n"


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
