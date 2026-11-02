#!/usr/bin/env python3
"""Run Harbor's Terminus 2 on one problem statement and write summary.json.

Usage: run_terminus2.py PROBLEM --model M [--max-turns N] [--temperature T] [--parser json|xml]
                        [--reasoning-effort E] [--output-dir D]

PROBLEM is the path of a file holding the task. Empty option values keep upstream's defaults. The
agent runs from the current folder, the benchmark's working directory. How Terminus 2 is run on
this machine is in terminus2_bridge.py, the only module that imports Harbor. It is imported inside
``main``'s error handling, so even a Harbor that cannot be imported ends with summary.json and an
error line.

Outputs: Terminus 2 writes ``trajectory.json`` to the output directory (default /logs/agent, which
is also where Harbor writes the tmux pane log, ``terminus_2.pane``). This script adds
``summary.json`` there, always, even when the run fails.

Exit code: 0 when Terminus 2's ``run`` returns (the task was confirmed complete, ``max_turns`` was
reached, or the tmux session ended). Otherwise 1, with ``AgentError: terminus2 <ExceptionClass>``
in $VALKYRIE_ERROR_PATH (or ``AgentError: terminus2 <option> must be ...`` for a kwarg that does not
parse). That line never holds task or model text.
"""

import argparse
import asyncio
import sys
import traceback
from pathlib import Path

from terminus2_support import load_upstream, no_metrics, parse_options, write_error, write_summary

DEFAULT_OUTPUT_DIR = "/logs/agent"


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


def fail(out_dir: Path, upstream: dict, line: str, stop_reason: str) -> int:
    """Report a run that ended before Terminus 2 could record anything: error line, summary, exit 1."""
    write_error(line)
    write_summary(out_dir, upstream, outcome="error", stop_reason=stop_reason, agent_exit_code=1, metrics=no_metrics())
    return 1


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
        return fail(out_dir, upstream, f"AgentError: terminus2 {error}", "invalid_options")
    try:
        import terminus2_bridge  # imports Harbor, so a broken install is reported like any failure
    except Exception as error:
        traceback.print_exc()
        name = type(error).__name__
        return fail(out_dir, upstream, f"AgentError: terminus2 {name}", name)
    return asyncio.run(terminus2_bridge.run(Path(args.problem), args.model, options, out_dir, upstream))


if __name__ == "__main__":
    sys.exit(main())
