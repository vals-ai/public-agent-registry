"""Pass a task to the native CLI and retain its JSON events and final answer."""

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
MODELS = {"openai/gpt-4.1", "anthropic/claude-sonnet-4-5", "openrouter/openai/gpt-4.1"}


def collect_events(path, agent):
    final = ""
    errors = 0
    records = 0
    completed = False
    failed = False
    with path.open(errors="replace") as stream:
        for line in stream:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            records += 1
            if event.get("type") == "error":
                errors += 1
                failed = True
            if agent == "opencode":
                part = event.get("part") or {}
                if event.get("type") == "text":
                    final = part.get("text", final)
                if event.get("type") == "step_finish":
                    completed = part.get("reason") == "stop"
            elif event.get("type") == "message_end":
                message = event.get("message") or {}
                if message.get("role") == "assistant":
                    failed = message.get("stopReason") in ("error", "aborted")
                    errors += int(failed)
                    completed = message.get("stopReason") == "stop"
                    final = "\n".join(part.get("text", "") for part in message.get("content", [])
                                      if isinstance(part, dict) and part.get("type") == "text")
    return final, errors, records, completed and not failed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--model", required=True, choices=sorted(MODELS))
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    metadata = json.loads((ROOT / "upstream.json").read_text())
    agent = metadata["agent"]
    if agent not in ("pi", "opencode", "omp"):
        raise ValueError("Unknown native agent")
    provider, model = args.model.split("/", 1)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    task = Path(args.task).read_bytes()
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix=f"valkyrie-{agent}-") as state:
        env = {**os.environ, "PI_CODING_AGENT_DIR": state,
               "XDG_CONFIG_HOME": state + "/config", "XDG_DATA_HOME": state + "/data",
               "XDG_STATE_HOME": state + "/state", "XDG_CACHE_HOME": state + "/cache"}
        env["PATH"] = str(ROOT / ".runtime/node/bin") + os.pathsep + env.get("PATH", "")
        for variable in ("OMP_PROFILE", "PI_PROFILE", "PI_CONFIG_FILES"):
            env.pop(variable, None)
        if agent == "pi":
            command = [str(ROOT / ".runtime/node/bin/node"),
                       str(ROOT / "node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js"),
                       "--print", "--mode", "json", "--no-session", "--provider", provider,
                       "--model", model, "--no-extensions", "--no-skills", "--no-prompt-templates", "--no-approve"]
        elif agent == "omp":
            command = [str(ROOT / ".runtime/omp"), "--print", "--mode", "json", "--no-session",
                       "--provider", provider, "--model", model, "--no-extensions", "--no-skills",
                       "--approval-mode", "yolo", "--no-title", "--no-ui"]
            env["PI_AUTO_QA"] = "0"
            env["PI_AUTO_QA_PUSH"] = "0"
        else:
            env["OPENCODE_CONFIG_CONTENT"] = json.dumps({"$schema": "https://opencode.ai/config.json",
                                                       "permission": "allow", "autoupdate": False})
            command = [str(ROOT / "node_modules/opencode-ai/bin/opencode.exe"), "run",
                       "--format", "json", "--model", args.model, "--auto"]
        with (output / "trajectory.jsonl").open("wb") as stdout, (output / "stderr.log").open("wb") as stderr:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                                       env=env, start_new_session=True)
            timed_out = False
            try:
                process.communicate(task, timeout=args.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
        final, errors, records, completed = collect_events(output / "trajectory.jsonl", agent)
        code = 124 if timed_out else (process.returncode or (0 if completed else 1))
        if code < 0:
            code = 128 - code
        (output / "final_message.txt").write_text(final)
        (output / "summary.json").write_text(json.dumps({
            "agent": agent, "native_version": metadata["version"], "requested_model": args.model,
            "exit_code": code, "native_exit_code": process.returncode, "timed_out": timed_out,
            "native_error_events": errors, "event_count": records,
            "native_completion_observed": completed,
            "elapsed_seconds": round(time.monotonic() - start, 3),
            "task_success": None,
        }, indent=2) + "\n")
        if code and os.environ.get("VALKYRIE_ERROR_PATH"):
            Path(os.environ["VALKYRIE_ERROR_PATH"]).write_text(
                f"AgentError: native {agent} execution failed; inspect stderr.log and trajectory.jsonl")
        return code


if __name__ == "__main__":
    sys.exit(main())
