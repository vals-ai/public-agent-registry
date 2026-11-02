import itertools
import json
import os
import subprocess
from pathlib import Path

FINISH = Path(__file__).resolve().parents[2] / "agents" / "pi" / "finish.sh"
UPSTREAM = {"repo": "earendil-works/pi", "tag": "v1.4.0", "commit": "a" * 40, "submodule": "pi"}

# Entries as pi writes them to a session file (packages/coding-agent/docs/session-format.md).
SESSION_HEADER = {
    "type": "session",
    "version": 3,
    "id": "0d2f6b5e-6f1a-4a47-8d0e-5d6d1f0c9a11",
    "timestamp": "2026-11-01T14:00:00.000Z",
    "cwd": "/testbed",
}
_ids = itertools.count(1)


def _entry(message):
    n = next(_ids)
    return {
        "type": "message",
        "id": f"{n:08x}",
        "parentId": None if n == 1 else f"{n - 1:08x}",
        "timestamp": "2026-11-01T14:00:01.000Z",
        "message": message,
    }


def user(text="SECRET PROMPT"):
    return _entry({"role": "user", "content": [{"type": "text", "text": text}], "timestamp": 1790000001000})


def tool_result(text="SECRET PROMPT"):
    return _entry(
        {
            "role": "toolResult",
            "toolCallId": "call_1",
            "toolName": "bash",
            "content": [{"type": "text", "text": text}],
            "isError": False,
            "timestamp": 1790000003000,
        }
    )


def assistant(stop_reason, **extra):
    """An assistant message entry (AgentMessage, packages/ai/src/types.ts AssistantMessage)."""
    message = {
        "role": "assistant",
        "content": [{"type": "text", "text": "SECRET PROMPT"}],
        "api": "anthropic-messages",
        "provider": "anthropic",
        "model": "claude-sonnet-4-5",
        "usage": {
            "input": 10,
            "output": 5,
            "cacheRead": 0,
            "cacheWrite": 0,
            "totalTokens": 15,
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "total": 0},
        },
        "stopReason": stop_reason,
        "timestamp": 1790000002000,
        **extra,
    }
    return _entry(message)


def finish(
    tmp_path,
    *,
    session,
    rc,
    with_error_path=True,
    env=None,
    upstream_text=None,
    extra_sessions=(),
):
    """Run finish.sh on ``tmp_path/sessions``.

    ``session`` is a list written as the one session file (items are dicts, one JSON line each, or raw
    strings), or None for no session file. ``extra_sessions`` are (name, items, mtime) files written
    beside it; the session directory exists only when there is at least one file. Every run must leave a well-formed summary.json behind.
    """
    sessions = tmp_path / "sessions"
    if session is not None or extra_sessions:
        sessions.mkdir()
    if session is not None:
        write_session(sessions / "2026-11-01T14-00-00-000Z_0d2f.jsonl", session, mtime=1_790_000_100)
    for name, items, mtime in extra_sessions:
        write_session(sessions / name, items, mtime=mtime)
    upstream = tmp_path / "upstream.json"
    upstream.write_text(json.dumps(UPSTREAM) if upstream_text is None else upstream_text)
    base = {k: v for k, v in os.environ.items() if k not in ("JQ", "VALKYRIE_ERROR_PATH")}
    if with_error_path:
        base["VALKYRIE_ERROR_PATH"] = str(tmp_path / "err")
    result = subprocess.run(
        ["bash", str(FINISH), str(sessions), str(rc), str(upstream), str(tmp_path / "out")],
        env={**base, **(env or {})},
        capture_output=True,
        text=True,
    )
    data = summary(tmp_path)
    assert set(data) == {"agent", "upstream", "outcome", "stop_reason", "agent_exit_code"}
    assert data["agent"] == "pi"
    return result


def write_session(path, items, *, mtime):
    path.write_text("".join((e if isinstance(e, str) else json.dumps(e)) + "\n" for e in items))
    os.utime(path, (mtime, mtime))


def summary(tmp_path):
    return json.loads((tmp_path / "out" / "summary.json").read_text())


def error_line(tmp_path):
    return (tmp_path / "err").read_text()


