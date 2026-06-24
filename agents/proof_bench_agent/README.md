# Proof Bench Agent

Valkyrie wrapper for the Proof Bench theorem-proving agent.

## Source

- Registry source: `vals-ai/agent-registry/proof_bench_agent`
- Agent source: https://github.com/vals-ai/proof-bench

## Valkyrie Usage

```bash
valkyrie agent install path/to/public-agent-registry/agents/proof_bench_agent
valkyrie run start --benchmark proof_bench --agent proof_bench_agent --model <model> --concurrency 1 --slice :1
```

## Required Secrets

The contract declares model provider secrets via `prodBenchmarksInfraApiKeys` and
uses `MODEL_PROXY_SSH_KEY` from `model_proxy_ssh`.

## Outputs

- Final output: `/logs`
- Primary log: `/logs/proof_bench_agent.log`
- Result JSON: `/logs/result.json`
