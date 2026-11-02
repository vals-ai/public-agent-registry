# Agent Registry

This repository contains agent contracts that can be installed and run with
[Valkyrie](https://github.com/vals-ai/Valkyrie). Each agent directory defines how
to install an agent, run it against a benchmark task, and collect its output.

The registry is intended to be community-maintained. Agents here run as their
upstream projects ship them: an agent is a folder with its contract, and the
upstream code is a git submodule inside it, pinned to a release tag.

## Agents

| Agent | Upstream | Pinned tag | Description |
| --- | --- | --- | --- |
| [`mini_swe_agent`](agents/mini_swe_agent/README.md) | [SWE-agent/mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) | `v2.4.6` | The minimal AI software engineering agent from the SWE-agent team. |
| [`opencode`](agents/opencode/README.md) | [anomalyco/opencode](https://github.com/anomalyco/opencode) | `v1.19.4` | The open source AI coding agent, installed from its release binary. Follows the 1.x line. |
| [`pi`](agents/pi/README.md) | [earendil-works/pi](https://github.com/earendil-works/pi) | `v1.4.0` | A minimal, extensible agent harness, run in print mode from its release binary. |
| [`terminus2`](agents/terminus2/README.md) | [harbor-framework/harbor](https://github.com/harbor-framework/harbor) | `v0.25.0` | Terminus 2, the terminal agent built into Harbor, which works through a tmux session. Built for Terminal-Bench. |

The pinned tag of each agent is in its `upstream.json`, together with the commit.
Each agent's README lists its model names, kwargs, outputs and quirks.

## Repository Layout

- `agents/`: the agents above. Each is a folder holding its Valkyrie contract and
  wrapper scripts, with the upstream repository as a submodule inside it.
- `examples/`: example contracts and reference implementations only.
- `scripts/`: `check_agents.py` verifies every agent folder, and `bump_agent.py`
  moves an agent's pin to a newer upstream release.
- `CONTRIBUTING.md`: contribution workflow and review expectations.

## Agent Directory Shape

```text
agents/<agent-name>/
  contract.yaml     # Valkyrie contract
  setup.sh          # install script used by contract.yaml
  <wrapper>         # run.sh, run.py, ...: adapts the task to the agent and collects its output
  README.md         # usage notes, required secrets, supported models, output files
  upstream.json     # repo, tag and commit of the pinned upstream release
  checksums.txt     # only for agents that download release assets: their sha256
  <submodule>/      # the upstream repository, a shallow HTTPS submodule at the pinned tag
```

See the [contract documentation](https://github.com/vals-ai/Valkyrie/blob/dev/docs/CONTRACTS.md)
for the fields `contract.yaml` supports. A weekly workflow opens one pull request
per agent when upstream has a newer release that is at least seven days old, and
every pull request is checked against `upstream.json` and the upstream tags.

## Using an Agent

<!-- TODO(min-valkyrie-version): first release with scoped submodule fetch + symlink skipping -->
Requires Valkyrie CLI ≥ vX.Y.Z: an older CLI clones every agent's upstream
repository in full on each install, and cannot bundle the agents whose upstream
repositories contain symlinks (opencode and terminus2).

Install an agent by pointing Valkyrie at the agent directory:

```bash
valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/main/agents/<agent-name>
```

Run a small slice with a benchmark to test. The agent reads its model provider's
API key from an environment variable, which you pass with
`-s ENV_VAR <secret-ref>`:

```bash
valkyrie run start --benchmark swebench --agent <agent-name> \
  --model anthropic/claude-sonnet-4-6 -s ANTHROPIC_API_KEY <secret-ref> \
  --concurrency 10 --slice :10
```

`<secret-ref>` is your Valkyrie secret that holds the key. Use the variable your
model's provider expects (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, ...). The key is an
environment variable in the sandbox, so the agent's own commands can read it.

Some agents need more than this. `mini_swe_agent` wants
`-k config=benchmarks/swebench.yaml` on SWE-bench, and `terminus2` was built for
Terminal-Bench (`--benchmark terminal-bench --dataset terminal-bench-2.1`). Check the
agent specific documentation to know what other options are available.

## What a Run Records

Every run writes a `summary.json` into the agent's output folder, next to its
trajectory. It holds the agent name, the outcome, the stop reason, the agent's exit
code, and `upstream`: the contents of the agent's `upstream.json`, so it names the
upstream repo, tag and commit that ran, whatever name the agent was installed under.

## Reference Agents

See `examples/` for working contracts:

- [codex-v1.0.0](examples/codex-v1.0.0/README.md)
- [claude_code-v1.0.0](examples/claude_code-v1.0.0/README.md)

These examples show common setup patterns, output collection, and README
structure.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. New agents
are added under `agents/` as a folder with a valid `contract.yaml`, a wrapper, and
the upstream repository as a submodule inside it, pinned to a release tag. They need
enough documentation for another user to install and run the agent with Valkyrie.
