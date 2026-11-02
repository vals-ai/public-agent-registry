# mini_swe_agent

[mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) by the SWE-agent team, run for Valkyrie
exactly as upstream ships it. The upstream repository is the `mini-swe-agent/` git submodule, pinned to
tag **v2.4.6** (the commit is in `upstream.json`). Only `contract.yaml`, `setup.sh`, `run.py` and this
README are Vals-authored.

## Install

```bash
valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/main/agents/mini_swe_agent
```

`setup.sh` installs uv 0.13.5 (checked against a pinned sha256) and builds a Python 3.12 venv in
`/opt/mini-swe-agent-venv` from the submodule. The only thing it puts on `PATH` is the
`mini-swe-agent-run` entry script, which works from whatever folder Valkyrie copies the agent into.

## Run

The agent needs an API key for the model's provider. Pass it as a secret:

```bash
valkyrie run start --benchmark swebench --agent mini_swe_agent \
  --model anthropic/claude-sonnet-4-6 -s ANTHROPIC_API_KEY <secret-ref> \
  -k config=benchmarks/swebench.yaml --concurrency 10 --slice :10
```

`--model` is a [litellm](https://docs.litellm.ai/docs/providers) model name and must include the
provider, for example `anthropic/claude-sonnet-4-6` or `openai/gpt-5.4`. Use the secret that provider
expects (`OPENAI_API_KEY`, `GEMINI_API_KEY`, ...).

| Kwarg (`-k name=value`) | Default | Meaning |
| --- | --- | --- |
| `config` | `mini.yaml` | mini-swe-agent config. Use `benchmarks/swebench.yaml` for SWE-bench. |
| `cost_limit` | empty | USD cap. Empty keeps upstream's default, `0` disables the cap. |
| `step_limit` | empty | Maximum agent steps. Empty keeps upstream's default. |
| `cost_tracking` | empty | Set to `ignore_errors` for models litellm has no price for. |

## Outputs

Written to `/logs/mini_swe_agent/` and collected as `mini_swe_agent/`:

- `trajectory.json`: the full run, saved by mini-swe-agent after every step.
- `summary.json`: `agent`, `upstream` (the contents of `upstream.json`), `outcome`
  (`completed` or `error`), `stop_reason` (mini-swe-agent's `exit_status`, such as `Submitted`,
  `LimitsExceeded` or `AuthenticationError`) and `agent_exit_code`. It is written even when the run fails.

The run exits 0 when the agent stops on its own, including when it hits the cost or step limit. Any
other ending (a bad API key, an unpriced model, a crash) exits 1 with a one-line
`AgentError: ...` reason for Valkyrie, so the task is skipped rather than graded.

## Quirks

- The agent runs in the benchmark's working directory with mini-swe-agent's `local` environment, so its
  commands run directly in the sandbox. `run.py` clears `environment.cwd`, so the `/testbed` that
  `benchmarks/swebench.yaml` sets for Docker runs does not apply.
- That environment runs each command with `/bin/sh`, not bash.
- If a model is unknown to litellm, upstream stops with a cost-tracking error. Set
  `-k cost_tracking=ignore_errors` for such models (and `cost_limit` then cannot stop the run).
- API keys passed with `-s` are environment variables inside the sandbox, so the agent's own commands
  can read them.
- `setup.sh` also installs litellm's `mcp` extra. litellm 1.106 imports `mcp` on every request that
  carries tools (mini-swe-agent's always do) without declaring it as a dependency.

## Updating

```bash
uv run python scripts/bump_agent.py agents/mini_swe_agent
```

picks the newest upstream release that is at least seven days old, checks it out in the submodule and
rewrites `upstream.json`.
