#!/usr/bin/env python3

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from model_library.registry_utils import TokenDict, recompute_cost

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


def split_urls(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def configure_mcp(sse_urls: list[str], http_urls: list[str]) -> None:
    if not sse_urls and not http_urls:
        return

    codex_home = Path.home() / ".codex"
    codex_home.mkdir(parents=True, exist_ok=True)
    config_path = codex_home / "config.toml"

    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    lines: list[str] = []
    skip_section = False
    for line in existing.splitlines():
        if line.startswith("[mcp_servers."):
            skip_section = True
            continue
        if line.startswith("[") and skip_section:
            skip_section = False
        if not skip_section:
            lines.append(line)

    while lines and not lines[-1].strip():
        lines.pop()
    if lines:
        lines.append("")

    for index, url in enumerate(http_urls):
        name = "supabase" if index == 0 else f"supabase_{index}"
        lines.extend([f"[mcp_servers.{name}]", f'url = "{url}"', ""])
    for index, url in enumerate(sse_urls):
        lines.extend([f"[mcp_servers.sse_server_{index}]", f'url = "{url}"', ""])

    config_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def event_from_line(line: str) -> dict[str, object] | None:
    stripped = line.strip()
    if not stripped:
        return None
    try:
        event = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return event if isinstance(event, dict) else None


def stream_codex(command: list[str], env: dict[str, str]) -> tuple[int, list[dict[str, object]]]:
    events: list[dict[str, object]] = []
    with (
        TRAJECTORY_PATH.open("w", encoding="utf-8") as trajectory_log,
        RAW_OUTPUT_PATH.open("w", encoding="utf-8") as raw_output,
    ):
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            cwd=WORKSPACE_PATH,
        )
        assert process.stdout is not None

        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            raw_output.write(line)
            raw_output.flush()
            event = event_from_line(line)
            if event is not None:
                events.append(event)
                trajectory_log.write(json.dumps(event) + "\n")
                trajectory_log.flush()

        return process.wait(), events


def extract_final_message(events: list[dict[str, object]]) -> str | None:
    for event in reversed(events):
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "agent_message":
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return None


def extract_usage(events: list[dict[str, object]]) -> dict[str, int] | None:
    for event in reversed(events):
        if event.get("type") == "turn.completed":
            usage = event.get("usage")
            if isinstance(usage, dict):
                return usage
    return None


def get_cli_version() -> str | None:
    try:
        result = subprocess.run(
            ["codex", "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None

    version = (result.stdout or result.stderr).strip()
    return version or None


async def _compute_cost(model: str, usage: dict[str, int]) -> dict | None:
    model_key = f"openai/{model.split('/')[-1]}"
    tokens: TokenDict = {
        "in_tokens": usage.get("input_tokens", 0) - usage.get("cached_input_tokens", 0),
        "out_tokens": usage.get("output_tokens", 0) - usage.get("reasoning_output_tokens", 0),
        "cache_read_tokens": usage.get("cached_input_tokens") or None,
        "reasoning_tokens": usage.get("reasoning_output_tokens") or None,
    }
    try:
        result = await recompute_cost(model_key, tokens)
        return result.model_dump()
    except Exception:
        return None


def write_summary(
    task_id: str,
    model: str,
    prompt_text: str,
    exit_code: int,
    wall_clock_duration: float,
    events: list[dict[str, object]],
) -> None:
    message = extract_final_message(events)
    if message:
        FINAL_MESSAGE_PATH.write_text(message + "\n", encoding="utf-8")

    usage = extract_usage(events)
    cost: dict | None = asyncio.run(_compute_cost(model, usage)) if usage else None

    metrics = {
        "cost": cost,
        "wall_clock_duration": round(wall_clock_duration, 3),
        **(usage or {}),
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=4), encoding="utf-8")

    summary = {
        "metadata": {
            "task_id": task_id,
            "model": model,
            "agent": "codex-v1.0.0",
            "cli_version": get_cli_version(),
            "timestamp": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
            "output_path": str(OUTPUT_ROOT),
            "success": bool(message) and (exit_code == 0 or usage is not None),
            "return_code": exit_code,
        },
        "task_prompt": prompt_text,
        "metrics": metrics,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=4), encoding="utf-8")


def main() -> int:
    args = parse_args()
    task_file = Path(args.problem_statement_path)
    assert task_file.exists(), f"Problem statement path not found: {task_file}"

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    prompt_text = task_file.read_text(encoding="utf-8")

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Codex agent requires OPENAI_API_KEY")

    configure_mcp(
        sse_urls=split_urls(os.environ.get("MCP_SSE_URLS", "")),
        http_urls=split_urls(os.environ.get("MCP_SHTTP_URLS", "")),
    )

    command = [
        "codex",
        "exec",
        "--json",
        "--skip-git-repo-check",
        "--sandbox",
        "danger-full-access",
        "--model",
        args.model.split("/")[-1],
        "--cd",
        str(WORKSPACE_PATH),
        "--",
        prompt_text,
    ]

    exit_code = 1
    events: list[dict[str, object]] = []
    start = time.monotonic()
    try:
        exit_code, events = stream_codex(command, dict(os.environ))
        return exit_code
    finally:
        write_summary(
            args.task_id,
            args.model,
            prompt_text,
            exit_code,
            time.monotonic() - start,
            events,
        )


if __name__ == "__main__":
    raise SystemExit(main())
