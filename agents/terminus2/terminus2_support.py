import json
import os
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

AGENT = "terminus2"
UPSTREAM = Path(__file__).with_name("upstream.json")
MAX_ERROR_CHARS = 512
METRIC_KEYS = ("n_input_tokens", "n_output_tokens", "n_cache_tokens", "cost_usd", "metadata")


def no_metrics() -> dict:
    return dict.fromkeys(METRIC_KEYS)


def scrubbed_env(environ: Mapping[str, str], key_names: Iterable[str]) -> dict[str, str]:
    drop = set(key_names)
    return {name: value for name, value in environ.items() if name not in drop and not name.endswith("_API_KEY")}


def parse_options(*, max_turns: str, temperature: str, parser: str, reasoning_effort: str) -> dict[str, object]:
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


def write_summary(out_dir: Path, *, outcome: str, stop_reason: str, agent_exit_code: int, metrics: dict) -> None:
    summary = {
        "agent": AGENT,
        "upstream": load_upstream(UPSTREAM),
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
    path = os.environ.get("VALKYRIE_ERROR_PATH")
    if not path:
        return
    line = " ".join(message.split())[:MAX_ERROR_CHARS]
    try:
        Path(path).write_text(line + "\n")
    except OSError as error:
        print(f"run_terminus2: could not write the error line: {type(error).__name__}", file=sys.stderr)


def load_upstream(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}
