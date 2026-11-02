import json
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def make_agent(tmp_path: Path) -> Callable[..., Path]:
    """Build ``<tmp_path>/agents/<folder>/`` holding a valid agent.

    ``contract`` and ``upstream`` overrides merge into the defaults. ``checksums`` is written
    to ``checksums.txt`` when it is a string, and no file is created when it is ``None``.
    """

    def build(
        *,
        folder: str = "x",
        contract: dict | None = None,
        upstream: dict | None = None,
        checksums: str | None = None,
    ) -> Path:
        agent_dir = tmp_path / "agents" / folder
        agent_dir.mkdir(parents=True)
        contract_data = {
            "name": folder,
            "install_cmd": "bash setup.sh",
            "run_cmd": "x {problem_statement_path}",
            **(contract or {}),
        }
        upstream_data = {
            "repo": "o/r",
            "tag": "v1.0.0",
            "commit": "a" * 40,
            "submodule": "r",
            **(upstream or {}),
        }
        (agent_dir / "contract.yaml").write_text(yaml.safe_dump(contract_data))
        (agent_dir / "upstream.json").write_text(json.dumps(upstream_data, indent=2) + "\n")
        if checksums is not None:
            (agent_dir / "checksums.txt").write_text(checksums)
        return agent_dir

    return build
