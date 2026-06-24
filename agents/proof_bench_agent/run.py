"""Thin Valkyrie wrapper for proof-bench agent."""

import argparse
import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

from model_library.agent import AgentResult, TurnSummary
from proof_bench.agent import run_agent
from proof_bench.mcp_client import ToolConfig, resolve_stdio_command
from proof_bench.prompts import build_prompt
from proof_bench.utils import _strip_response_and_format_proof

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

MAX_TURNS = 40


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ProofBench Valkyrie Agent")
    parser.add_argument(
        "--model",
        required=True,
        help="Model string (e.g. anthropic/claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--problem-file", required=True, help="Path to JSON problem file"
    )
    parser.add_argument("--task-id", required=True, help="Problem identifier")
    parser.add_argument("--output", required=True, help="Path to write result.json")
    parser.add_argument(
        "--lean-project", required=True, help="Path to Lean project with Mathlib"
    )
    return parser.parse_args()


def load_problem(problem_file: str) -> dict:
    """Read and parse the JSON problem file written by the benchmark service."""
    text = Path(problem_file).read_text()
    problem = json.loads(text)

    required_fields = {"id", "header", "formal", "statement"}
    missing = required_fields - problem.keys()
    if missing:
        raise ValueError(f"Problem file missing required fields: {missing}")

    # proof_bench internally uses "natural" for the NL statement field,
    # but the benchmark service JSONL uses "statement"
    if "natural" not in problem and "statement" in problem:
        problem["natural"] = problem["statement"]

    return problem


def snapshot_environment(lean_project: str) -> dict[str, Any]:
    """Capture Lean/Mathlib version info from the sandbox for diagnostics."""
    env: dict[str, Any] = {}

    try:
        result = subprocess.run(
            ["lean", "--version"], capture_output=True, text=True, timeout=10
        )
        env["lean_version"] = result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        env["lean_version"] = None

    manifest_path = Path(lean_project) / "lake-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
        for pkg in manifest.get("packages", []):
            if pkg.get("name") == "mathlib":
                env["mathlib_rev"] = pkg.get("rev")
                env["mathlib_input_rev"] = pkg.get("inputRev")
                break
    except Exception:
        env["mathlib_rev"] = None
        env["mathlib_input_rev"] = None

    return env


def build_tool_configs(lean_project: str) -> tuple[ToolConfig, ToolConfig]:
    """Build MCP tool configs pointing at the sandbox Lean project."""
    stdio_command = resolve_stdio_command()

    run_code_config: ToolConfig = {
        "transport": "stdio",
        "project_path": lean_project,
        "stdio_command": stdio_command,
    }

    loogle_config: ToolConfig = {
        "transport": "stdio",
        "project_path": lean_project,
        "stdio_command": stdio_command,
        "loogle_daemon_url": "http://127.0.0.1:8765",
        "max_results": 8,
    }

    return loogle_config, run_code_config


def check_proof_resolved(result: AgentResult) -> tuple[bool, str]:
    """Check if submit_proof was called and succeeded."""
    resolved = any(
        tc.success
        for turn in result.turns
        if isinstance(turn, TurnSummary)
        for tc in turn.tool_calls
        if tc.tool_name == "submit_proof" and tc.done
    )
    if resolved:
        return True, "Proof verified by submit_proof"

    # Check if submit_proof was called but failed
    submitted = any(
        tc.tool_name == "submit_proof"
        for turn in result.turns
        if isinstance(turn, TurnSummary)
        for tc in turn.tool_calls
    )
    if submitted:
        return False, "Proof submitted but verification failed"

    if result.stop_reason == "error":
        return False, f"Agent error: {result.final_error}"

    return False, "No proof submitted (agent may have timed out)"


def _build_per_turn_summaries(result: AgentResult) -> list[dict[str, Any]]:
    """Extract per-turn tool call summaries for diagnostics."""
    summaries: list[dict[str, Any]] = []
    for i, turn in enumerate(result.turns):
        if isinstance(turn, TurnSummary):
            summaries.append({
                "turn": i + 1,
                "duration_seconds": turn.duration_seconds,
                "tool_calls": [
                    {
                        "tool_name": tc.tool_name,
                        "success": tc.success,
                        "done": tc.done,
                        "duration_seconds": tc.duration_seconds,
                        "error": str(tc.error) if tc.error else None,
                    }
                    for tc in turn.tool_calls
                ],
                "tokens": {
                    "in_tokens": turn.metadata.in_tokens,
                    "out_tokens": turn.metadata.out_tokens,
                    "reasoning_tokens": turn.metadata.reasoning_tokens,
                    "cache_read_tokens": turn.metadata.cache_read_tokens,
                },
            })
        else:
            summaries.append({
                "turn": i + 1,
                "error": str(turn.error),
                "duration_seconds": turn.duration_seconds,
            })
    return summaries


def build_output(
    result: AgentResult,
    *,
    model: str,
    problem: dict[str, Any],
    environment: dict[str, Any],
    loogle_config: ToolConfig,
) -> dict[str, Any]:
    """Build the output JSON with verification result, agent metadata, and diagnostics."""
    resolved, reason = check_proof_resolved(result)

    proof_text = result.final_answer or ""
    processed_proof = _strip_response_and_format_proof(proof_text) or ""

    full_proof_code = (
        f"{problem['header']}\n\n{problem['formal']}\n{processed_proof}"
        if processed_proof
        else ""
    )

    return {
        "resolved": resolved,
        "reason": reason,
        "proof": processed_proof,
        "full_proof_code": full_proof_code,
        "agent_result": json.loads(result.model_dump_json()),
        "diagnostics": {
            "agent_config": {
                "model": model,
                "max_turns": MAX_TURNS,
                "include_nl_proof": False,
                "k": 1,
                "loogle_mode": "local_daemon" if loogle_config.get("loogle_daemon_url") else "remote",
                "loogle_daemon_url": loogle_config.get("loogle_daemon_url"),
            },
            "environment": environment,
            "per_turn_summaries": _build_per_turn_summaries(result),
        },
    }


async def run(args: argparse.Namespace) -> None:
    problem = load_problem(args.problem_file)
    logger.info("Loaded problem: %s", problem["id"])

    environment = snapshot_environment(args.lean_project)
    logger.info("Environment: %s", environment)

    # Write empty output upfront so it exists even if we're killed by timeout.
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "resolved": False,
                "reason": "Agent did not complete (likely timed out)",
                "proof": "",
                "agent_result": {},
            }
        )
    )

    loogle_config, run_code_config = build_tool_configs(args.lean_project)

    system_prompt, user_prompt = build_prompt(
        problem,
        include_nl_proof=False,
        use_tools=True,
        max_turns=MAX_TURNS,
    )

    result = await run_agent(
        args.model,
        user_prompt,
        system_prompt=system_prompt,
        loogle_config=loogle_config,
        run_code_config=run_code_config,
        problem_context={"header": problem["header"], "formal": problem["formal"]},
        max_turns=MAX_TURNS,
        question_id=args.task_id,
        log_dir=Path("/logs"),
    )

    output = build_output(
        result,
        model=args.model,
        problem=problem,
        environment=environment,
        loogle_config=loogle_config,
    )
    output_path.write_text(json.dumps(output, indent=2))
    logger.info(
        "Wrote result to %s (resolved=%s, reason=%s)",
        args.output,
        output["resolved"],
        output["reason"],
    )

    if result.stop_reason == "error":
        print(f"Agent error: {result.final_error}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