def test_success(tmp_path):
    r = finish(tmp_path, session=[SESSION_HEADER, user(), assistant("stop")], rc=0)
    assert r.returncode == 0
    assert summary(tmp_path) == {
        "agent": "pi",
        "upstream": UPSTREAM,
        "outcome": "completed",
        "stop_reason": "stop",
        "agent_exit_code": 0,
    }
    assert not (tmp_path / "err").exists()


def test_length_stop_is_graded(tmp_path):
    r = finish(tmp_path, session=[SESSION_HEADER, assistant("toolUse"), assistant("length")], rc=1)
    assert r.returncode == 0
    assert summary(tmp_path) | {"upstream": None} == {
        "agent": "pi",
        "upstream": None,
        "outcome": "completed",
        "stop_reason": "length",
        "agent_exit_code": 1,
    }
    assert summary(tmp_path)["upstream"] == UPSTREAM
    assert not (tmp_path / "err").exists()


def test_error_stop(tmp_path):
    r = finish(
        tmp_path,
        session=[SESSION_HEADER, user(), assistant("error", errorMessage="SECRET PROMPT")],
        rc=1,
    )
    assert r.returncode == 1
    assert error_line(tmp_path) == "AgentError: pi exited with code 1 (stop: error)\n"
    assert summary(tmp_path) == {
        "agent": "pi",
        "upstream": UPSTREAM,
        "outcome": "error",
        "stop_reason": "error",
        "agent_exit_code": 1,
    }
    assert "SECRET PROMPT" not in r.stdout + r.stderr + (tmp_path / "out" / "summary.json").read_text()


def test_aborted_stop(tmp_path):
    r = finish(tmp_path, session=[SESSION_HEADER, assistant("aborted")], rc=1)
    assert r.returncode == 1
    assert error_line(tmp_path) == "AgentError: pi exited with code 1 (stop: aborted)\n"


def test_no_session(tmp_path):
    r = finish(tmp_path, session=None, rc=1)
    assert r.returncode == 1
    assert error_line(tmp_path) == "AgentError: pi exited with code 1 (no session)\n"
    assert summary(tmp_path) == {
        "agent": "pi",
        "upstream": UPSTREAM,
        "outcome": "error",
        "stop_reason": "unknown",
        "agent_exit_code": 1,
    }


def test_directory_without_jsonl_files_counts_as_no_session(tmp_path):
    r = finish(tmp_path, session=None, rc=2, extra_sessions=[("notes.txt", ["not a session"], 1_790_000_000)])
    assert r.returncode == 2
    assert error_line(tmp_path) == "AgentError: pi exited with code 2 (no session)\n"
    assert summary(tmp_path)["agent_exit_code"] == 2


def test_other_exit_codes_are_errors(tmp_path):
    r = finish(tmp_path, session=[SESSION_HEADER, assistant("toolUse")], rc=2)
    assert r.returncode == 2
    assert error_line(tmp_path) == "AgentError: pi exited with code 2 (stop: toolUse)\n"
    assert summary(tmp_path)["outcome"] == "error"


def test_killed_passes_137_through(tmp_path):
    r = finish(tmp_path, session=[SESSION_HEADER], rc=137)
    assert r.returncode == 137
    assert summary(tmp_path) == {
        "agent": "pi",
        "upstream": UPSTREAM,
        "outcome": "killed",
        "stop_reason": "killed",
        "agent_exit_code": 137,
    }
    assert not (tmp_path / "err").exists()


def test_killed_ignores_the_session(tmp_path):
    r = finish(tmp_path, session=[SESSION_HEADER, assistant("error")], rc=137)
    assert r.returncode == 137
    assert summary(tmp_path)["outcome"] == "killed"
    assert not (tmp_path / "err").exists()


def test_killed_without_a_session(tmp_path):
    r = finish(tmp_path, session=None, rc=137)
    assert r.returncode == 137
    assert not (tmp_path / "err").exists()


def test_last_assistant_message_wins(tmp_path):
    # A failed request that pi retried and the retry succeeded: the run is graded on how it ended.
    entries = [SESSION_HEADER, user(), assistant("error"), user(), assistant("toolUse"), tool_result(), assistant("stop")]
    r = finish(tmp_path, session=entries, rc=0)
    assert r.returncode == 0
    assert summary(tmp_path)["stop_reason"] == "stop"


