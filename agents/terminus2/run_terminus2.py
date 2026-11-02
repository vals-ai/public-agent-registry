#!/usr/bin/env python3
import argparse
import asyncio
import sys
import traceback
from pathlib import Path

from terminus2_support import no_metrics, parse_options, write_error, write_summary

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
    return parser.parse_args(argv)


def fail(out_dir: Path, line: str, stop_reason: str) -> int:
    write_error(line)
    write_summary(out_dir, outcome="error", stop_reason=stop_reason, agent_exit_code=1, metrics=no_metrics())
    return 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.output_dir)
    try:
        options = parse_options(
            max_turns=args.max_turns,
            temperature=args.temperature,
            parser=args.parser,
            reasoning_effort=args.reasoning_effort,
        )
    except ValueError as error:
        return fail(out_dir, f"AgentError: terminus2 {error}", "invalid_options")
    try:
        import terminus2_bridge
    except Exception as error:
        traceback.print_exc()
        name = type(error).__name__
        return fail(out_dir, f"AgentError: terminus2 {name}", name)
    return asyncio.run(terminus2_bridge.run(Path(args.problem), args.model, options, out_dir))


if __name__ == "__main__":
    sys.exit(main())
