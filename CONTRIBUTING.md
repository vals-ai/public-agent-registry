# Contributing

Thanks for contributing an agent to the registry. This repository is meant to
make agents easy to discover, install, run, and compare with Valkyrie.

## Add an Agent

Add contributed agents under `agents/` as Git submodules. Non-submodule agent
contributions will not be accepted. Prefer the agent's original public upstream
repository and pin its commit. Valkyrie-specific files can be maintained in this
registry when the upstream does not include them.

```bash
git submodule add https://github.com/<owner>/<agent-repo>.git agents/<agent-name>
git submodule update --init --recursive agents/<agent-name>
```

Use a stable, versioned directory name when publishing a release-style agent,
for example:

```text
agents/my_agent-v1.0.0
```

Include the Valkyrie contract files either inside the agent submodule or in a
matching `contracts/<agent-name>/` directory in this registry:

- `contract.yaml`
- `setup.sh`
- `README.md`

For a native upstream integration, use this layout:

```text
agents/my_agent-v1.0.0/       # Git submodule of the original upstream
contracts/my_agent-v1.0.0/   # contract.yaml, setup.sh, README.md and adapter
```

Install the contract directory, not the upstream checkout. Keep the upstream
commit and the package or binary version installed by `setup.sh` aligned; record
both in the integration README and metadata. Native source stays in its own
submodule instead of being copied into the Valkyrie install bundle. No separate
integration repository is needed.

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

For new integrations, start from the shared
[agent README template](templates/agent-README.md). Keep its section order and
fill in the agent's native upstream/version, runtime requirements, configuration,
usage, outputs, validation, limitations, and license. Use `None` or
`Not applicable` where a section does not apply. Document only implemented
behavior and record checks that have actually run.

Keep the integration README alongside `contract.yaml` and `setup.sh`. For native
upstreams this is `contracts/<agent-name>/README.md`, maintained in the same PR
as the contract and source submodule pin. For self-contained integrations it
remains inside the agent submodule.

Distinguish the integration release from the native agent version. Document only
the options exposed by the Valkyrie contract, and label native-only CLI options
separately if included. Provide a one-task run example and use placeholders for
the user's secret-store names, never raw credentials.

### Example commands:

Install the agent

```bash
valkyrie agent install 'https://github.com/vals-ai/public-agent-registry/tree/main/contracts/AGENT_DIRECTORY'
```

Agent usage with valkyrie

```bash
valkyrie run start --benchmark swebench --agent 'CONTRACT_AGENT_NAME' --concurrency 1 --slice 0:1
```

## Output Expectations

Outputs are optional but should be included so that users can find trajectories and metrics.

## Secrets and Private Data

Do not commit private keys, tokens, internal hostnames, private repository URLs,
or personal data. Contract secret values should refer to secret names, not raw
secret values.

Before opening a pull request, scan your contract and agent directories for accidental private
or machine-local content.

## Before opening a pr

Before contributing, run through the process of how an external user would install and run your agent. Doing a pass before opening a pr will save time and ensure that everything is working.

Commands to test through valkyrie:

Install agent

```bash
valkyrie agent install 'https://github.com/vals-ai/public-agent-registry/tree/REGISTRY_COMMIT_SHA/contracts/AGENT_DIRECTORY'
```

Run agent

```bash
valkyrie run start --benchmark swebench --agent 'CONTRACT_AGENT_NAME' --concurrency 1 --slice 0:1
```

## Pull Requests

PR templates have been created to give a direction on what we are looking for.

- Contributing an agent to the registry -> [add-agent.md](.github/PULL_REQUEST_TEMPLATE/add-agent.md)
- Updating an agent -> [update-agent.md](.github/PULL_REQUEST_TEMPLATE/update-agent.md)
