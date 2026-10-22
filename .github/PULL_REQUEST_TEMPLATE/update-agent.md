# Update Agent

## Agent

- Agent name:
- Version before:
- Version after:
- Agent directory: `agents/<agent-name>`
- Installation method and pinned native version:
- Source submodule (if needed): `agents/<agent-name>/upstream` or None
- Upstream repository:

## Summary of changes

<!-- What changed and why. Include user-facing behavior changes. -->

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

## Review Notes

<!-- Anything specific reviewers should inspect closely. -->

## Validation

- [ ] Contract, setup and README remain together in a self-contained agent directory.
- [ ] Native dependencies are pinned; any required source submodule is inside the agent directory.
- [ ] Installation and a one-task Valkyrie run have been verified for this update.

<!-- Record checks performed, their results and supporting evidence. -->
