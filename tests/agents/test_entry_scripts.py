"""The entry scripts setup.sh writes for the Python agents: -E and no stdin.

Each test runs the ``printf`` line from setup.sh that writes the entry script, with the venv's Python
standing in as this interpreter and the wrapper replaced by a probe, then runs the entry script with a
task-style PYTHONPATH that would shadow the standard library's ``json`` module.
"""

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

AGENTS = Path(__file__).resolve().parents[2] / "agents"

PROBE = """\
import json, sys
print(sys.flags.ignore_environment, json.__name__, sys.stdin.read() == "", sys.argv[1:])
"""


@pytest.mark.parametrize(
    ("agent", "entry", "wrapper"),
    [("mini_swe_agent", "mini-swe-agent-run", "run.py"), ("terminus2", "terminus2-run", "run_terminus2.py")],
)
def test_entry_script_ignores_the_tasks_python_variables(tmp_path, agent, entry, wrapper):
    (line,) = [
        line
        for line in (AGENTS / agent / "setup.sh").read_text().splitlines()
        if line.startswith("printf ") and f"> /usr/local/bin/{entry}" in line
    ]
    script = tmp_path / entry
    here = tmp_path / "bundle"
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "python").symlink_to(sys.executable)
    here.mkdir()
    (here / wrapper).write_text(PROBE)
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "json.py").write_text("raise SystemExit('the task shadowed json')\n")

    write = line.replace(f"/usr/local/bin/{entry}", shlex.quote(str(script)))
    subprocess.run(["bash", "-c", write], env={**os.environ, "venv": str(venv), "here": str(here)}, check=True)
    result = subprocess.run(
        ["bash", str(script), "--model", "a b"],
        env={**os.environ, "PYTHONPATH": str(shadow)},
        input="the task's stdin",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "1 json True ['--model', 'a b']\n"
