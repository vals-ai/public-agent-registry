import json
import tempfile
from pathlib import Path

import yaml

from minisweagent.agents.default import METRICS_PER_TURN_FILENAME, METRICS_TOTAL_FILENAME, DefaultAgent
from minisweagent.environments.local import LocalEnvironment
from minisweagent.models.test_models import DeterministicModel, make_output

MOCK_IN_TOKENS = 100
MOCK_OUT_TOKENS = 50
MOCK_COST_TOTAL = 0.01
MOCK_COST_INPUT = 0.008
MOCK_COST_OUTPUT = 0.002
MOCK_DURATION_SECONDS = 1.5


def _load_default_agent_config():
    config_path = Path("src/minisweagent/config/default.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)["agent"]


def _make_metrics_dict():
    return {
        "cost": {
            "input": MOCK_COST_INPUT,
            "total": MOCK_COST_TOTAL,
            "output": MOCK_COST_OUTPUT,
            "reasoning": None,
            "cache_read": None,
            "cache_write": None,
            "total_input": MOCK_COST_INPUT,
            "total_output": MOCK_COST_OUTPUT,
            "total_override": None,
        },
        "duration_seconds": MOCK_DURATION_SECONDS,
        "in_tokens": MOCK_IN_TOKENS,
        "out_tokens": MOCK_OUT_TOKENS,
        "reasoning_tokens": None,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "extra": {},
        "total_input_tokens": MOCK_IN_TOKENS,
        "total_output_tokens": MOCK_OUT_TOKENS,
    }


def test_agent_save_includes_class_names():
    """Test that agent.save includes the full class names with import paths."""
    default_config = _load_default_agent_config()
    model = DeterministicModel(outputs=[make_output("echo 'test'", [])])
    env = LocalEnvironment()
    agent = DefaultAgent(model, env, **default_config)

    agent.add_messages({"role": "system", "content": "test system message"})
    agent.add_messages({"role": "user", "content": "test user message"})

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / "test_trajectory.json"

        agent.save(temp_path, {"info": {"exit_status": "Submitted", "submission": "test result"}})

        with temp_path.open() as f:
            saved_data = json.load(f)

        assert "info" in saved_data
        assert "config" in saved_data["info"]

        config = saved_data["info"]["config"]

        assert "agent_type" in config
        assert "model_type" in config
        assert "environment_type" in config

        assert config["agent_type"] == "minisweagent.agents.default.DefaultAgent"
        assert config["model_type"] == "minisweagent.models.test_models.DeterministicModel"
        assert config["environment_type"] == "minisweagent.environments.local.LocalEnvironment"

        assert saved_data["info"]["exit_status"] == "Submitted"
        assert saved_data["info"]["submission"] == "test result"
        assert saved_data["trajectory_format"] == "mini-swe-agent-1.1"


def test_agent_serialize():
    """Test that agent.serialize returns the correct structure."""
    default_config = _load_default_agent_config()
    model = DeterministicModel(outputs=[make_output("echo 'test'", [])])
    env = LocalEnvironment()
    agent = DefaultAgent(model, env, **default_config)

    agent.add_messages({"role": "system", "content": "test system message"})
    agent.add_messages({"role": "user", "content": "test user message"})

    data = agent.serialize()

    assert "info" in data
    assert "config" in data["info"]
    assert "messages" in data


def test_save_writes_metrics_with_correct_values():
    NUM_TURNS = 3
    default_config = _load_default_agent_config()
    model = DeterministicModel(outputs=[make_output("echo 'test'", [])])
    env = LocalEnvironment()
    agent = DefaultAgent(model, env, **default_config)

    agent.add_messages({"role": "system", "content": "test"})
    for _ in range(NUM_TURNS):
        agent.add_messages({"role": "assistant", "content": "resp", "extra": {"metrics": _make_metrics_dict()}})
        agent.add_messages({"role": "tool", "content": "output", "tool_call_id": "call"})

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / "trajectory.json"
        agent.save(temp_path)

        per_turn = json.loads((Path(temp_dir) / METRICS_PER_TURN_FILENAME).read_text())
        assert len(per_turn) == NUM_TURNS
        for entry in per_turn:
            assert entry["in_tokens"] == MOCK_IN_TOKENS
            assert entry["out_tokens"] == MOCK_OUT_TOKENS
            assert entry["duration_seconds"] == MOCK_DURATION_SECONDS
            assert entry["cost"]["total"] == MOCK_COST_TOTAL
            assert entry["cost"]["input"] == MOCK_COST_INPUT
            assert entry["cost"]["output"] == MOCK_COST_OUTPUT

        totals = json.loads((Path(temp_dir) / METRICS_TOTAL_FILENAME).read_text())
        assert totals["in_tokens"] == MOCK_IN_TOKENS * NUM_TURNS
        assert totals["out_tokens"] == MOCK_OUT_TOKENS * NUM_TURNS
        assert totals["total_input_tokens"] == MOCK_IN_TOKENS * NUM_TURNS
        assert totals["total_output_tokens"] == MOCK_OUT_TOKENS * NUM_TURNS
        assert totals["cost"]["total"] == MOCK_COST_TOTAL * NUM_TURNS
        assert totals["cost"]["input"] == MOCK_COST_INPUT * NUM_TURNS
        assert totals["cost"]["output"] == MOCK_COST_OUTPUT * NUM_TURNS
        assert "wall_clock_duration" in totals


def test_save_without_path_writes_nothing():
    default_config = _load_default_agent_config()
    model = DeterministicModel(outputs=[make_output("echo 'test'", [])])
    env = LocalEnvironment()
    agent = DefaultAgent(model, env, **default_config)

    agent.add_messages({"role": "assistant", "content": "resp", "extra": {"metrics": _make_metrics_dict()}})

    data = agent.save(None)
    assert "messages" in data
