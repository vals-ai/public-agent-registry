"""Tests for agents/terminus2/terminus2_bridge.py, which imports Harbor, and run_terminus2.main with it.

Run with ``uv run --with ./agents/terminus2/harbor pytest tests/agents/test_terminus2_local_env.py``.
A plain ``uv run pytest`` skips this file because Harbor is not installed there.
"""

import asyncio
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

import pytest

pytest.importorskip("harbor")

from harbor.agents.agent_auth_resolution import PROVIDERS  # noqa: E402
from harbor.environments.base import ExecResult  # noqa: E402
from harbor.environments.capabilities import EnvironmentCapabilities  # noqa: E402

AGENT_DIR = Path(__file__).resolve().parents[2] / "agents" / "terminus2"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


support = _load("terminus2_support", AGENT_DIR / "terminus2_support.py")
bridge = _load("terminus2_bridge", AGENT_DIR / "terminus2_bridge.py")
runner = _load("run_terminus2", AGENT_DIR / "run_terminus2.py")
LocalEnvironment = bridge.LocalEnvironment


def make_env(tmp_path: Path, key_names=()) -> "LocalEnvironment":
    return LocalEnvironment(cwd=tmp_path, out_dir=tmp_path / "out", key_names=key_names)


# --- LocalEnvironment -------------------------------------------------------------------------


async def test_exec_runs_in_cwd(tmp_path):
    env = make_env(tmp_path)
    result = await env.exec("pwd")
    assert result.return_code == 0 and result.stdout.strip() == str(tmp_path)


async def test_exec_hides_provider_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    env = make_env(tmp_path, key_names=["ANTHROPIC_API_KEY"])
    assert (await env.exec("printenv ANTHROPIC_API_KEY")).return_code == 1


async def test_exec_hides_listed_names_and_any_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/creds.json")
    monkeypatch.setenv("SOME_VENDOR_API_KEY", "k")
    monkeypatch.setenv("TERMINUS2_TEST_KEPT", "kept")
    env = make_env(tmp_path, key_names=["GOOGLE_APPLICATION_CREDENTIALS"])
    result = await env.exec("env")
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in result.stdout
    assert "SOME_VENDOR_API_KEY" not in result.stdout
    assert "TERMINUS2_TEST_KEPT=kept" in result.stdout


async def test_exec_takes_cwd_and_env_arguments(tmp_path):
    (tmp_path / "sub").mkdir()
    env = make_env(tmp_path)
    result = await env.exec('pwd; printf %s "$EXTRA"', cwd=str(tmp_path / "sub"), env={"EXTRA": "x y"})
    assert result.stdout == f"{tmp_path / 'sub'}\nx y"


async def test_exec_keeps_stdout_and_stderr_apart(tmp_path):
    env = make_env(tmp_path)
    result = await env.exec("echo out; echo err >&2; exit 3")
    assert (result.stdout, result.stderr, result.return_code) == ("out\n", "err\n", 3)
    quiet = await env.exec("true")
    assert (quiet.stdout, quiet.stderr, quiet.return_code) == (None, None, 0)


async def test_exec_uses_bash_and_ignores_user(tmp_path):
    env = make_env(tmp_path)
    result = await env.exec("[[ 1 == 1 ]] && id -u", user="nobody")
    assert result.return_code == 0
    assert result.stdout.strip() == str(os.getuid())


async def test_exec_has_no_stdin(tmp_path):
    env = make_env(tmp_path)
    result = await env.exec("cat", timeout_sec=5)
    assert result.return_code == 0 and result.stdout is None


async def test_exec_timeout_matches_docker_environment(tmp_path):
    # DockerEnvironment._collect_buffered_output at v0.25.0: when timeout_sec is set and passes,
    # the process is terminated and RuntimeError("Command timed out after N seconds") is raised.
    env = make_env(tmp_path)
    started = time.monotonic()
    with pytest.raises(RuntimeError, match=r"^Command timed out after 1 seconds$"):
        await env.exec("sleep 5", timeout_sec=1)
    assert time.monotonic() - started < 4


async def test_exec_timeout_kills_the_whole_command(tmp_path):
    env = make_env(tmp_path)
    with pytest.raises(RuntimeError):
        await env.exec("(sleep 2; touch late) & wait", timeout_sec=1)
    await asyncio.sleep(2.5)
    assert not (tmp_path / "late").exists()


async def test_exec_zero_or_no_timeout_waits(tmp_path):
    env = make_env(tmp_path)
    assert (await env.exec("sleep 0.2; echo done", timeout_sec=0)).stdout == "done\n"
    assert (await env.exec("sleep 0.2; echo done", timeout_sec=None)).stdout == "done\n"


