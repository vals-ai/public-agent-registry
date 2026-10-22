# Agent Registry

This repository contains agent contracts that can be installed and run with
[Valkyrie](https://github.com/vals-ai/Valkyrie). Each agent directory defines how
to install an agent, run it against a benchmark task, and collect its output.

The registry is intended to be community-maintained. Community contributed
agents must be added under `agents/` as Git submodules. Valkyrie contract files
may live in the submodule itself or in a matching `contracts/<agent-name>/`
directory maintained in this registry.

## Repository Layout

- `agents/`: community contributed agents. Every agent here must be a Git
  submodule pointing to its public repository.
- `contracts/`: registry-maintained Valkyrie integrations for native upstream
  agents that do not include Valkyrie contract files.
- `examples/`: example contracts and reference implementations only.
- `CONTRIBUTING.md`: contribution workflow and review expectations.

## Agents

- [terminus2](agents/terminus2-v1.0.0): Terminus 2 terminal-based agent for
  containerized benchmark tasks.
- [mini_sweagent-v1.0.0](agents/mini_sweagent-v1.0.0): Mini SWE-agent
  for SWE-bench tasks, packaged with the public model library.

## Agent Directory Shape

Each installable contract directory should include:

- `contract.yaml`: Valkyrie contract. See the
  [contract documentation](https://github.com/vals-ai/Valkyrie/blob/dev/docs/CONTRACTS.md)
  for supported fields and examples.
- `README.md`: short usage notes, required secrets, supported models, and output
  files.
- `setup.sh`: install script used by `contract.yaml`.
- Any wrapper scripts needed to run the agent and collect outputs.

Use the shared [agent README template](templates/agent-README.md) for new
integrations. For native upstream agents, keep these files and the integration
README under `contracts/<agent-name>/`, alongside the source submodule at
`agents/<agent-name>`. This lets the integration use the original repository
without requiring an agent fork or a separate integration repository. Existing
submodules that include their own contracts remain supported.

## Using an Agent

Install an agent by pointing Valkyrie at the directory containing `contract.yaml`.
For registry-maintained integrations, use `contracts/<agent-name>`; for existing
self-contained agent submodules, use `agents/<agent-name>`:

```bash
valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/main/contracts/<agent-name>
```

Run a small slice with a benchmark to test:

```bash
valkyrie run start --benchmark swebench --agent '<agent-name>' --concurrency 1 --slice 0:1
```

Checkout the agent specific documentation to know what other options are available.

## Reference Agents

See `examples/` for working contracts:

- [codex-v1.0.0](examples/codex-v1.0.0/README.md)
- [claude_code-v1.0.0](examples/claude_code-v1.0.0/README.md)
- [mini_sweagent-v1.0.0](examples/mini_sweagent-v1.0.0/README.md)

These examples show common setup patterns, output collection, and README
structure.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. New
community agents must be added under `agents/` as submodules, include a valid
`contract.yaml` in the submodule or matching `contracts/` directory, and provide enough documentation for another user to install
and run the agent with Valkyrie.
