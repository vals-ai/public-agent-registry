# Contributing

Thanks for contributing an agent to the registry. This repository is meant to
make agents easy to discover, install, run, and compare with Valkyrie.

## Add an Agent

Add a self-contained, versioned directory under `agents/`. Keep the Valkyrie
contract, setup, README and adapter together so that directory can be installed
on its own:

```text
agents/my_agent-v1.0.0/
  contract.yaml
  setup.sh
  README.md
  ...                       # adapter and pinned dependency metadata as needed
  upstream/                 # optional source submodule, only when needed
```

Prefer installing an exact version of the agent's original public package or
prebuilt release from `setup.sh`. Include dependency lockfiles or release
checksums as appropriate, and record the native version and repository in the
README and integration metadata. A package-based integration does not need a
source submodule or a separate integration repository.

If setup needs the upstream source, add it as a nested submodule inside the
agent directory and pin the required commit:

```bash
git submodule add https://github.com/<owner>/<agent-repo>.git agents/my_agent-v1.0.0/upstream
git -C agents/my_agent-v1.0.0/upstream checkout <upstream-commit>
git add agents/my_agent-v1.0.0/upstream .gitmodules
```

Ensure required submodules are initialized and their source is included when
building the install bundle. Do not depend on sibling directories elsewhere in
the registry. Existing agent submodules that already contain their own contract,
setup and README remain supported.

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

Keep the integration README at `agents/<agent-name>/README.md`, alongside
`contract.yaml` and `setup.sh`. Maintain these files in the same PR as the
package pin or optional nested source submodule.

Distinguish the integration release from the native agent version. Document only
the options exposed by the Valkyrie contract, and label native-only CLI options
separately if included. Provide a one-task run example and use placeholders for
the user's secret-store names, never raw credentials.

### Example commands

Install the agent:

```bash
valkyrie agent install 'https://github.com/vals-ai/public-agent-registry/tree/main/agents/AGENT_DIRECTORY'
```

Run through Valkyrie:

```bash
valkyrie run start --benchmark swebench --agent 'CONTRACT_AGENT_NAME' --concurrency 1 --slice 0:1
```

## Output Expectations

Outputs are optional but should be included so that users can find trajectories and metrics.

## Secrets and Private Data

Do not commit private keys, tokens, internal hostnames, private repository URLs,
or personal data. Contract secret values should refer to secret names, not raw
secret values.

Before opening a pull request, scan your agent directory for accidental private
or machine-local content.

## Validation Before Review

Follow the installation and run process an external user would use. Verify the
complete agent directory can be bundled, installed and run through Valkyrie.
Record the checks performed and their results in the PR description.

Install the candidate registry commit:

```bash
valkyrie agent install 'https://github.com/vals-ai/public-agent-registry/tree/REGISTRY_COMMIT_SHA/agents/AGENT_DIRECTORY'
```

Run one task:

```bash
valkyrie run start --benchmark swebench --agent 'CONTRACT_AGENT_NAME' --concurrency 1 --slice 0:1
```

## Pull Requests

Use the appropriate template to describe the integration and its validation:

- Contributing an agent to the registry -> [add-agent.md](.github/PULL_REQUEST_TEMPLATE/add-agent.md)
- Updating an agent -> [update-agent.md](.github/PULL_REQUEST_TEMPLATE/update-agent.md)
