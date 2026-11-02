import importlib.util
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

RUN = Path(__file__).resolve().parents[2] / "agents" / "mini_swe_agent" / "run.py"
_spec = importlib.util.spec_from_file_location("mini_swe_agent_run", RUN)
run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run)

OUT = Path("/logs/mini_swe_agent/trajectory.json")


def install_fake_mini(monkeypatch, app):
    """Stand in for ``minisweagent.run.mini`` so no upstream code (or model) is needed."""
    package = types.ModuleType("minisweagent")
    package.__path__ = []
    subpackage = types.ModuleType("minisweagent.run")
    subpackage.__path__ = []
    mini = types.ModuleType("minisweagent.run.mini")
    mini.app = app
    monkeypatch.setitem(sys.modules, "minisweagent", package)
    monkeypatch.setitem(sys.modules, "minisweagent.run", subpackage)
    monkeypatch.setitem(sys.modules, "minisweagent.run.mini", mini)


def option_value(argv, flag):
    return argv[argv.index(flag) + 1]


def test_build_argv_defaults():
    assert run.build_argv(
        "fix it", model="anthropic/m", config="mini.yaml", output=OUT, cost_limit="", step_limit=""
    ) == [
        "-t", "fix it", "-m", "anthropic/m", "-c", "mini.yaml", "-c", "environment.cwd=",
        "--environment-class", "local", "--agent-class", "default", "-y", "--exit-immediately",
        "-o", str(OUT),
    ]  # fmt: skip


def test_build_argv_limits_and_dash_task():
    argv = run.build_argv(
        "--not-a-flag", model="m", config="mini.yaml", output=OUT, cost_limit="3", step_limit="50"
    )
    assert argv[:2] == ["-t", "--not-a-flag"]
    assert argv[-4:] == ["-l", "3", "-c", "agent.step_limit=50"]


def test_build_argv_cost_limit_zero_is_passed():
    argv = run.build_argv("t", model="m", config="mini.yaml", output=OUT, cost_limit="0", step_limit="")
    assert argv[-2:] == ["-l", "0"]


@pytest.mark.parametrize(
    ("status", "code", "outcome"),
    [("Submitted", 0, "completed"), ("LimitsExceeded", 0, "completed"), ("AuthenticationError", 1, "error")],
)
def test_summarize(tmp_path, status, code, outcome):
    (tmp_path / "t.json").write_text(json.dumps({"info": {"exit_status": status}}))
    assert run.summarize(tmp_path / "t.json", {"repo": "r"}, code) == {
        "agent": "mini_swe_agent",
        "upstream": {"repo": "r"},
        "outcome": outcome,
        "stop_reason": status,
        "agent_exit_code": code,
    }


def test_summarize_missing_trajectory(tmp_path):
    assert run.summarize(tmp_path / "none.json", {}, 1)["stop_reason"] == "no trajectory"


@pytest.mark.parametrize("content", ["not json", "[]", '{"info": []}', '{"info": {"exit_status": 3}}'])
def test_summarize_unreadable_trajectory(tmp_path, content):
    (tmp_path / "t.json").write_text(content)
    assert run.summarize(tmp_path / "t.json", {}, 0)["stop_reason"] == "no trajectory"


def test_write_error_is_a_noop_without_path(monkeypatch):
    monkeypatch.delenv("VALKYRIE_ERROR_PATH", raising=False)
    run.write_error("AgentError: anything")  # must not raise


def test_write_error_truncates_to_one_line_of_512_chars(tmp_path, monkeypatch):
    monkeypatch.setenv("VALKYRIE_ERROR_PATH", str(tmp_path / "err"))
    run.write_error("AgentError: " + "x\n" * 600)
    text = (tmp_path / "err").read_text()
    assert text.endswith("\n")
    assert text.count("\n") == 1
    assert len(text.rstrip("\n")) <= 512


