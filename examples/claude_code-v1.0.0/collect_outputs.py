#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

WORKSPACE_PATH = Path.cwd()
OUTPUT_ROOT = Path(os.environ.get("AGENT_OUTPUT_ROOT", "/logs"))
TRAJECTORY_PATH = OUTPUT_ROOT / "trajectory.jsonl"
FINAL_MESSAGE_PATH = OUTPUT_ROOT / "final_message.txt"
METRICS_PATH = OUTPUT_ROOT / "metrics_total.json"
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"
RAW_OUTPUT_PATH = OUTPUT_ROOT / "raw_output.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("problem_statement_path")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--model", required=True)
    return parser.parse_args()


def event_from_line(line: str) -> Optional[dict[str, Any]]:
    stripped = line.strip()
    if not stripped:
        return None
    try:
        event = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return event if isinstance(event, dict) else None


def extract_text_from_content(content: Any) -> Optional[str]:
    if isinstance(content, str) and content.strip():
        return content.strip()
    if not isinstance(content, list):
        return None

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if item.get("type") == "text" and isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n".join(parts) if parts else None


def extract_final_message(events: list[dict[str, Any]]) -> Optional[str]:
    for event in reversed(events):
        result = event.get("result")
        if isinstance(result, str) and result.strip():
            return result.strip()

    for event in reversed(events):
        message = event.get("message")
        if isinstance(message, dict):
            text = extract_text_from_content(message.get("content"))
            if text:
                return text

        text = extract_text_from_content(event.get("content"))
        if text:
            return text

    return None


def extract_metrics(events: list[dict[str, Any]], wall_clock_duration: float) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "cost": None,
        "wall_clock_duration": round(wall_clock_duration, 3),
    }
    for event in reversed(events):
        if "total_cost_usd" in event:
            metrics["cost"] = event.get("total_cost_usd")
            break

    for event in reversed(events):
        usage = event.get("usage")
        if isinstance(usage, dict):
            metrics.update(usage)
            break

    return metrics


def get_cli_version() -> Optional[str]:
    try:
        result = subprocess.run(
            ["claude", "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None

    version = (result.stdout or result.stderr).strip()
    return version or None


def write_summary(
    task_id: str,
    model: str,
    prompt_text: str,
    exit_code: int,
    wall_clock_duration: float,
    events: list[dict[str, Any]],
) -> None:
    message = extract_final_message(events)
    if message:
        FINAL_MESSAGE_PATH.write_text(message + "\n", encoding="utf-8")

    metrics = extract_metrics(events, wall_clock_duration)
    METRICS_PATH.write_text(json.dumps(metrics, indent=4), encoding="utf-8")

    summary = {
        "metadata": {
            "task_id": task_id,
            "model": model,
            "agent": "claude_code-v1.0.0",
            "cli_version": get_cli_version(),
            "timestamp": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
            "output_path": str(OUTPUT_ROOT),
            "success": bool(message) and exit_code == 0,
            "return_code": exit_code,
        },
        "task_prompt": prompt_text,
        "metrics": metrics,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=4), encoding="utf-8")


def build_claude_command() -> list[str]:
    return [
        "claude",
        "-p",
        "--verbose",
        "--output-format",
        "stream-json",
        "--allowedTools",
        "Bash Edit Write Read Glob Grep LS WebFetch NotebookEdit NotebookRead "
        "TodoRead TodoWrite Agent Skill SlashCommand Task WebSearch",
    ]


def stream_claude(command: list[str], prompt_text: str, env: dict[str, str]) -> tuple[int, list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    with (
        RAW_OUTPUT_PATH.open("w", encoding="utf-8") as raw_output,
        TRAJECTORY_PATH.open("w", encoding="utf-8") as trajectory,
    ):
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            cwd=WORKSPACE_PATH,
        )
        assert process.stdin is not None
        assert process.stdout is not None

        process.stdin.write(prompt_text)
        process.stdin.close()

        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            raw_output.write(line)
            raw_output.flush()
            event = event_from_line(line)
            if event is not None:
                events.append(event)
                trajectory.write(json.dumps(event) + "\n")
                trajectory.flush()

        return process.wait(), events


def main() -> int:
    args = parse_args()
    task_file = Path(args.problem_statement_path)
    if not task_file.exists():
        raise SystemExit(f"Problem statement path not found: {task_file}")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    prompt_text = task_file.read_text(encoding="utf-8")
    model_name = args.model.removeprefix("anthropic/")

    env = dict(os.environ)
    env["ANTHROPIC_MODEL"] = model_name

    exit_code = 1
    events: list[dict[str, Any]] = []
    start = time.monotonic()
    try:
        exit_code, events = stream_claude(build_claude_command(), prompt_text, env)
        return exit_code
    finally:
        write_summary(
            task_id=args.task_id,
            model=args.model,
            prompt_text=prompt_text,
            exit_code=exit_code,
            wall_clock_duration=time.monotonic() - start,
            events=events,
        )


if __name__ == "__main__":
    raise SystemExit(main())