def test_last_assistant_error_after_earlier_stop_is_an_error(tmp_path):
    r = finish(tmp_path, session=[SESSION_HEADER, assistant("stop"), user(), assistant("error")], rc=1)
    assert r.returncode == 1
    assert error_line(tmp_path) == "AgentError: pi exited with code 1 (stop: error)\n"


def test_entries_after_the_last_assistant_message_are_ignored(tmp_path):
    entries = [
        SESSION_HEADER,
        assistant("length"),
        tool_result(),
        user(),
        {"type": "usage", "id": "ffffffff", "parentId": None, "timestamp": "2026-11-01T14:00:09.000Z", "kind": "x", "usage": {}},
        {"type": "custom", "id": "fffffffe", "parentId": None, "timestamp": "2026-11-01T14:00:10.000Z", "data": {"stopReason": "stop"}},
    ]
    r = finish(tmp_path, session=entries, rc=1)
    assert r.returncode == 0
    assert summary(tmp_path)["stop_reason"] == "length"


def test_only_assistant_messages_carry_a_stop_reason(tmp_path):
    odd = _entry({"role": "toolResult", "toolCallId": "c", "toolName": "bash", "content": [], "stopReason": "length"})
    r = finish(tmp_path, session=[SESSION_HEADER, assistant("error"), odd], rc=1)
    assert r.returncode == 1
    assert error_line(tmp_path) == "AgentError: pi exited with code 1 (stop: error)\n"


def test_newest_session_file_wins(tmp_path):
    # Newest by modification time, not by name: the names sort the other way round.
    older = ("2026-11-01T15-00-00-000Z_old.jsonl", [SESSION_HEADER, assistant("error")], 1_790_000_000)
    newer = ("2026-11-01T13-00-00-000Z_new.jsonl", [SESSION_HEADER, assistant("stop")], 1_790_000_900)
    r = finish(tmp_path, session=[SESSION_HEADER, assistant("length")], rc=0, extra_sessions=[older, newer])
    assert r.returncode == 0
    assert summary(tmp_path)["stop_reason"] == "stop"


def test_session_file_with_spaces_in_its_name(tmp_path):
    spaced = ("a session.jsonl", [SESSION_HEADER, assistant("stop")], 1_790_000_900)
    r = finish(tmp_path, session=[SESSION_HEADER, assistant("error")], rc=0, extra_sessions=[spaced])
    assert r.returncode == 0
    assert summary(tmp_path)["stop_reason"] == "stop"


def test_truncated_last_line_is_ignored(tmp_path):
    """A kill can cut the last line short; the entries before it still count."""
    r = finish(tmp_path, session=[SESSION_HEADER, assistant("error"), '{"type":"message","id":"00000009","mess'], rc=1)
    assert r.returncode == 1
    assert error_line(tmp_path) == "AgentError: pi exited with code 1 (stop: error)\n"


def test_wholly_non_json_session_file(tmp_path):
    r = finish(tmp_path, session=["SECRET PROMPT", "not json at all", "{"], rc=1)
    assert r.returncode == 1
    assert error_line(tmp_path) == "AgentError: pi exited with code 1\n"
    assert summary(tmp_path) == {
        "agent": "pi",
        "upstream": UPSTREAM,
        "outcome": "error",
        "stop_reason": "unknown",
        "agent_exit_code": 1,
    }
    assert "SECRET PROMPT" not in r.stdout + r.stderr + (tmp_path / "out" / "summary.json").read_text()


def test_non_json_session_file_after_a_clean_exit(tmp_path):
    r = finish(tmp_path, session=["not json at all"], rc=0)
    assert r.returncode == 0
    assert summary(tmp_path)["outcome"] == "completed"
    assert summary(tmp_path)["stop_reason"] == "unknown"


def test_session_without_an_assistant_message(tmp_path):
    r = finish(tmp_path, session=[SESSION_HEADER, user()], rc=143)
    assert r.returncode == 143
    assert error_line(tmp_path) == "AgentError: pi exited with code 143\n"
    assert summary(tmp_path)["stop_reason"] == "unknown"


