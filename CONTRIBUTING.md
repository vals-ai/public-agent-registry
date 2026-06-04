# Contributing

Thanks for contributing an agent to the registry. This repository is meant to
make agents easy to discover, install, run, and compare with Valkyrie.

## Add an Agent

Add contributed agents under `agents/` as Git submodules. Non-submodule agent
contributions will not be accepted. The reason for this is to simplify the review process and make it easier for you, the submitter to make changes. Maintaining multiple versions of an agent can be cumbersome, submodules are the best way to share without over-extending reviewers or yourself.

```bash
git submodule add https://github.com/<owner>/<agent-repo>.git agents/<agent-name>
git submodule update --init --recursive agents/<agent-name>
```

Use a stable, versioned directory name when publishing a release-style agent,
for example:

```text
agents/my_agent-v1.0.0
```

Inside the agent directory, include the Valkyrie contract files needed to run
the agent:

- `contract.yaml`
- `setup.sh`
- `README.md`

The goal is to allow users to install and run agents without needing to make any modifications.

## Contract Requirements

Create a `contract.yaml` file. See the
[contract documentation](https://github.com/vals-ai/Valkyrie/blob/dev/docs/CONTRACTS.md)
for supported fields and examples.

## README Requirements

Each agent README should include (to make the agent easy to use):

- Installation instructions
- Any secrets required to run the agent
- Usage through Valkyrie

### Example commands:

Install the agent

```bash
valkyrie agent install path/to/github/url/agents/<agent-name>
```

Agent usage with valkyrie

```bash
valkyrie run start --benchmark swebench --agent <agent-name> --concurrency 10 --slice :10
```

## Output Expectations

Outputs are optional but should be included so that users can find trajectories and metrics.

## Secrets and Private Data

Do not commit private keys, tokens, internal hostnames, private repository URLs,
or personal data. Contract secret values should refer to secret names, not raw
secret values.

Before opening a pull request, scan your agent directory for accidental private
or machine-local content.

## Before opening a pr

Before contributing, run through the process of how an external user would install and run your agent. Doing a pass before opening a pr will save time and ensure that everything is working.

Commands to test through valkyrie:

Install agent

```bash
valkyrie agent install path/to/github/url/agents/<agent-name>
```

Run agent

```bash
valkyrie run start --benchmark swebench --agent <agent-name> --concurrency 1 --slice :1
```

## Pull Requests

PR templates have been created to give a direction on what we are looking for.

- Contributing an agent to the registry -> [add-agent.md](.github/PULL_REQUEST_TEMPLATE/add-agent.md)
- Updating an agent -> [update-agent.md](.github/PULL_REQUEST_TEMPLATE/update-agent.md)