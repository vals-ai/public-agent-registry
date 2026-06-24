# Finance Agent v2

Valkyrie wrapper for the Finance Agent Benchmark v2 agent.

## Source

- Registry source: `vals-ai/agent-registry/fabv2_agent`
- Benchmark repository: https://github.com/vals-ai/finance-agent-v2

## Valkyrie Usage

```bash
valkyrie agent install path/to/public-agent-registry/agents/fabv2_agent
valkyrie run start --benchmark finance_agent_v2 --agent fabv2_agent --model <model> --concurrency 1 --slice :1
```

## Required Secrets

The contract declares model provider secrets via `prodBenchmarksInfraApiKeys`,
`MODEL_PROXY_SSH_KEY` from `model_proxy_ssh`, plus tool secrets for Tavily, SEC
EDGAR, and pricing data.

## Outputs

- Final output: `/app/results/valkyrie`
- Vals-format config and result artifacts are declared in `contract.yaml`.
