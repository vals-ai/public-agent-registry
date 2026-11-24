# Agent Registry

This repository contains agent contracts that can be installed and run with
[Valkyrie](https://github.com/vals-ai/Valkyrie). Each agent directory defines how
to install an agent, run it against a benchmark task, and collect its output.

The registry is intended to be community-maintained. Agents here run as their
upstream projects ship them: an agent is a folder with its contract, and the
upstream code is a git submodule inside it, pinned to a release tag.

## Agents

| Agent | Upstream | Description |
| --- | --- | --- |
| [`claude_code`](agents/claude_code/README.md) | [anthropics/claude-code](https://github.com/anthropics/claude-code) | Claude Code in headless mode, installed with its official installer. |
| [`codex`](agents/codex/README.md) | [openai/codex](https://github.com/openai/codex) | The Codex CLI in exec mode, installed from npm. |
| [`mini_swe_agent`](agents/mini_swe_agent/README.md) | [SWE-agent/mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) | The minimal AI software engineering agent from the SWE-agent team. |
| [`opencode`](agents/opencode/README.md) | [anomalyco/opencode](https://github.com/anomalyco/opencode) | The open source AI coding agent, installed from its release binary. Follows the 1.x line. |
| [`pi`](agents/pi/README.md) | [earendil-works/pi](https://github.com/earendil-works/pi) | A minimal, extensible agent harness, run in print mode from its release binary. |
| [`terminus2`](agents/terminus2/README.md) | [harbor-framework/harbor](https://github.com/harbor-framework/harbor) | Terminus 2, the terminal agent built into Harbor, which works through a tmux session. Built for Terminal-Bench. |

Each agent's `agents/<agent-name>/upstream.json` holds its registry `version` and, for agents
with a submodule, the upstream `repo`, `tag` and `commit`.
Each agent's README lists its secrets, model names, kwargs and output files.

## Repository Layout

- `agents/`: the agents above. Each is a folder holding its Valkyrie contract and
  wrapper scripts, with the upstream repository as a submodule inside it.
- `scripts/`: `check_agents.py` verifies every agent folder.
- `CONTRIBUTING.md`: contribution workflow and review expectations.

## Agent Directory Shape

```text
agents/<agent-name>/
  contract.yaml     # Valkyrie contract
  setup.sh          # install script used by contract.yaml
  <wrapper>         # run.sh, run.py, ...: adapts the task to the agent and collects its output
  README.md         # usage notes, required secrets, supported models, output files
  upstream.json     # registry version, plus repo, tag and commit of the pinned upstream release
  checksums.txt     # only for agents that download release assets: their sha256
  <submodule>/      # the upstream repository, a shallow HTTPS submodule at the pinned tag
```

See the [contract documentation](https://github.com/vals-ai/Valkyrie/blob/dev/docs/CONTRACTS.md)
for the fields `contract.yaml` supports. Every pull request is checked against
`upstream.json` and the upstream tags (see [CONTRIBUTING.md](CONTRIBUTING.md#checks)).

## Using an Agent

Install an agent by name. Valkyrie picks its highest release, or the one after `@`:

```bash
valkyrie agent install <agent-name>
valkyrie agent install <agent-name>@<version>
```

Each release is a git tag `<agent-name>/v<version>`, made when `version` in `upstream.json`
changes on `main`. Release tags never move, and Valkyrie installs the commit the tag points at.
A full URL such as `https://github.com/vals-ai/public-agent-registry/tree/main/agents/<agent-name>`
also works.

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
`-k config benchmarks/swebench.yaml` on SWE-bench, and `terminus2` was built for
Terminal-Bench (`--benchmark terminal-bench --dataset terminal-bench-2.1`). Check the
agent specific documentation to know what other options are available.

## What a Run Records

Every run writes a `summary.json` into the agent's output folder, next to its
trajectory. It holds the agent name, the outcome, the stop reason, the agent's exit
code, and `upstream`: the contents of the agent's `upstream.json`, so it names the
upstream repo, tag and commit that ran, whatever name the agent was installed under.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. New agents
are added under `agents/` as a folder with a valid `contract.yaml`, a wrapper, and
the upstream repository as a submodule inside it, pinned to a release tag. They need
enough documentation for another user to install and run the agent with Valkyrie.
