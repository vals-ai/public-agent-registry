# Agent Registry

This repository contains agent contracts that can be installed and run with
[Valkyrie](https://github.com/vals-ai/Valkyrie). Each agent directory defines how
to install an agent, run it against a benchmark task, and collect its output.

The registry is intended to be community-maintained. Community contributed
agents must be added under `agents/` as Git submodules and include the contract
files needed for Valkyrie to install and run them. Non-submodule agent
contributions will not be accepted.

## Repository Layout

- `agents/`: community contributed agents. Every agent here must be a Git
  submodule.
- `examples/`: example contracts and reference implementations only.
- `CONTRIBUTING.md`: contribution workflow and review expectations.

## Agents

- [terminus2](agents/terminus2-v1.0.0): Terminus 2 terminal-based agent for
  containerized benchmark tasks.
- [mini_sweagent-v1.0.0](agents/mini_sweagent-v1.0.0): Mini SWE-agent
  for SWE-bench tasks, packaged with the public model library.
- [proof_bench_agent-v1.0.0](agents/proof_bench_agent-v1.0.0): Lean theorem
  proving agent for ProofBench tasks.

## Agent Directory Shape

Each agent directory should include:

- `contract.yaml`: Valkyrie contract. See the
  [contract documentation](https://github.com/vals-ai/Valkyrie/blob/dev/docs/CONTRACTS.md)
  for supported fields and examples.
- `README.md`: short usage notes, required secrets, supported models, and output
  files.
- `setup.sh`: install script used by `contract.yaml`.
- Any wrapper scripts needed to run the agent and collect outputs.

Community agents are expected to live in their own repository and be added here
as submodules under `agents/`.

## Using an Agent

Install an agent by pointing Valkyrie at the agent directory:

```bash
valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/main/agents/<agent-name>
```

Run a small slice with a benchmark to test:

```bash
valkyrie run start --benchmark swebench --agent <agent-name> --concurrency 10 --slice :10
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
`contract.yaml`, and provide enough documentation for another user to install
and run the agent with Valkyrie.
