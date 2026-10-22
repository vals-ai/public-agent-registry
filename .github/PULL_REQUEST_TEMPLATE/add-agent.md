# Contribute an Agent to the registry

## Agent details

- Agent name:
- Version:
- Agent directory: `agents/<agent-name>`
- Installation method and pinned native version:
- Source submodule (if needed): `agents/<agent-name>/upstream` or None
- Upstream repository link:

## Description

<!-- What agent is being added, what it runs, and what benchmark/task types it targets. -->

## Submission Checklist

- [ ] The agent is a self-contained directory under `agents/`.
- [ ] Native dependencies are pinned; any required source submodule is inside the agent directory.
- [ ] `contract.yaml` and `setup.sh` are included in the agent directory.
- [ ] The agent directory includes a `README.md` following the [shared format](../../templates/agent-README.md).
- [ ] The contract follows the [contract documentation](https://github.com/vals-ai/Valkyrie/blob/dev/docs/CONTRACTS.md).
- [ ] Agent has been tested out on [valkyrie](https://github.com/vals-ai/Valkyrie#start-a-run).

## Secrets

- Required secrets (if any):

<!-- List environment variable names only. Do not include secret values. -->

- [ ] No private keys, tokens, internal hostnames, or personal paths are committed.
- [ ] Secret values refer to secret names, not raw secret values. **ONLY USE REFERENCES**.

## Output

<!-- Example: summary.json, metrics_total.json, final_message.txt, trajectory.jsonl, raw_output.txt -->

- Final output path:
- Output files:

## Test it out

Commands to test through valkyrie:

Install agent

```bash
valkyrie agent install 'https://github.com/vals-ai/public-agent-registry/tree/REGISTRY_COMMIT_SHA/agents/AGENT_DIRECTORY'
```

Run agent

```bash
valkyrie run start --benchmark swebench --agent 'CONTRACT_AGENT_NAME' --concurrency 1 --slice 0:1
```

## Known Limitations / Issues

<!-- Anything reviewers or users should know before using this agent. -->
