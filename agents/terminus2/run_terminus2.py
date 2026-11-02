#!/usr/bin/env python3
"""Run Harbor's Terminus 2 on one problem statement and write summary.json.

Usage: run_terminus2.py PROBLEM --model M [--max-turns N] [--temperature T] [--parser json|xml]
                        [--reasoning-effort E] [--output-dir D]

PROBLEM is the path of a file holding the task. Empty option values keep upstream's defaults.

Harbor runs Terminus 2 outside the task container and drives a tmux session inside it through an
environment object. Valkyrie runs this script inside the task container, and none of Harbor's
environment types runs commands on the current machine, so ``LocalEnvironment`` below is that
bridge: its ``exec`` runs bash here, and its uploads and downloads are local copies. ``run`` then
calls Terminus 2 in the order Harbor's ``trial.py`` does (construct, ``setup``, ``run``), with one
step added: after ``setup`` it types ``cd <task folder>`` into the tmux session, because the login
shell tmux starts need not begin there. Harbor itself is not modified. This uses Harbor internals
that are not documented as public API, pinned at the tag in upstream.json.

Outputs: Terminus 2 writes ``trajectory.json`` to the output directory (default /logs/agent, which
is also where Harbor writes the tmux pane log, ``terminus_2.pane``). This script adds
``summary.json`` there, always, even when the run fails.

Exit code: 0 when ``run`` returns (the task was confirmed complete, ``max_turns`` was reached, or
the tmux session ended). Otherwise 1, with ``AgentError: terminus2 <ExceptionClass>`` in
$VALKYRIE_ERROR_PATH. That line holds only the exception's class name, never task or model text.
"""

import argparse
import asyncio
import os
import shlex
import shutil
import signal
import sys
import traceback
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from harbor.agents.agent_auth_resolution import PROVIDERS
from harbor.agents.terminus_2.terminus_2 import Terminus2
from harbor.environments.base import BaseEnvironment, ExecResult
from harbor.environments.capabilities import EnvironmentCapabilities
from harbor.models.agent.context import AgentContext
from harbor.models.task.config import EnvironmentConfig
from harbor.models.trial.paths import TrialPaths
from terminus2_support import load_upstream, parse_options, scrubbed_env, write_error, write_summary

DEFAULT_OUTPUT_DIR = "/logs/agent"
# DockerEnvironment._terminate_process waits this long after SIGTERM before SIGKILL.
KILL_GRACE_SEC = 5


def provider_env_names() -> list[str]:
    """Every environment variable name in Harbor's provider table: keys, base URLs and the rest."""
    names: set[str] = set()
    for access in PROVIDERS.values():
        names.update(access.api_key_candidate_names, access.base_url_candidate_names, access.extra_env_names)
    return sorted(names)


@dataclass(frozen=True)
class _OutputPaths(TrialPaths):
    """TrialPaths whose ``agent_dir`` is the output directory itself, not ``<trial_dir>/agent``."""

    @property
    def agent_dir(self) -> Path:
        return self.trial_dir


