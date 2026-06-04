# Update Agent

## Agent

- Agent name:
- Version before:
- Version after:
- Submodule path: `agents/<agent-name>`
- Upstream repository:

## Summary of changes

<!-- What changed and why. Include user-facing behavior changes. -->

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

## Review Notes

<!-- Anything specific reviewers should inspect closely. -->
