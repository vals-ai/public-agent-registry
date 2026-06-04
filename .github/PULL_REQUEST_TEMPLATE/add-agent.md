# Contribute an Agent to the registry

## Agent details

- Agent name:
- Version:
- Submodule path: `agents/<agent-name>`
- Upstream repository link:

## Description

<!-- What agent is being added, what it runs, and what benchmark/task types it targets. -->

## Submission Checklist

- [ ] The agent is added under `agents/` as a Git submodule.
- [ ] `contract.yaml` is included.
- [ ] `README.md` is included that documents usage.
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
valkyrie agent install path/to/github/url/agents/<agent-name>
```

Run agent

```bash
valkyrie run start --benchmark swebench --agent <agent-name> --concurrency 1 --slice :1
```

## Known Limitations / Issues

<!-- Anything reviewers or users should know before using this agent. -->