async def test_download_onto_same_path_is_noop(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    env = make_env(tmp_path)
    await env.download_file(f, f)
    await env.upload_file(f, str(f))
    assert f.read_text() == "x"


async def test_file_copies_create_parent_folders(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("x")
    env = make_env(tmp_path)
    await env.upload_file(src, str(tmp_path / "up" / "b.txt"))
    await env.download_file(str(src), tmp_path / "down" / "c.txt")
    assert (tmp_path / "up" / "b.txt").read_text() == "x"
    assert (tmp_path / "down" / "c.txt").read_text() == "x"


async def test_dir_copies_merge_contents_into_target(tmp_path):
    src = tmp_path / "src"
    (src / "inner").mkdir(parents=True)
    (src / "inner" / "f.txt").write_text("new")
    target = tmp_path / "target"
    (target / "inner").mkdir(parents=True)
    (target / "inner" / "f.txt").write_text("old")
    (target / "keep.txt").write_text("keep")
    env = make_env(tmp_path)
    await env.upload_dir(src, str(target))
    assert (target / "inner" / "f.txt").read_text() == "new"
    assert (target / "keep.txt").read_text() == "keep"
    await env.download_dir(str(src), tmp_path / "down")
    assert (tmp_path / "down" / "inner" / "f.txt").read_text() == "new"
    await env.download_dir(str(src), src)
    assert (src / "inner" / "f.txt").read_text() == "new"


async def test_lifecycle_and_description(tmp_path):
    env = make_env(tmp_path)
    await env.start(force_build=True)
    await env.stop(delete=True)
    assert env.capabilities == EnvironmentCapabilities()
    assert env.trial_paths.agent_dir == tmp_path / "out"
    assert env.default_user is None
    assert LocalEnvironment.type() == "local"


def test_default_output_dir_is_harbors_agent_dir():
    env = LocalEnvironment(cwd=Path("/"), out_dir=Path("/logs/agent"), key_names=[])
    assert env.trial_paths.agent_dir == Path("/logs/agent")


def test_provider_env_names_are_every_name_in_harbors_table():
    expected = set()
    for access in PROVIDERS.values():
        expected.update(access.api_key_candidate_names)
        expected.update(access.base_url_candidate_names)
        expected.update(access.extra_env_names)
    names = bridge.provider_env_names()
    assert set(names) == expected
    assert {"ANTHROPIC_API_KEY", "OPENAI_BASE_URL", "AWS_SECRET_ACCESS_KEY", "GOOGLE_APPLICATION_CREDENTIALS"} <= set(
        names
    )


# --- run() and main() with a stand-in agent --------------------------------------------------


def fake_agent_class(*, setup_error=None, run_error=None, metrics=None):
    """A stand-in for Terminus2 that records what the wrapper does with it."""

    class FakeAgent:
        calls: list = []
        instances: list = []

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            FakeAgent.instances.append(self)

        @staticmethod
        def name():
            return "terminus-2"

        async def setup(self, environment):
            FakeAgent.calls.append(("setup", environment))
            if setup_error is not None:
                raise setup_error

        async def run(self, instruction, environment, context):
            FakeAgent.calls.append(("run", instruction, environment))
            for key, value in (metrics or {}).items():
                setattr(context, key, value)
            if run_error is not None:
                raise run_error

    return FakeAgent


class AuthenticationError(Exception):
    pass


@pytest.fixture
def case(tmp_path, monkeypatch):
    """A task folder to run in, a problem file, and a LocalEnvironment.exec that records commands.

    ``use_agent`` swaps in a stand-in agent class whose ``calls`` list then also gets the
    recorded exec commands, so the order of setup, exec and run can be checked.
    """
    task = tmp_path / "task dir 'q'"
    task.mkdir()
    monkeypatch.chdir(task)
    monkeypatch.setenv("VALKYRIE_ERROR_PATH", str(tmp_path / "err"))
    problem = tmp_path / "problem.md"
    problem.write_text("-x 'single' \"double\"\nSECRET TASK TEXT\n")
    calls = []
    state = {"exec_code": 0}

    async def fake_exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        calls.append(("exec", command))
        return ExecResult(return_code=state["exec_code"])

    monkeypatch.setattr(LocalEnvironment, "exec", fake_exec)

    def use_agent(agent_class):
        monkeypatch.setattr(bridge, "Terminus2", agent_class)
        agent_class.calls = calls
        return agent_class

    return types.SimpleNamespace(
        task=task,
        problem=problem,
        out=tmp_path / "out",
        err=tmp_path / "err",
        state=state,
        upstream={"repo": "harbor-framework/harbor", "tag": "v0.25.0"},
        use_agent=use_agent,
    )


def summary(out: Path) -> dict:
    return json.loads((out / "summary.json").read_text())


async def test_run_follows_harbors_trial_order(case):
    agent = case.use_agent(fake_agent_class())
    code = await bridge.run(case.problem, "anthropic/m", {"max_turns": 5}, case.out, case.upstream)
    assert code == 0
    (instance,) = agent.instances
    assert instance.kwargs == {
        "logs_dir": case.out,
        "model_name": "anthropic/m",
        "record_terminal_session": False,
        "max_turns": 5,
    }
    cd = shlex.join(["tmux", "send-keys", "-t", "terminus-2", f"cd {shlex.quote(str(case.task))}", "Enter"])
    assert [call[0] for call in agent.calls] == ["setup", "exec", "run"]
    assert agent.calls[1] == ("exec", cd)
    setup_env, run_env = agent.calls[0][1], agent.calls[2][2]
    assert setup_env is run_env
    assert isinstance(setup_env, LocalEnvironment)
    assert setup_env.trial_paths.agent_dir == case.out
    assert agent.calls[2][1] == case.problem.read_text()


async def test_run_success_writes_summary_with_metrics(case):
    metrics = {
        "n_input_tokens": 120,
        "n_output_tokens": 30,
        "n_cache_tokens": 100,
        "cost_usd": 0.25,
        "metadata": {"n_episodes": 4, "api_request_times_msec": [1.5], "summarization_count": 0},
    }
    case.use_agent(fake_agent_class(metrics=metrics))
    assert await bridge.run(case.problem, "m", {}, case.out, case.upstream) == 0
    assert summary(case.out) == {
        "agent": "terminus2",
        "upstream": case.upstream,
        "outcome": "completed",
        "stop_reason": "returned",
        "agent_exit_code": 0,
        "metrics": metrics,
    }
    assert not case.err.exists()


async def test_run_error_in_setup(case):
    agent = case.use_agent(fake_agent_class(setup_error=RuntimeError("SECRET TASK TEXT")))
    assert await bridge.run(case.problem, "m", {}, case.out, case.upstream) == 1
    assert case.err.read_text() == "AgentError: terminus2 RuntimeError\n"
    assert [call[0] for call in agent.calls] == ["setup"]
    assert summary(case.out) == {
        "agent": "terminus2",
        "upstream": case.upstream,
        "outcome": "error",
        "stop_reason": "RuntimeError",
        "agent_exit_code": 1,
        "metrics": {
            "n_input_tokens": None,
            "n_output_tokens": None,
            "n_cache_tokens": None,
            "cost_usd": None,
            "metadata": None,
        },
    }


async def test_run_error_in_run_keeps_metrics_and_hides_text(case):
    case.use_agent(fake_agent_class(run_error=AuthenticationError("SECRET model said"), metrics={"n_input_tokens": 9}))
    assert await bridge.run(case.problem, "m", {}, case.out, case.upstream) == 1
    assert case.err.read_text() == "AgentError: terminus2 AuthenticationError\n"
    result = summary(case.out)
    assert (result["outcome"], result["stop_reason"]) == ("error", "AuthenticationError")
    assert result["metrics"]["n_input_tokens"] == 9
    assert "SECRET" not in (case.out / "summary.json").read_text()


async def test_run_error_when_cd_fails(case):
    agent = case.use_agent(fake_agent_class())
    case.state["exec_code"] = 1
    assert await bridge.run(case.problem, "m", {}, case.out, case.upstream) == 1
    assert case.err.read_text() == "AgentError: terminus2 RuntimeError\n"
    assert [call[0] for call in agent.calls] == ["setup", "exec"]


async def test_run_error_when_constructor_rejects_options(case):
    class Rejecting(fake_agent_class()):
        def __init__(self, **kwargs):
            raise ValueError("bad option")

    agent = case.use_agent(Rejecting)
    assert await bridge.run(case.problem, "m", {}, case.out, case.upstream) == 1
    assert case.err.read_text() == "AgentError: terminus2 ValueError\n"
    assert agent.calls == []


async def test_run_error_when_problem_is_unreadable(case):
    agent = case.use_agent(fake_agent_class())
    assert await bridge.run(case.problem.with_name("missing.md"), "m", {}, case.out, case.upstream) == 1
    assert case.err.read_text() == "AgentError: terminus2 FileNotFoundError\n"
    assert agent.calls == []


@pytest.mark.parametrize("setup_error", [None, RuntimeError("x")])
async def test_run_summary_failure_keeps_code_and_error_line(case, capsys, setup_error):
    case.use_agent(fake_agent_class(setup_error=setup_error))
    case.out.write_text("a file where the output folder should be")
    code = await bridge.run(case.problem, "m", {}, case.out, case.upstream)
    if setup_error is None:
        assert code == 0
        assert not case.err.exists()
    else:
        assert code == 1
        assert case.err.read_text() == "AgentError: terminus2 RuntimeError\n"
    assert "could not write" in capsys.readouterr().err


def main_argv(case, **flags):
    values = {"max_turns": "", "temperature": "", "parser": "", "reasoning_effort": "", **flags}
    upstream = case.out.parent / "upstream.json"
    upstream.write_text(json.dumps(case.upstream))
    return [
        str(case.problem),
        "--model", "anthropic/m",
        "--max-turns", values["max_turns"],
        "--temperature", values["temperature"],
        "--parser", values["parser"],
        "--reasoning-effort", values["reasoning_effort"],
        "--output-dir", str(case.out),
        "--upstream", str(upstream),
    ]  # fmt: skip


def test_main_empty_kwargs_keep_upstream_defaults(case):
    agent = case.use_agent(fake_agent_class())
    assert runner.main(main_argv(case)) == 0
    assert agent.instances[0].kwargs == {
        "logs_dir": case.out,
        "model_name": "anthropic/m",
        "record_terminal_session": False,
    }
    assert summary(case.out)["upstream"] == case.upstream


def test_main_passes_typed_options(case):
    agent = case.use_agent(fake_agent_class())
    argv = main_argv(case, max_turns="40", temperature="0.2", parser="xml", reasoning_effort="high")
    assert runner.main(argv) == 0
    assert agent.instances[0].kwargs == {
        "logs_dir": case.out,
        "model_name": "anthropic/m",
        "record_terminal_session": False,
        "max_turns": 40,
        "temperature": 0.2,
        "parser_name": "xml",
        "reasoning_effort": "high",
    }


def test_main_bad_option_is_an_error(case):
    agent = case.use_agent(fake_agent_class())
    assert runner.main(main_argv(case, max_turns="lots")) == 1
    assert case.err.read_text() == "AgentError: terminus2 max_turns must be an integer\n"
    assert agent.instances == []
    result = summary(case.out)
    assert (result["outcome"], result["stop_reason"], result["agent_exit_code"]) == ("error", "invalid_options", 1)


def test_main_default_upstream_is_the_shipped_file():
    args = runner.parse_args(["p", "--model", "m"])
    assert Path(args.upstream) == AGENT_DIR / "upstream.json"
    assert args.output_dir == "/logs/agent"
    assert (args.max_turns, args.temperature, args.parser, args.reasoning_effort) == ("", "", "", "")


# --- the real Terminus2 and tmux, without a model ---------------------------------------------


@pytest.fixture
def private_tmux(monkeypatch):
    """Point tmux at a private socket folder so no tmux server of the user's is touched."""
    if shutil.which("tmux") is None:
        pytest.skip("needs tmux")
    socket_dir = tempfile.mkdtemp(prefix="t2-")  # short: tmux socket paths are length-limited
    monkeypatch.setenv("TMUX_TMPDIR", socket_dir)
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)
    yield
    subprocess.run(["tmux", "kill-server"], env={**os.environ, "TMUX_TMPDIR": socket_dir}, capture_output=True)
    shutil.rmtree(socket_dir, ignore_errors=True)


async def test_real_session_starts_in_task_dir_without_keys(tmp_path, monkeypatch, private_tmux):
    """Harbor's own Terminus2.setup and TmuxSession on LocalEnvironment, with run() replaced."""
    task = tmp_path / "task dir"
    task.mkdir()
    monkeypatch.chdir(task)
    # A login profile that leaves the shell elsewhere, as an image's profile may: only the wrapper's
    # cd brings the shell back to the task folder.
    home = tmp_path / "home"
    home.mkdir()
    (home / ".bash_profile").write_text('cd "$HOME"\n')
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-SECRET-1")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "SECRET-2.json")
    monkeypatch.setenv("VALKYRIE_ERROR_PATH", str(tmp_path / "err"))
    problem = tmp_path / "p.md"
    problem.write_text("say hi")
    where, seen_env = tmp_path / "where.txt", tmp_path / "env.txt"

    async def fake_run(self, instruction, environment, context):
        keys = f"pwd > {shlex.quote(str(where))}; env > {shlex.quote(str(seen_env))}.tmp; mv {shlex.quote(str(seen_env))}.tmp {shlex.quote(str(seen_env))}"
        result = await environment.exec(shlex.join(["tmux", "send-keys", "-t", self.name(), keys, "Enter"]))
        assert result.return_code == 0
        for _ in range(100):
            if seen_env.exists():
                break
            await asyncio.sleep(0.1)
        context.n_input_tokens = 1

    monkeypatch.setattr(bridge.Terminus2, "run", fake_run)
    code = await bridge.run(problem, "anthropic/claude-sonnet-4-6", {}, tmp_path / "out", {})
    assert code == 0, (tmp_path / "err").read_text() if (tmp_path / "err").exists() else ""
    assert where.read_text().strip() == str(task)
    assert "SECRET" not in seen_env.read_text()
    assert summary(tmp_path / "out")["metrics"]["n_input_tokens"] == 1