@pytest.fixture
def mini_env(tmp_path, monkeypatch):
    """Isolate the process state ``main`` changes (argv, the MSWEA_* variables) and the upstream.json it records."""
    monkeypatch.setattr(sys, "argv", list(sys.argv))
    for name in ("MSWEA_CONFIGURED", "MSWEA_SILENT_STARTUP", "MSWEA_COST_TRACKING"):
        monkeypatch.setenv(name, "before")
        monkeypatch.delenv(name)
    monkeypatch.setenv("VALKYRIE_ERROR_PATH", str(tmp_path / "err"))
    problem = tmp_path / "p.md"
    problem.write_text("SECRET TASK TEXT")
    upstream = tmp_path / "upstream.json"
    upstream.write_text(json.dumps({"repo": "o/r", "tag": "v9"}))
    monkeypatch.setattr(run, "UPSTREAM", upstream)
    return types.SimpleNamespace(
        problem=problem,
        out=tmp_path / "out",
        err=tmp_path / "err",
        base=[str(problem), "--model", "m", "--output-dir", str(tmp_path / "out")],
    )


def fake_app(status, code, calls=None, *, write=True):
    def app():
        argv = list(sys.argv)
        if calls is not None:
            calls.append({"argv": argv, "env": dict(os.environ)})
        if write:
            output = Path(option_value(argv, "-o"))
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps({"info": {"exit_status": status}}))
        raise SystemExit(code)

    return app


def test_main_failure_writes_error_without_task_text(mini_env, monkeypatch):
    install_fake_mini(monkeypatch, fake_app("AuthenticationError", 1))
    assert run.main(mini_env.base) == 1
    assert mini_env.err.read_text() == "AgentError: mini-swe-agent exited with code 1 (AuthenticationError)\n"
    assert "SECRET" not in mini_env.err.read_text()
    summary = json.loads((mini_env.out / "summary.json").read_text())
    assert summary == {
        "agent": "mini_swe_agent",
        "upstream": {"repo": "o/r", "tag": "v9"},
        "outcome": "error",
        "stop_reason": "AuthenticationError",
        "agent_exit_code": 1,
    }


def test_main_success_passes_task_and_sets_env(mini_env, monkeypatch):
    calls = []
    install_fake_mini(monkeypatch, fake_app("Submitted", 0, calls))
    argv = [*mini_env.base, "--cost-limit", "2", "--step-limit", "40", "--cost-tracking", "ignore_errors"]
    assert run.main(argv) == 0
    (call,) = calls
    assert call["argv"][0] == "mini"
    assert option_value(call["argv"], "-t") == "SECRET TASK TEXT"
    assert option_value(call["argv"], "-m") == "m"
    assert option_value(call["argv"], "-c") == "mini.yaml"
    assert option_value(call["argv"], "-o") == str(mini_env.out / "trajectory.json")
    assert option_value(call["argv"], "-l") == "2"
    assert call["argv"][-2:] == ["-c", "agent.step_limit=40"]
    assert call["env"]["MSWEA_CONFIGURED"] == "true"
    assert call["env"]["MSWEA_SILENT_STARTUP"] == "1"
    assert call["env"]["MSWEA_COST_TRACKING"] == "ignore_errors"
    assert not mini_env.err.exists()
    summary = json.loads((mini_env.out / "summary.json").read_text())
    assert (summary["outcome"], summary["stop_reason"], summary["agent_exit_code"]) == ("completed", "Submitted", 0)


def test_main_empty_options_are_omitted(mini_env, monkeypatch):
    calls = []
    install_fake_mini(monkeypatch, fake_app("Submitted", 0, calls))
    argv = [*mini_env.base, "--cost-limit", "", "--step-limit", "", "--cost-tracking", ""]
    assert run.main(argv) == 0
    (call,) = calls
    assert "-l" not in call["argv"]
    assert not any(part.startswith("agent.step_limit") for part in call["argv"])
    assert "MSWEA_COST_TRACKING" not in call["env"]


def test_main_reports_a_limit_stop_as_completed(mini_env, monkeypatch):
    install_fake_mini(monkeypatch, fake_app("LimitsExceeded", 0))
    assert run.main(mini_env.base) == 0
    assert json.loads((mini_env.out / "summary.json").read_text())["outcome"] == "completed"
    assert not mini_env.err.exists()


