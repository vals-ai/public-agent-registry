"""Helpers for run_terminus2.py that do not need Harbor: options, environment, summary, errors.

Kept apart from run_terminus2.py so they can be tested without installing Harbor.
"""

import json
import os
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

AGENT = "terminus2"
MAX_ERROR_CHARS = 512
# The AgentContext fields copied into summary.json's "metrics".
METRIC_KEYS = ("n_input_tokens", "n_output_tokens", "n_cache_tokens", "cost_usd", "metadata")


def no_metrics() -> dict:
    """The ``metrics`` of a run that ended before Terminus 2 recorded any: every key, all null."""
    return dict.fromkeys(METRIC_KEYS)


def scrubbed_env(environ: Mapping[str, str], key_names: Iterable[str]) -> dict[str, str]:
    """A copy of ``environ`` without the names in ``key_names`` or any name ending in ``_API_KEY``."""
    drop = set(key_names)
    return {name: value for name, value in environ.items() if name not in drop and not name.endswith("_API_KEY")}


def parse_options(*, max_turns: str, temperature: str, parser: str, reasoning_effort: str) -> dict[str, object]:
    """Terminus2 keyword arguments for the kwargs that are set. Empty ones keep upstream's default.

    Raises ValueError, naming the option but not its value, when a number does not parse.
    """
    options: dict[str, object] = {}
    if max_turns:
        try:
            options["max_turns"] = int(max_turns)
        except ValueError:
            raise ValueError("max_turns must be an integer") from None
    if temperature:
        try:
            options["temperature"] = float(temperature)
        except ValueError:
            raise ValueError("temperature must be a number") from None
    if parser:
        options["parser_name"] = parser
    if reasoning_effort:
        options["reasoning_effort"] = reasoning_effort
    return options


def write_summary(
    out_dir: Path, upstream: dict, *, outcome: str, stop_reason: str, agent_exit_code: int, metrics: dict
) -> None:
    """Write ``out_dir/summary.json``. A failure is reported on stderr and never raised, so it
    cannot change the run's exit code or stop the error line from being written."""
    summary = {
        "agent": AGENT,
        "upstream": upstream,
        "outcome": outcome,
        "stop_reason": stop_reason,
        "agent_exit_code": agent_exit_code,
        "metrics": metrics,
    }
    path = out_dir / "summary.json"
    temporary = out_dir / "summary.json.tmp"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(summary, indent=2, default=str) + "\n")
        temporary.replace(path)
    except OSError as error:
        print(f"run_terminus2: could not write {path}: {type(error).__name__}", file=sys.stderr)
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def write_error(message: str) -> None:
    """Write ``message`` as one line (at most 512 characters) to $VALKYRIE_ERROR_PATH, if set."""
    path = os.environ.get("VALKYRIE_ERROR_PATH")
    if not path:
        return
    line = " ".join(message.split())[:MAX_ERROR_CHARS]
    try:
        Path(path).write_text(line + "\n")
    except OSError as error:
        print(f"run_terminus2: could not write the error line: {type(error).__name__}", file=sys.stderr)


def load_upstream(path: Path) -> dict:
    """The contents of upstream.json, or {} if it is missing or not a JSON object."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}
