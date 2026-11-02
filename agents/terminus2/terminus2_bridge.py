import asyncio
import os
import shlex
import shutil
import signal
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
from terminus2_support import METRIC_KEYS, scrubbed_env, write_error, write_summary

KILL_GRACE_SEC = 5


def provider_env_names() -> list[str]:
    names: set[str] = set()
    for access in PROVIDERS.values():
        names.update(access.api_key_candidate_names, access.base_url_candidate_names, access.extra_env_names)
    return sorted(names)


@dataclass(frozen=True)
class _OutputPaths(TrialPaths):
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
    return {key: getattr(context, key) for key in METRIC_KEYS}


async def run(problem: Path, model: str, options: dict, out_dir: Path) -> int:
    cwd = Path.cwd()
    context = AgentContext()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "trajectory.json").unlink(missing_ok=True)
    except OSError:
        pass
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
        outcome, stop_reason, code = "error", name, 1
    else:
        outcome, stop_reason, code = "completed", "returned", 0
    write_summary(out_dir, outcome=outcome, stop_reason=stop_reason, agent_exit_code=code, metrics=metrics_of(context))
    return code
