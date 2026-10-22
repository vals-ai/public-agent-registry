# Agent Registry

This repository contains agent contracts that can be installed and run with
[Valkyrie](https://github.com/vals-ai/Valkyrie). Each versioned directory under
`agents/` is a complete installable integration: its contract, setup, README,
and any adapter or required source live together.

The registry is intended to be community-maintained. Integrations use the
agent's original public packages, releases, or source repositories.

## Repository Layout

- `agents/`: self-contained agent integrations. Existing integrations supplied
  as Git submodules are also supported.
- `examples/`: example contracts and reference implementations only.
- `templates/agent-README.md`: standard README format for agent integrations.
- `CONTRIBUTING.md`: contribution workflow and review expectations.

## Agents

- [terminus2](agents/terminus2-v1.0.0): Terminus 2 terminal-based agent for
  containerized benchmark tasks.
- [mini_sweagent-v1.0.0](agents/mini_sweagent-v1.0.0): Mini SWE-agent
  for SWE-bench tasks, packaged with the public model library.
- [OpenCode v1.0.0](agents/opencode-v1.0.0/README.md): native upstream `1.19.3` with a Valkyrie integration.

## Agent Directory Shape

Each installable directory should include:

- `contract.yaml`: Valkyrie contract. See the
  [contract documentation](https://github.com/vals-ai/Valkyrie/blob/dev/docs/CONTRACTS.md)
  for supported fields and examples.
- `README.md`: usage, required secrets, supported models, output files and
  validation, following the [shared template](templates/agent-README.md).
- `setup.sh`: install script used by `contract.yaml`.
- Any adapter scripts and dependency metadata needed to install and run the agent.

Prefer a pinned upstream package or release when available. If the integration
needs an upstream source checkout, place it in a nested Git submodule such as
`agents/my_agent-v1.0.0/upstream/`. Keep everything needed to build the install
bundle within the agent directory. A source submodule is optional.

## Using an Agent

Install an agent by pointing Valkyrie at its directory containing `contract.yaml`:

```bash
valkyrie agent install 'https://github.com/vals-ai/public-agent-registry/tree/main/agents/<agent-name>'
```

Run a small slice with a benchmark to test:

```bash
valkyrie run start --benchmark swebench --agent '<agent-name>' --concurrency 1 --slice 0:1
```

Check the agent's README for supported benchmarks, model options and secrets.

## Reference Agents

See `examples/` for working contracts:

- [codex-v1.0.0](examples/codex-v1.0.0/README.md)
- [claude_code-v1.0.0](examples/claude_code-v1.0.0/README.md)
- [mini_sweagent-v1.0.0](examples/mini_sweagent-v1.0.0/README.md)

These examples show common setup patterns, output collection, and README
structure.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Add a
self-contained directory under `agents/` with a valid `contract.yaml`, setup,
and enough documentation for another user to install and run it with Valkyrie.
