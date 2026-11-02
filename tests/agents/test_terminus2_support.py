import importlib.util
import json
from pathlib import Path

import pytest

AGENT_DIR = Path(__file__).resolve().parents[2] / "agents" / "terminus2"
_spec = importlib.util.spec_from_file_location("terminus2_support", AGENT_DIR / "terminus2_support.py")
support = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(support)


def test_scrubbed_env_drops_listed_and_api_key_names():
    env = {
        "PATH": "/bin",
        "ANTHROPIC_API_KEY": "k",
        "CUSTOM_API_KEY": "k",
        "GOOGLE_APPLICATION_CREDENTIALS": "f",
        "HOME": "/root",
    }
    assert support.scrubbed_env(env, ["GOOGLE_APPLICATION_CREDENTIALS"]) == {"PATH": "/bin", "HOME": "/root"}


def test_scrubbed_env_keeps_lookalike_names_and_copies():
    env = {"API_KEY_PATH": "/x", "MY_API_KEYS": "y", "OPENAI_BASE_URL": "u"}
    result = support.scrubbed_env(env, ["OPENAI_BASE_URL"])
    assert result == {"API_KEY_PATH": "/x", "MY_API_KEYS": "y"}
    result["NEW"] = "1"
    assert "NEW" not in env


def test_parse_options_drops_empty_values():
    assert support.parse_options(max_turns="", temperature="", parser="", reasoning_effort="") == {}


def test_parse_options_maps_and_types():
    assert support.parse_options(max_turns="40", temperature="0.2", parser="xml", reasoning_effort="high") == {
        "max_turns": 40,
        "temperature": 0.2,
        "parser_name": "xml",
        "reasoning_effort": "high",
    }


def test_parse_options_passes_only_what_is_set():
    assert support.parse_options(max_turns="", temperature="0", parser="", reasoning_effort="") == {"temperature": 0.0}


@pytest.mark.parametrize(
    ("kwargs", "option"),
    [
        ({"max_turns": "ten"}, "max_turns"),
        ({"max_turns": "2.5"}, "max_turns"),
        ({"temperature": "warm"}, "temperature"),
    ],
)
def test_parse_options_rejects_bad_numbers(kwargs, option):
    values = {"max_turns": "", "temperature": "", "parser": "", "reasoning_effort": "", **kwargs}
    with pytest.raises(ValueError, match=option) as error:
        support.parse_options(**values)
    assert kwargs[option] not in str(error.value)


def read_summary(out_dir: Path) -> dict:
    return json.loads((out_dir / "summary.json").read_text())


def test_write_summary_shape(tmp_path):
    metrics = {
        "n_input_tokens": 10,
        "n_output_tokens": 2,
        "n_cache_tokens": 0,
        "cost_usd": 0.5,
        "metadata": {"n_episodes": 3},
    }
    support.write_summary(
        tmp_path / "out",
        {"repo": "harbor-framework/harbor", "tag": "v0.25.0"},
        outcome="completed",
        stop_reason="returned",
        agent_exit_code=0,
        metrics=metrics,
    )
    assert read_summary(tmp_path / "out") == {
        "agent": "terminus2",
        "upstream": {"repo": "harbor-framework/harbor", "tag": "v0.25.0"},
        "outcome": "completed",
        "stop_reason": "returned",
        "agent_exit_code": 0,
        "metrics": metrics,
    }
    assert [p.name for p in (tmp_path / "out").iterdir()] == ["summary.json"]


def test_write_summary_replaces_an_old_summary(tmp_path):
    (tmp_path / "summary.json").write_text("old")
    support.write_summary(tmp_path, {}, outcome="error", stop_reason="X", agent_exit_code=1, metrics={})
    assert read_summary(tmp_path)["outcome"] == "error"


def test_write_summary_stringifies_values_json_cannot_hold(tmp_path):
    support.write_summary(
        tmp_path,
        {},
        outcome="completed",
        stop_reason="returned",
        agent_exit_code=0,
        metrics={"metadata": {"p": Path("/x")}},
    )
    assert read_summary(tmp_path)["metrics"] == {"metadata": {"p": "/x"}}


def test_write_summary_failure_is_reported_not_raised(tmp_path, capsys):
    blocker = tmp_path / "file"
    blocker.write_text("")
    support.write_summary(blocker, {}, outcome="error", stop_reason="X", agent_exit_code=1, metrics={})
    assert "could not write" in capsys.readouterr().err


def test_write_error_is_a_noop_without_path(monkeypatch):
    monkeypatch.delenv("VALKYRIE_ERROR_PATH", raising=False)
    support.write_error("AgentError: anything")  # must not raise


def test_write_error_truncates_to_one_line_of_512_chars(tmp_path, monkeypatch):
    monkeypatch.setenv("VALKYRIE_ERROR_PATH", str(tmp_path / "err"))
    support.write_error("AgentError: " + "x\n" * 600)
    text = (tmp_path / "err").read_text()
    assert text.endswith("\n")
    assert text.count("\n") == 1
    assert len(text.rstrip("\n")) <= 512


def test_write_error_failure_is_reported_not_raised(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("VALKYRIE_ERROR_PATH", str(tmp_path / "missing" / "err"))
    support.write_error("AgentError: x")
    assert "could not write" in capsys.readouterr().err


def test_load_upstream(tmp_path):
    (tmp_path / "u.json").write_text('{"repo": "o/r"}')
    (tmp_path / "list.json").write_text("[]")
    (tmp_path / "bad.json").write_text("{")
    assert support.load_upstream(tmp_path / "u.json") == {"repo": "o/r"}
    assert support.load_upstream(tmp_path / "list.json") == {}
    assert support.load_upstream(tmp_path / "bad.json") == {}
    assert support.load_upstream(tmp_path / "none.json") == {}


def test_the_shipped_upstream_json_loads():
    upstream = support.load_upstream(AGENT_DIR / "upstream.json")
    assert upstream["repo"] == "harbor-framework/harbor"
    assert upstream["submodule"] == "harbor"
