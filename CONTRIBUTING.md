# Contributing

Thanks for contributing an agent to the registry. This repository is meant to
make agents easy to discover, install, run, and compare with Valkyrie.

Agents here run as their upstream projects ship them. An agent is a folder with
its Valkyrie contract and a small wrapper, and the upstream repository is a git
submodule inside that folder, pinned to a release tag. We do not keep forks or
patch upstream code.

## Add an Agent

### Folder layout

Each agent lives in `agents/<agent-name>/`:

```text
agents/<agent-name>/
  contract.yaml     # Valkyrie contract
  setup.sh          # install script used by contract.yaml
  <wrapper>         # run.sh, run.py, ...: adapts the task to the agent and collects its output
  README.md         # usage notes, required secrets, supported models, output files
  upstream.json     # repo, tag and commit of the pinned upstream release
  checksums.txt     # only if setup.sh downloads release assets: their sha256
  <submodule>/      # the upstream repository, pinned to the release tag
```

The folder name is the contract's `name`. It does not carry a version, because the
version is the pin in `upstream.json`: use `mini_swe_agent`, not `mini_swe_agent-v1.0.0`.
Valkyrie keys an agent by its name, and installing under an existing name replaces that
agent, so a name never changes when the pin does.

### Add the upstream repository

Add the upstream repository as a shallow submodule inside the agent folder, over HTTPS
(Valkyrie's installer rejects any other URL), then pin it to a release tag:

```bash
git submodule add --depth 1 https://github.com/<owner>/<repo>.git agents/<agent-name>/<submodule>
git config -f .gitmodules submodule.agents/<agent-name>/<submodule>.shallow true
printf '{\n  "repo": "<owner>/<repo>",\n  "tag": "",\n  "commit": "",\n  "submodule": "<submodule>"\n}\n' > agents/<agent-name>/upstream.json
uv run python scripts/bump_agent.py agents/<agent-name> --pin <tag>
git add .gitmodules agents/<agent-name>
uv run python scripts/check_agents.py
```

`<submodule>` is the folder name you chose for the checkout, usually the repository's name.
Do not set `branch =` in `.gitmodules`: the pin is what makes an install reproducible.
`--pin` checks the tag out in the submodule and fills in `tag` and `commit` in
`upstream.json` (and `checksums.txt`, see `assets` below). It stages nothing, so you
`git add` the result.

If the agent is a module inside a larger project (Terminus 2 is part of Harbor), the
upstream repository is the whole project and the wrapper imports the part it needs.

### upstream.json

`upstream.json` records what the folder runs. The wrapper copies it into every run's
`summary.json`, because Valkyrie's upload drops `.git` and the submodule's commit cannot
be read inside the sandbox.

| Field | Required | Meaning |
| --- | --- | --- |
| `repo` | yes | The upstream GitHub repository, `owner/name`. |
| `tag` | yes | The pinned release tag, a plain version such as `v1.2.3` so that `bump_agent.py` can compare it. |
| `commit` | yes | The 40-character commit the tag points at. It must equal the submodule's pinned commit. |
| `submodule` | yes | Path of the submodule inside the agent folder, relative. |
| `track` | no | Only releases whose tag starts with this are considered, for example `"v1."` keeps opencode on 1.x while 2.x exists. Without it, only releases with the current tag's major version count. |
| `assets` | no | Release asset file names that `setup.sh` downloads. Each needs a `<sha256>  <file name>` line in `checksums.txt`, which `--pin` writes from the release's `SHA256SUMS` (or `sha256sum.txt`, or by downloading and hashing the asset). Other lines, such as a static `jq`, are kept. |

`scripts/check_agents.py` fails if `upstream.json` is malformed, if its commit differs
from the submodule's, if the tag does not resolve to that commit upstream, if the
submodule URL is not `https://github.com/<repo>`, or if an asset has no checksum line.
It also fails on any submodule that is not an agent's `agents/<agent>/<submodule>`, and
on any `.gitmodules` URL that is not `https://github.com/<owner>/<repo>`.

### Pick a release at least seven days old

Pin the newest upstream release that is at least seven days old. This is the same
seven-day aging the repository applies to Python packages (`exclude-newer`), and it keeps
a bad release from reaching the registry before upstream has noticed it. Drafts and
prereleases never count. `bump_agent.py` applies the rule for you when it picks a release,
but `--pin` takes any tag, so check the release date yourself when you pin by hand.

### The wrapper adapts input and output only

A wrapper turns the task file into the agent's prompt, picks the non-interactive flags,
and copies the agent's own logs to `/logs`. It does not change how the agent behaves:
prompts, tools, step loops and limits stay at upstream's defaults unless the user passes a
kwarg. Do not patch the submodule. An environment variable the wrapper sets should only
switch off something that breaks a non-interactive run or changes which version runs (an
auto-update, a version check, a first-run wizard).

### setup.sh

- Valkyrie copies the agent to `/bundle/<library name>/`, and `valkyrie agent install --name`
  can change that name, so never hardcode the folder. `setup.sh` records `$PWD` and writes an
  entry script, `/usr/local/bin/<agent>-run`, that `run_cmd` calls by name.
- Install into `/opt/<agent>` or a venv there, not into the task's own `PATH` or Python,
  and run the agent by absolute path, so the agent's own `python` commands still hit
  the task's interpreter.
- Make it safe to run again: Valkyrie retries a failed install in the same sandbox.
- Check anything you download against a pinned sha256 (`checksums.txt`, or the digest of a
  pinned installer). Python installs pass `--exclude-newer "7 days"`, unless they install
  from the upstream project's own lock file, which already fixes every version: Terminus 2
  runs `uv sync --frozen` on Harbor's `uv.lock` instead.
- `install_cmd` gets ten minutes. A bundle can hold at most 1 GB, 5 GB unpacked and 100,000
  files, and symlinks in it are left out of the upload.

## Contract Requirements

Create a `contract.yaml` file. See the
[contract documentation](https://github.com/vals-ai/Valkyrie/blob/dev/docs/CONTRACTS.md)
for supported fields and examples.

- `name` is the folder name.
- `defaults.model` is required, written in the agent's own model syntax. The README gives
  an example for the common providers.
- `final_output` is usually `/logs/<agent>`. Terminus 2 uses `/logs/agent`, because Harbor
  hardcodes that folder. `output_artifacts` lists the trajectory and `summary.json` so they
  can be read without extracting the archive.
- Do not add a `secrets` block. Users pass their own keys with
  `-s ENV_VAR <secret-ref>`, and the README names the variables the agent reads.

## Summary and Exit Codes

Every run writes `summary.json` into the agent's output folder, even when the run fails:

```json
{
  "agent": "<agent-name>",
  "upstream": {"repo": "...", "tag": "...", "commit": "...", "submodule": "..."},
  "outcome": "completed",
  "stop_reason": "...",
  "agent_exit_code": 0
}
```

`upstream` is the contents of `upstream.json`, `outcome` is `completed`, `error` or
`killed`, and `stop_reason` is the agent's own word for why it stopped.

Valkyrie skips grading a task when the run exits with any code other than 0 or 137, so the
exit code decides whether the sandbox is graded:

- The agent ran and stopped on its own (it submitted, hit a step, turn or cost limit, or
  was cut off at its output limit): exit 0, so the sandbox is graded. Put the stop reason in
  `summary.json`.
- The agent was killed (137): exit 137.
- The agent could not really run (a bad or missing API key, an unknown model, a crash): write
  one line starting with `AgentError: ` to `$VALKYRIE_ERROR_PATH`, for example
  `AgentError: <agent> <ExceptionClass>`, and exit nonzero. Never put the task, a prompt or
  model output in that line, and copy only error names, not messages.

## README Requirements

Each agent README covers usage only; how the wrapper works belongs in its code and in this
guide. It includes:

- What the agent is, with a link to its upstream project
- Configuration: the secrets it reads (passed as `-s ENV_VAR <secret-ref>`), the model name
  format with an example, the final output path, the kwargs, and any constraint that changes
  how it is used (for example, a glibc-based task image)
- Usage through Valkyrie: the install and run commands
- The output files

The README does not repeat the pinned tag: `upstream.json` records it.

### Example commands:

Install the agent

```bash
valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/main/agents/<agent-name>
```

Agent usage with valkyrie

```bash
valkyrie run start --benchmark swebench --agent <agent-name> --model <model> \
  -s ENV_VAR <secret-ref> --concurrency 10 --slice :10
```

## Secrets and Private Data

Do not commit private keys, tokens, internal hostnames, private repository URLs,
or personal data. The contract has no `secrets` block (`check_agents.py` rejects it), and
nothing in the folder may point at a private repository, a private registry or a
Vals-internal service.

Before opening a pull request, scan your agent directory for accidental private
or machine-local content.

## Checks

```bash
uv sync
uv run python scripts/check_agents.py            # --offline skips the upstream tag lookup
```

`check-agents.yml` runs this on every pull request, except the bump pull requests
described below: a pull request opened with the workflow's `GITHUB_TOKEN` does not trigger
other workflows, so the bump workflow runs `check_agents.py` itself. If `check-agents.yml` is a
required check on `main`, a maintainer has to run it on a bump pull request, for example by
closing and reopening the pull request. Pushing a commit to it runs the check too, but then
the bot stops updating the branch (see below).

## Updating an Agent

`scripts/bump_agent.py` moves the pin of one agent:

```bash
uv run python scripts/bump_agent.py agents/<agent-name> --dry-run   # report only
uv run python scripts/bump_agent.py agents/<agent-name>             # newest eligible release
uv run python scripts/bump_agent.py agents/<agent-name> --pin v1.2.3
```

It prints one JSON line, `{"agent", "from", "to", "newer_major"}`. `to` is the tag it picked,
or null when the pin is current. `newer_major` is the newest release at least seven days old
on a higher major version, which the script never moves to by itself. Set `GITHUB_TOKEN` to
get higher GitHub API rate limits. The script checks the tag out in the submodule and rewrites
`upstream.json` and `checksums.txt`, but stages nothing: `git add agents/<agent-name>`, run
`scripts/check_agents.py`, and commit.

Every Monday the `bump-agents.yml` workflow runs the script for each agent. When there is a
newer release, a read-only job runs `check_agents.py` on the bump, and a second job, the only
one with write access and one that never runs upstream code, opens (or updates) a pull request
from the branch `bump-<agent-name>`, with a smoke-test checklist. When the only newer release is
a new major version, it opens an issue instead, one per agent, because that move is a human
decision; later runs edit that issue to name the newest major version. A bump pull request
changes the pin only: the contract's `name` stays the same.

While a bump pull request is open, the workflow rebuilds its branch from `main` only as long
as the branch holds nothing but the bot's own commits. Once you push a commit to it (a wrapper
fix, say), later runs leave the branch alone and only refresh the description, which then
names any newer release. Merge or close the pull request to let the bot move on.

## Before opening a pr

Before contributing, run through the process of how an external user would install and run your agent. Doing a pass before opening a pr will save time and ensure that everything is working.

Valkyrie's tree URL parser rejects branch names that contain a slash, so test from a branch
whose name has none. Push your work to one, then install it the way an outside user would,
with no GitHub credentials: the variables below keep git from using your saved credentials
and config, and `--name` keeps the test install from replacing an agent you already have:

```bash
git push origin <your-branch>:<agent-name>-test
env -u GH_TOKEN -u GITHUB_TOKEN GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0 \
  valkyrie agent install https://github.com/<owner>/public-agent-registry/tree/<agent-name>-test/agents/<agent-name> --name <agent-name>-test
```

Then run one task:

```bash
valkyrie run start --benchmark swebench --agent <agent-name>-test --model <model> \
  -s ENV_VAR <secret-ref> --concurrency 1 --slice :1
```

`valkyrie run results RUN_ID` should show a graded task, and `valkyrie run artifacts RUN_ID`
should list the trajectory and a `summary.json` that names the pinned tag and commit. Also
run once with an invalid API key: `valkyrie run errors RUN_ID` should show your one-line
`AgentError: ...` reason. If the agent has a limit you can set to something tiny (a step or
turn limit), check that the task is still graded.

## Pull Requests

PR templates have been created to give a direction on what we are looking for.

- Contributing an agent to the registry -> [add-agent.md](.github/PULL_REQUEST_TEMPLATE/add-agent.md)
- Updating an agent -> [update-agent.md](.github/PULL_REQUEST_TEMPLATE/update-agent.md)