def _same_path(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _copy_file(source: Path | str, target: Path | str) -> None:
    source, target = Path(source), Path(target)
    if _same_path(source, target):
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _copy_dir(source: Path | str, target: Path | str) -> None:
    """Copy the contents of ``source`` into ``target``, overwriting files, like ``docker cp src/. dst``."""
    source, target = Path(source), Path(target)
    if _same_path(source, target):
        return
    shutil.copytree(source, target, symlinks=True, dirs_exist_ok=True)


def _signal_group(process: asyncio.subprocess.Process, sig: int) -> None:
    try:
        os.killpg(process.pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def _text(data: bytes | None) -> str | None:
    return data.decode(errors="replace") if data else None


class LocalEnvironment(BaseEnvironment):
    """A Harbor environment that is the machine this runs on: the task container."""

    def __init__(self, cwd: Path, out_dir: Path, key_names: Iterable[str]):
        self._cwd = Path(cwd)
        self._key_names = frozenset(key_names)
        super().__init__(
            environment_dir=self._cwd,
            environment_name="local",
            session_id="terminus2-local",
            trial_paths=_OutputPaths(Path(out_dir)),
            task_env_config=EnvironmentConfig(),
        )

    @staticmethod
    def type() -> str:
        return "local"

    @property
    def capabilities(self) -> EnvironmentCapabilities:
        return EnvironmentCapabilities()

    def _validate_definition(self) -> None:
        pass

    async def start(self, force_build: bool) -> None:
        pass

    async def stop(self, delete: bool) -> None:
        pass

    async def upload_file(self, source_path: Path | str, target_path: str) -> None:
        _copy_file(source_path, target_path)

    async def upload_dir(self, source_dir: Path | str, target_dir: str) -> None:
        _copy_dir(source_dir, target_dir)

    async def download_file(self, source_path: str, target_path: Path | str) -> None:
        _copy_file(source_path, target_path)

    async def download_dir(self, source_dir: str, target_dir: Path | str) -> None:
        _copy_dir(source_dir, target_dir)

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: int | None = None,
        user: str | int | None = None,
    ) -> ExecResult:
        """Run ``command`` with ``bash -c`` in ``cwd`` (default: the task folder), without stdin.

        ``user`` is ignored: Valkyrie runs the agent as root. The command gets this process's
        environment minus provider keys (``scrubbed_env``), plus ``env``. The tmux server and its
        shell are started through here, so they never see those keys.

        Timeouts behave as in Harbor's DockerEnvironment.exec: a falsy ``timeout_sec`` waits for
        as long as the command runs; otherwise, when it passes, the command gets SIGTERM, then
        SIGKILL after 5 seconds, and RuntimeError("Command timed out after N seconds") is raised.
        The signals go to the command's whole process group, so nothing it started keeps running.
        """
        process = await asyncio.create_subprocess_exec(
            "bash",
            "-c",
            command,
            cwd=cwd or self._cwd,
            env={**scrubbed_env(os.environ, self._key_names), **(self._merge_env(env) or {})},
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        try:
            if timeout_sec:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_sec)
            else:
                stdout, stderr = await process.communicate()
        except asyncio.TimeoutError:
            _signal_group(process, signal.SIGTERM)
            try:
                await asyncio.wait_for(process.wait(), timeout=KILL_GRACE_SEC)
            except asyncio.TimeoutError:
                pass
            _signal_group(process, signal.SIGKILL)
            await process.wait()
            raise RuntimeError(f"Command timed out after {timeout_sec} seconds") from None
        return ExecResult(stdout=_text(stdout), stderr=_text(stderr), return_code=process.returncode or 0)


def metrics_of(context: AgentContext) -> dict:
    """Token and cost totals that Terminus 2 recorded in ``context``."""
    return {
        "n_input_tokens": context.n_input_tokens,
        "n_output_tokens": context.n_output_tokens,
        "n_cache_tokens": context.n_cache_tokens,
        "cost_usd": context.cost_usd,
        "metadata": context.metadata,
    }


async def run(problem: Path, model: str, options: dict, out_dir: Path, upstream: dict) -> int:
    """Run Terminus 2 on the task in ``problem`` from the current folder; return the exit code."""
    cwd = Path.cwd()
    context = AgentContext()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "trajectory.json").unlink(missing_ok=True)  # never ship an earlier run's file
    except OSError:
        pass  # Terminus 2 logs its own failure to write here; write_summary reports ours
    try:
        instruction = problem.read_text(encoding="utf-8")
        environment = LocalEnvironment(cwd=cwd, out_dir=out_dir, key_names=provider_env_names())
        agent = Terminus2(logs_dir=out_dir, model_name=model, record_terminal_session=False, **options)
        await agent.setup(environment)
        cd = shlex.join(["tmux", "send-keys", "-t", agent.name(), f"cd {shlex.quote(str(cwd))}", "Enter"])
        if (await environment.exec(cd)).return_code != 0:
            raise RuntimeError("could not type cd into the tmux session")
        await agent.run(instruction, environment, context)
    except Exception as error:
        traceback.print_exc()
        name = type(error).__name__
        write_error(f"AgentError: terminus2 {name}")
        write_summary(
            out_dir, upstream, outcome="error", stop_reason=name, agent_exit_code=1, metrics=metrics_of(context)
        )
        return 1
    write_summary(
        out_dir, upstream, outcome="completed", stop_reason="returned", agent_exit_code=0, metrics=metrics_of(context)
    )
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_terminus2.py",
        usage=(
            "run_terminus2.py PROBLEM --model M [--max-turns N] [--temperature T] [--parser json|xml] "
            "[--reasoning-effort E] [--output-dir D]"
        ),
        description="Run Harbor's Terminus 2 on the task in the file PROBLEM.",
    )
    parser.add_argument("problem", metavar="PROBLEM", help="file holding the task")
    parser.add_argument("--model", required=True, help="litellm model name")
    parser.add_argument("--max-turns", default="", help="empty keeps upstream's default (no practical limit)")
    parser.add_argument("--temperature", default="", help="empty sends none")
    parser.add_argument("--parser", default="", help="json or xml; empty keeps upstream's default (json)")
    parser.add_argument("--reasoning-effort", default="", help="empty sends none")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help=f"default: {DEFAULT_OUTPUT_DIR}")
    parser.add_argument(
        "--upstream",
        default=str(Path(__file__).with_name("upstream.json")),
        help="upstream.json to record in summary.json (default: next to this file)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.output_dir)
    upstream = load_upstream(Path(args.upstream))
    try:
        options = parse_options(
            max_turns=args.max_turns,
            temperature=args.temperature,
            parser=args.parser,
            reasoning_effort=args.reasoning_effort,
        )
    except ValueError as error:
        write_error(f"AgentError: terminus2 {error}")
        write_summary(
            out_dir,
            upstream,
            outcome="error",
            stop_reason="invalid_options",
            agent_exit_code=1,
            metrics=metrics_of(AgentContext()),
        )
        return 1
    return asyncio.run(run(Path(args.problem), args.model, options, out_dir, upstream))


if __name__ == "__main__":
    sys.exit(main())
