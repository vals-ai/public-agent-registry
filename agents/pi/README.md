# pi

[pi](https://github.com/earendil-works/pi) by Earendil Works, run for Valkyrie exactly as upstream
ships it. The upstream repository is the `pi/` git submodule, pinned to the release recorded in
`upstream.json` (`tag` and `commit`). Only `contract.yaml`, `setup.sh`, `run.sh`, `finish.sh`,
`checksums.txt` and this README are Vals-authored.

## Install

```bash
valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/main/agents/pi
```

`setup.sh` downloads the release tarball for the sandbox (`pi-linux-x64.tar.gz` or
`pi-linux-arm64.tar.gz`) from the pinned GitHub release, and a static jq 1.8.2. Both are checked
against the sha256 in `checksums.txt` before they are used, and the installed `pi --version` must
equal the version in the submodule's `packages/coding-agent/package.json`. Everything goes in
`/opt/pi/`, which is not on `PATH`: the tarball's `pi/` folder (the executable and the files it loads
from beside itself) is kept whole at `/opt/pi/pi/`, and the only thing the task's `PATH` gains is the
`pi-run` entry script, which works from whatever folder Valkyrie copies the agent into. It can be run
again after a failed attempt.

pi's release binaries are linked against glibc. On a musl image (Alpine) `setup.sh` installs nothing
and exits 1 with `pi's release binaries need glibc; this image uses musl`, so use a Debian- or
Ubuntu-based image.

## Run

The agent needs an API key for the model's provider. Pass it as a secret:

```bash
valkyrie run start --benchmark swebench --agent pi \
  --model anthropic/claude-sonnet-4-6 -s ANTHROPIC_API_KEY <secret-ref> \
  -k thinking high --concurrency 10 --slice :10
```

`--model` is `provider/id`, for example `anthropic/claude-sonnet-4-6`, `deepseek/deepseek-v4-pro` or
`openrouter/deepseek/deepseek-chat`, and `pi --list-models` lists them. The wrapper splits it on the
first `/` into pi's `--provider` and `--model`; passed whole, pi would match an id such as
`deepseek/deepseek-chat` against OpenRouter's models instead. Use the secret that provider expects
(`OPENAI_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, ...).

| Kwarg (`-k name value`) | Default | Meaning |
| --- | --- | --- |
| `thinking` | empty | pi's thinking level (`--thinking`): `off`, `minimal`, `low`, `medium`, `high`, `xhigh` or `max`. Empty keeps pi's default, `medium`. pi clamps the level to what the model supports, and ignores a value that is not one of these with a warning. |

The agent runs `pi -p` (print mode) in the benchmark's working directory with pi's own defaults: its
default tools (`read`, `bash`, `edit` and `write`) can run commands and edit files in the sandbox, and
pi does not ask for approval before tool calls. There is no turn limit either: pi works until the
model stops calling tools, so the task's time limit in Valkyrie is the only bound.

## Outputs

Written to `/logs/pi/` and collected as `pi/`:

- `session.jsonl`: the whole session, pi's own session file (`sessions/<timestamp>_<id>.jsonl`). One
  JSON entry per line: a `session` header, then `message` entries with the role `system`, `user`,
  `assistant` or `toolResult` (an assistant message holds its text, thinking and tool calls, its
  `usage`, and a `stopReason`), plus entries for model and thinking-level changes, compaction and
  context edits. The format is documented in the submodule at
  `pi/packages/coding-agent/docs/session-format.md`. It is not sanitized, so it holds the task text.
  It is missing if the run never got a conversation started.
- `summary.json`: `agent`, `upstream` (the contents of `upstream.json`), `outcome` (`completed`,
  `error` or `killed`), `stop_reason` and `agent_exit_code`. It is written even when the run fails.
  `stop_reason` is the `stopReason` of the last assistant message in the session (`stop`, `length`,
  `toolUse`, `error`, `aborted` or `deferred`), `killed` for a killed run, and `unknown` when there is
  no readable assistant message. `agent_exit_code` is what pi itself exited with.

`final_message.txt` (what pi printed on stdout, the final reply) and `stderr.log` stay in `/logs/pi/`
too.

The run exits 0 when pi stops on its own. That includes a reply cut off at the model's output token
limit (`stopReason` `length`): pi exits 1 after printing the partial reply, but the work was done and
the run is graded, with `agent_exit_code` 1 in `summary.json`. If pi is killed (exit code 137) the run
exits 137 with no error line. Any other ending exits with pi's code and a one-line
`AgentError: pi exited with code N (stop: error)` for Valkyrie, so the task is skipped rather than
graded. The part in brackets is the last stop reason, `(no session)` when pi left no session file, and
left out when the session has no readable assistant message. Only that word is copied, never message
text, since it can quote the task.

## Quirks

- `run.sh` sets two environment variables, `PI_SKIP_VERSION_CHECK=1` (no request for a newer version,
  so the version that runs is the pinned one) and `PI_TELEMETRY=0`. Nothing else about pi is changed:
  the task repo's `AGENTS.md` and `CLAUDE.md` are loaded exactly as they would be running pi there
  locally.
- `--no-approve` only makes explicit what print mode does anyway on a fresh home directory: the task
  repo's `.pi/` settings, extensions, skills and prompt templates are not trusted, so they are not
  loaded. Context files (`AGENTS.md`, `CLAUDE.md`) load regardless of that.
- The task goes to pi as an `@file` argument, so its size is not limited by the command line and it
  does not appear in the process list. pi puts it in the first prompt wrapped as
  `<file name="/path/to/problem">...</file>`, and skips an empty file. stdin is `/dev/null` because pi
  waits for end-of-file on any stdin that is not a terminal and adds what it read to the prompt.
- If the model hits its output limit with room to spare (a provider that caps the output below the
  model's own limit), pi first drops that reply, compacts the context and tries once more, so the
  session may hold a `length` reply that a later reply replaced. The last assistant message decides.
- API keys passed with `-s` are environment variables inside the sandbox, so the agent's own commands
  can read them.
- The install was checked on Debian (glibc), arm64 natively and x64 under emulation, running
  `setup.sh` twice in one container, and on Alpine (musl) for the message above. The agent was run end
  to end only against a stand-in model server, not a real provider.

## Updating

```bash
uv run python scripts/bump_agent.py agents/pi
```

picks the newest upstream release on the same major version that is at least seven days old, checks it
out in the submodule, rewrites `upstream.json` and refreshes the sha256 lines in `checksums.txt` from
the release's `SHA256SUMS`. The jq lines in `checksums.txt` are kept.
