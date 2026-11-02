# Update Agent

## Agent

- Agent name:
- Upstream repository:
- Tag before:
- Tag after:

## Summary of changes

<!-- What changed and why. Include user-facing behavior changes. -->

## Checklist

- [ ] `upstream.json` matches the submodule (repo, tag and commit), and `checksums.txt` is refreshed if the agent has `assets`.
- [ ] `scripts/check_agents.py` passes.
- [ ] The new tag is the newest release that is at least seven days old, or the reason it is not is below.

## Test it out

Commands to test through valkyrie:

Install agent

```bash
valkyrie agent install https://github.com/<owner>/public-agent-registry/tree/<slash-free-branch>/agents/<agent-name> --name <agent-name>-test
```

Run agent

```bash
valkyrie run start --benchmark swebench --agent <agent-name>-test --model <model> -s ENV_VAR <secret-ref> --concurrency 1 --slice :1
```

## Review Notes

<!-- Anything specific reviewers should inspect closely. -->
