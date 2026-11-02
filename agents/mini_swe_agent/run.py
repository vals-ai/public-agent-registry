#!/usr/bin/env python3
"""Run upstream mini-swe-agent on one problem statement and write summary.json.

Usage: run.py PROBLEM --model M [--config C] [--cost-limit X] [--step-limit N]
              [--cost-tracking V] [--output-dir D]

PROBLEM is the path of a file holding the task. The agent runs in the current directory with the
``local`` environment, so it edits the benchmark's working directory directly. Outputs land in
the output directory: ``trajectory.json`` (written by mini-swe-agent) and ``summary.json``
(always written, even when the agent fails).

Exit code: 0 when the agent stopped on its own (including at a cost or step limit), otherwise
nonzero, with one ``AgentError: ...`` line in ``$VALKYRIE_ERROR_PATH``. That line only holds the
exit code and mini-swe-agent's exit status, never the task or model text.

``minisweagent`` is imported inside ``run_mini``, after the environment is set, because it reads
its settings from the environment at import time and prints a banner unless told not to.
"""

import argparse
import json
import os
import re
import sys
import traceback
from pathlib import Path

AGENT = "mini_swe_agent"
DEFAULT_OUTPUT_DIR = "/logs/mini_swe_agent"
UPSTREAM = Path(__file__).with_name("upstream.json")
NO_TRAJECTORY = "no trajectory"
MAX_ERROR_CHARS = 512
STATUS = re.compile(r"\w{1,80}", re.ASCII)


def build_argv(
    task: str, *, model: str, config: str, output: Path, cost_limit: str, step_limit: str
) -> list[str]:
    """Command line for ``mini``: unattended, local environment, in the current directory.

    ``-c environment.cwd=`` comes after the config so a benchmark config's fixed ``cwd`` (for
    example ``/testbed``) does not apply. ``-t`` takes the task as its value even when the text
    starts with a dash.
    """
    argv = [
        "-t", task,
        "-m", model,
        "-c", config,
        "-c", "environment.cwd=",
        "--environment-class", "local",
        "--agent-class", "default",
        "-y",
        "--exit-immediately",
        "-o", str(output),
    ]  # fmt: skip
    if cost_limit:
        argv += ["-l", cost_limit]
    if step_limit:
        argv += ["-c", f"agent.step_limit={step_limit}"]
    return argv


def read_exit_status(trajectory: Path) -> str | None:
    """``info.exit_status`` of a saved trajectory, or None if it is missing or malformed."""
    try:
        status = json.loads(trajectory.read_text(encoding="utf-8"))["info"]["exit_status"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return status if isinstance(status, str) else None


def summarize(trajectory: Path, upstream: dict, agent_exit_code: int) -> dict:
    """The summary.json content for one run."""
    stop_reason = read_exit_status(trajectory)
    return {
        "agent": AGENT,
        "upstream": upstream,
        "outcome": "completed" if agent_exit_code == 0 else "error",
        "stop_reason": NO_TRAJECTORY if stop_reason is None else stop_reason,
        "agent_exit_code": agent_exit_code,
    }


def write_error(message: str) -> None:
    """Write ``message`` as one line (at most 512 characters) to $VALKYRIE_ERROR_PATH, if set."""
    path = os.environ.get("VALKYRIE_ERROR_PATH")
    if not path:
        return
    line = " ".join(message.split())[:MAX_ERROR_CHARS]
    Path(path).write_text(line + "\n")


def load_upstream(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run.py",
        usage=(
            "run.py PROBLEM --model M [--config C] [--cost-limit X] [--step-limit N] "
            "[--cost-tracking V] [--output-dir D]"
        ),
        description="Run mini-swe-agent on the task in the file PROBLEM.",
    )
    parser.add_argument("problem", metavar="PROBLEM", help="file holding the task")
    parser.add_argument("--model", required=True, help="litellm model name")
    parser.add_argument("--config", default="mini.yaml", help="mini-swe-agent config (default: mini.yaml)")
    parser.add_argument("--cost-limit", default="", help="USD; empty keeps upstream's default, 0 disables")
    parser.add_argument("--step-limit", default="", help="max agent steps; empty keeps upstream's default")
    parser.add_argument("--cost-tracking", default="", help="MSWEA_COST_TRACKING value, e.g. ignore_errors")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help=f"default: {DEFAULT_OUTPUT_DIR}")
    return parser.parse_args(argv)


def run_mini(argv: list[str]) -> int:
    """Run ``mini`` with ``argv`` in this process and return its exit code."""
    sys.argv = ["mini", *argv]
    try:
        from minisweagent.run.mini import app

        app()
    except SystemExit as stop:
        if stop.code is None:
            return 0
        return stop.code if isinstance(stop.code, int) else 1
    except Exception:
        traceback.print_exc()
        return 1
    return 0


def error_status(stop_reason: str) -> str:
    """``stop_reason`` as shown in the error line: only word characters, else ``unknown``."""
    return stop_reason if stop_reason == NO_TRAJECTORY or STATUS.fullmatch(stop_reason) else "unknown"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    trajectory = output_dir / "trajectory.json"
    trajectory.unlink(missing_ok=True)

    error = None
    try:
        task = Path(args.problem).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        code = 1
        error = "AgentError: cannot read the problem statement"
    else:
        os.environ["MSWEA_CONFIGURED"] = "true"
        os.environ["MSWEA_SILENT_STARTUP"] = "1"
        if args.cost_tracking:
            os.environ["MSWEA_COST_TRACKING"] = args.cost_tracking
        code = run_mini(
            build_argv(
                task,
                model=args.model,
                config=args.config,
                output=trajectory,
                cost_limit=args.cost_limit,
                step_limit=args.step_limit,
            )
        )

    summary = summarize(trajectory, load_upstream(UPSTREAM), code)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    if code != 0:
        status = error_status(summary["stop_reason"])
        write_error(error or f"AgentError: mini-swe-agent exited with code {code} ({status})")
    return code


if __name__ == "__main__":
    sys.exit(main())