def test_empty_session_file(tmp_path):
    r = finish(tmp_path, session=[], rc=1)
    assert r.returncode == 1
    assert error_line(tmp_path) == "AgentError: pi exited with code 1\n"


def test_stop_reason_is_never_free_text(tmp_path):
    r = finish(tmp_path, session=[SESSION_HEADER, assistant("SECRET PROMPT with spaces")], rc=1)
    assert r.returncode == 1
    assert error_line(tmp_path) == "AgentError: pi exited with code 1\n"
    assert summary(tmp_path)["stop_reason"] == "unknown"
    assert "SECRET PROMPT" not in r.stdout + r.stderr + (tmp_path / "out" / "summary.json").read_text()


def test_an_unusable_last_stop_reason_does_not_fall_back_to_an_earlier_one(tmp_path):
    r = finish(tmp_path, session=[SESSION_HEADER, assistant("length"), assistant({"nested": "SECRET PROMPT"})], rc=1)
    assert r.returncode == 1
    assert error_line(tmp_path) == "AgentError: pi exited with code 1\n"


def test_error_line_is_one_short_line(tmp_path):
    finish(tmp_path, session=[SESSION_HEADER, assistant("E" * 5000)], rc=1)
    line = error_line(tmp_path)
    assert line == "AgentError: pi exited with code 1\n"
    assert len(line) <= 513


def test_without_error_path_still_writes_summary(tmp_path):
    r = finish(tmp_path, session=[SESSION_HEADER, assistant("error")], rc=1, with_error_path=False)
    assert r.returncode == 1
    assert summary(tmp_path)["outcome"] == "error"


def test_exit_code_that_is_not_a_number_counts_as_1(tmp_path):
    r = finish(tmp_path, session=[SESSION_HEADER, assistant("error")], rc="oops")
    assert r.returncode == 1
    assert summary(tmp_path)["agent_exit_code"] == 1
    assert error_line(tmp_path) == "AgentError: pi exited with code 1 (stop: error)\n"


def test_exit_code_above_255_counts_as_1(tmp_path):
    # exit 256 would wrap to 0 and look like success.
    r = finish(tmp_path, session=[SESSION_HEADER, assistant("error")], rc=256)
    assert r.returncode == 1


def test_unreadable_upstream_json_still_exits_with_the_mapped_code(tmp_path):
    r = finish(tmp_path, session=[SESSION_HEADER, assistant("error")], rc=1, upstream_text="{ not json")
    assert r.returncode == 1
    assert error_line(tmp_path) == "AgentError: pi exited with code 1 (stop: error)\n"
    assert summary(tmp_path) == {
        "agent": "pi",
        "upstream": None,
        "outcome": "error",
        "stop_reason": "error",
        "agent_exit_code": 1,
    }


def test_unreadable_upstream_json_keeps_137(tmp_path):
    r = finish(tmp_path, session=[SESSION_HEADER], rc=137, upstream_text="{ not json")
    assert r.returncode == 137
    assert summary(tmp_path)["outcome"] == "killed"
    assert not (tmp_path / "err").exists()


def test_broken_jq_still_exits_with_the_mapped_code(tmp_path):
    missing_jq = {"JQ": str(tmp_path / "no-such-jq")}
    r = finish(tmp_path, session=[SESSION_HEADER, assistant("error")], rc=1, env=missing_jq)
    assert r.returncode == 1
    assert error_line(tmp_path) == "AgentError: pi exited with code 1\n"
    assert summary(tmp_path) == {
        "agent": "pi",
        "upstream": None,
        "outcome": "error",
        "stop_reason": "unknown",
        "agent_exit_code": 1,
    }


def test_broken_jq_keeps_137_and_0(tmp_path):
    missing_jq = {"JQ": str(tmp_path / "no-such-jq")}
    (tmp_path / "killed").mkdir()
    killed = finish(tmp_path / "killed", session=[SESSION_HEADER], rc=137, env=missing_jq)
    assert killed.returncode == 137
    assert summary(tmp_path / "killed")["outcome"] == "killed"
    (tmp_path / "done").mkdir()
    done = finish(tmp_path / "done", session=[SESSION_HEADER, assistant("stop")], rc=0, env=missing_jq)
    assert done.returncode == 0
    assert summary(tmp_path / "done")["outcome"] == "completed"
