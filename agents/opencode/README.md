# opencode

[opencode](https://github.com/anomalyco/opencode) by Anomaly, run for Valkyrie exactly as upstream
ships it. The upstream repository is the `opencode/` git submodule, pinned to the release recorded in
`upstream.json` (`tag` and `commit`). Only `contract.yaml`, `setup.sh`, `run.sh`, `finish.sh`,
`checksums.txt` and this README are Vals-authored.

## Install

```bash
valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/main/agents/opencode
```

`setup.sh` downloads the release binary for the sandbox (`linux`, x64 or arm64, glibc or musl, and the
`-baseline` build on an x64 CPU without avx2, chosen the way upstream's install script chooses) from
the pinned GitHub release, and a static jq 1.8.2. Both are checked against the sha256 in
`checksums.txt` before they are used, and the installed `opencode --version` must equal the version
in the submodule's `packages/opencode/package.json`. Everything goes in `/opt/opencode/`, which is
not on `PATH`: the only thing the task's `PATH` gains is the `opencode-run` entry script, which works
from whatever folder Valkyrie copies the agent into. On Alpine it also installs `libstdc++` and
`libgcc`, which the musl build needs. It can be run again after a failed attempt.

## Run

The agent needs an API key for the model's provider. Pass it as a secret:

```bash
valkyrie run start --benchmark swebench --agent opencode \
  --model anthropic/claude-sonnet-4-6 -s ANTHROPIC_API_KEY <secret-ref> \
  -k variant high --concurrency 10 --slice :10
```

`--model` is opencode's `provider/model` form, for example `anthropic/claude-sonnet-4-6` or
`openai/gpt-5.4`, and `opencode models` lists them. Use the secret that provider expects
(`OPENAI_API_KEY`, `GEMINI_API_KEY`, ...).

| Kwarg (`-k name value`) | Default | Meaning |
| --- | --- | --- |
| `variant` | empty | The provider's reasoning effort (`--variant`, for example `high`). Empty keeps the provider default. |

The agent runs `opencode run --auto --format json` in the benchmark's working directory, with the
task on stdin. `--auto` approves every permission request that is not explicitly denied, so the agent
can run commands and edit files in the sandbox without asking.

## Outputs

Written to `/logs/opencode/` and collected as `opencode/`:

- `session.json`: the whole session (messages, tool calls and results), from `opencode export`. It is
  not sanitized, so it holds the task text. It is missing if the run never started a session.
- `summary.json`: `agent`, `upstream` (the contents of `upstream.json`), `outcome` (`completed`,
  `error` or `killed`), `stop_reason` (the same word) and `agent_exit_code`. It is written even when
  the run fails.

`events.jsonl` (opencode's JSON event stream) and `stderr.log` stay in `/logs/opencode/` too.

The run exits 0 when opencode stops on its own. If opencode is killed (exit code 137) the run exits
137 with no error line. Any other ending exits with opencode's code and a one-line
`AgentError: opencode exited with code N (ErrorName)` for Valkyrie, so the task is skipped rather than
graded. `ErrorName` is the name of the last error event (for example `ProviderAuthError`) and is left
out when there is none; the event's message is never copied, since it can quote the task.

## Quirks

- `run.sh` sets one environment flag, `OPENCODE_DISABLE_AUTOUPDATE=1`, so the version that runs is the
  pinned one. Nothing else about opencode is changed: the task repo's own `opencode.json`, `.opencode/`
  folder and `AGENTS.md`/`CLAUDE.md` apply exactly as they would if you ran opencode there locally, and
  opencode's built-in provider plugins are loaded.
- `OPENCODE_DISABLE_MODELS_FETCH` is not set, so opencode still fetches its model list from
  models.dev on a fresh `HOME`. Whether a run resolves the model without that fetch was not checked.
- API keys passed with `-s` are environment variables inside the sandbox, so the agent's own commands
  can read them.
- The task goes to opencode on stdin, not as an argument, so its size is not limited by the command
  line and it does not appear in the process list.
- The install was checked on Debian (glibc) and Alpine (musl), arm64 natively and x64 under emulation
  (which has no avx2, so it used the `-baseline` build). The agent was run end to end only against a
  stand-in model server, not a real provider.

## Updating

```bash
uv run python scripts/bump_agent.py agents/opencode
```

picks the newest `v1.*` upstream release that is at least seven days old, checks it out in the
submodule, rewrites `upstream.json` and refreshes the sha256 lines in `checksums.txt`. When the release
has no checksum file, the six Linux tarballs (about 80 MB each) are downloaded and hashed. The jq lines
in `checksums.txt` are kept.
