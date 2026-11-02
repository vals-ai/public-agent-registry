# Contribute an Agent to the registry

## Agent details

- Agent name: <!-- the folder name under `agents/` and the contract's `name` -->
- Upstream repository: <!-- https://github.com/<owner>/<repo> -->
- Pinned tag: <!-- the release tag in `upstream.json`; the newest release at least seven days old -->

## Description

<!-- What agent is being added, what it runs, and what benchmark/task types it targets. -->

## Submission Checklist

- [ ] The agent is a folder under `agents/` with the upstream repository as an HTTPS submodule inside it.
- [ ] `upstream.json` matches the submodule (repo, tag and commit).
- [ ] `scripts/check_agents.py` passes.
- [ ] The pinned tag is the newest upstream release that is at least seven days old.
- [ ] The wrapper only adapts input and output: no changes to the agent's prompts, tools, loops or limits, and no patches to the submodule.
- [ ] `contract.yaml` is included, with `name` equal to the folder name.
- [ ] `README.md` is included that documents usage.
- [ ] The contract follows the [contract documentation](https://github.com/vals-ai/Valkyrie/blob/dev/docs/CONTRACTS.md).
- [ ] Every run writes `summary.json` with the `upstream` contents, and the exit codes follow [CONTRIBUTING.md](https://github.com/vals-ai/public-agent-registry/blob/main/CONTRIBUTING.md#summary-and-exit-codes).
- [ ] Agent has been tested out on [valkyrie](https://github.com/vals-ai/Valkyrie#start-a-run), from a branch whose name has no slash.

## Secrets

- Required secrets (if any):

<!-- List environment variable names only. Do not include secret values. -->

- [ ] No private keys, tokens, internal hostnames, or personal paths are committed.
- [ ] The contract has no `secrets` block. Users pass their keys with `-s ENV_VAR <secret-ref>`, and no secret values are committed.

## Output

<!-- Example: summary.json, trajectory.json, session.jsonl, final_message.txt -->

- Final output path:
- Output files:

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

## Known Limitations / Issues

<!-- Anything reviewers or users should know before using this agent. -->