def test_main_uncaught_exception_still_writes_summary_and_error(mini_env, monkeypatch):
    def app():
        output = Path(option_value(sys.argv, "-o"))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"info": {"exit_status": "RuntimeError"}}))
        raise RuntimeError("SECRET MODEL TEXT")

    install_fake_mini(monkeypatch, app)
    assert run.main(mini_env.base) == 1
    assert mini_env.err.read_text() == "AgentError: mini-swe-agent exited with code 1 (RuntimeError)\n"
    summary = json.loads((mini_env.out / "summary.json").read_text())
    assert (summary["outcome"], summary["agent_exit_code"]) == ("error", 1)


def test_main_ignores_a_stale_trajectory(mini_env, monkeypatch):
    mini_env.out.mkdir()
    (mini_env.out / "trajectory.json").write_text(json.dumps({"info": {"exit_status": "Submitted"}}))
    install_fake_mini(monkeypatch, fake_app("", 1, write=False))
    assert run.main(mini_env.base) == 1
    assert json.loads((mini_env.out / "summary.json").read_text())["stop_reason"] == "no trajectory"
    assert mini_env.err.read_text() == "AgentError: mini-swe-agent exited with code 1 (no trajectory)\n"


def test_main_unreadable_problem_writes_summary_and_error(mini_env, monkeypatch):
    install_fake_mini(monkeypatch, fake_app("Submitted", 0))
    argv = ["/nonexistent/problem.md", *mini_env.base[1:]]
    assert run.main(argv) == 1
    assert mini_env.err.read_text() == "AgentError: cannot read the problem statement\n"
    assert json.loads((mini_env.out / "summary.json").read_text())["outcome"] == "error"


def test_main_defaults_to_the_logs_directory():
    args = run.parse_args(["p.md", "--model", "m"])
    assert args.output_dir == "/logs/mini_swe_agent"
    assert args.config == "mini.yaml"


def test_main_error_line_never_echoes_a_free_text_status(mini_env, monkeypatch):
    install_fake_mini(monkeypatch, fake_app("some free text from somewhere", 1))
    assert run.main(mini_env.base) == 1
    assert mini_env.err.read_text() == "AgentError: mini-swe-agent exited with code 1 (unknown)\n"


TASK_UTF8 = "Fix the café menu: naïve → résumé ✓"


def test_main_passes_a_non_ascii_task_through(mini_env, monkeypatch):
    mini_env.problem.write_text(TASK_UTF8, encoding="utf-8")
    calls = []
    install_fake_mini(monkeypatch, fake_app("Submitted", 0, calls))
    assert run.main(mini_env.base) == 0
    assert option_value(calls[0]["argv"], "-t") == TASK_UTF8


def test_main_reads_the_task_as_utf8_whatever_the_locale(tmp_path):
    """The entry script runs Python with -E, so PYTHONUTF8 cannot help: a Latin-1 locale must not matter."""
    env = {**os.environ, "LC_ALL": "en_US.ISO8859-1", "LANG": "en_US.ISO8859-1"}
    env.pop("PYTHONUTF8", None)
    probe = [sys.executable, "-E", "-X", "utf8=0", "-c", "import locale; print(locale.getencoding())"]
    encoding = subprocess.run(probe, env=env, capture_output=True, text=True, check=True).stdout.strip()
    if encoding.lower().replace("-", "") == "utf8":
        pytest.skip("no Latin-1 locale on this machine, so the default encoding is UTF-8 anyway")

    problem = tmp_path / "p.md"
    problem.write_text(TASK_UTF8, encoding="utf-8")
    seen = tmp_path / "seen.txt"
    code = f"""
import importlib.util, sys, types
spec = importlib.util.spec_from_file_location("run", {str(RUN)!r})
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)
def app():
    open({str(seen)!r}, "w", encoding="utf-8").write(sys.argv[sys.argv.index("-t") + 1])
    raise SystemExit(0)
mini = types.ModuleType("minisweagent.run.mini")
mini.app = app
for name in ("minisweagent", "minisweagent.run"):
    sys.modules[name] = types.ModuleType(name)
sys.modules["minisweagent.run.mini"] = mini
sys.exit(run.main([{str(problem)!r}, "--model", "m", "--output-dir", {str(tmp_path / "out")!r}]))
"""
    result = subprocess.run([sys.executable, "-E", "-X", "utf8=0", "-c", code], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert seen.read_text(encoding="utf-8") == TASK_UTF8
