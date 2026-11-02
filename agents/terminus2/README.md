# terminus2

Terminus 2, the agent built into [Harbor](https://github.com/harbor-framework/harbor) (Apache-2.0),
run for Valkyrie exactly as upstream ships it. Terminus 2 has no repository of its own: it is
`harbor.agents.terminus_2.Terminus2` inside Harbor, so the upstream repository is all of Harbor, the
`harbor/` git submodule, pinned to the release recorded in `upstream.json` (`tag` and `commit`). Only
`contract.yaml`, `setup.sh`, `run_terminus2.py`, `terminus2_bridge.py`, `terminus2_support.py` and
this README are Vals-authored. Harbor itself is not modified.

## Install

```bash
valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/main/agents/terminus2
```

`setup.sh` installs `curl` and `tmux` if the image lacks them (with `apt-get`, `dnf`, `yum` or `apk`),
then uv 0.13.5 (checked against a pinned sha256 before it runs), and builds a venv in
`/opt/terminus2-venv` from Harbor's own `uv.lock` with `uv sync --frozen --no-dev`, so the versions
are exactly the ones Harbor tested. Its interpreter is a uv-managed Python (the version in
`harbor/.python-version`) in `/opt/terminus2-python`, not the task's own Python, so a task that
changes the system Python does not break the agent. The only thing it puts on `PATH` is the
`terminus2-run` entry script, which works from whatever folder Valkyrie copies the agent into. It can
be run again after a failed attempt. The install takes about 320 MB under `/opt`, and the bundle
carries all of Harbor (about 100 MB, mostly docs and adapters).

Harbor's lock pins a litellm whose only Linux wheels need glibc 2.28 or newer. On a musl image
(Alpine) `setup.sh` installs nothing and exits 1 with
`Terminus 2's dependencies (litellm) need glibc; this image uses musl`, so use a Debian-, Ubuntu- or
Fedora-based image.

## Run

The agent needs an API key for the model's provider. Pass it as a secret. Terminus 2 was built for
Terminal-Bench, so that is the benchmark to start with:

```bash
valkyrie run start --benchmark terminal-bench --dataset terminal-bench-2.1 --agent terminus2 \
  --model anthropic/claude-sonnet-4-6 -s ANTHROPIC_API_KEY <secret-ref> \
  --concurrency 10 --slice :10
```

`--model` is a [litellm](https://docs.litellm.ai/docs/providers) model name and must include the
provider, for example `anthropic/claude-sonnet-4-6`, `openai/gpt-5.4` or `gemini/gemini-2.5-pro`. Use
the secret that provider expects (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, ...).

| Kwarg (`-k name value`) | Default | Meaning |
| --- | --- | --- |
| `max_turns` | empty | Maximum agent turns. Empty keeps upstream's default, no practical limit. |
| `temperature` | empty | Sampling temperature. Empty sends none, so the provider's default applies. |
| `parser` | empty | How replies are parsed: `json` or `xml`. Empty keeps upstream's default, `json`. |
| `reasoning_effort` | empty | `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max` or `default`. Empty sends none. |

Terminus 2 works in a tmux session: each turn the model reads the screen and sends keystrokes to a
`bash --login` shell. That shell starts in the benchmark's working directory.

## How it runs inside the sandbox

Harbor normally runs Terminus 2 *outside* the task container and drives the tmux session inside it
through an environment object (`exec`, `upload_file`, `download_file`). Valkyrie runs the agent
*inside* the task container, and none of Harbor's environment types runs commands on the current
machine. So `terminus2_bridge.py` defines a small `LocalEnvironment` (a Harbor `BaseEnvironment`) whose
`exec` runs `bash -c` on this machine, with timeouts that behave like Harbor's Docker environment, and
whose uploads and downloads are local copies. It then calls Terminus 2 in the order Harbor's own
`trial.py` does: construct `Terminus2(..., record_terminal_session=False)`, `setup` (which starts
tmux), `run`. One step is added between them: the wrapper types `cd <working directory>` into the
tmux session, because a login shell's profile may move it elsewhere. That `cd` is the first thing on
the terminal screen the model sees.

This bridge relies on Harbor internals (`BaseEnvironment`, `TrialPaths`, `AgentContext`, the provider
table, the tmux session name) that Harbor does not document as a public API. The pinned release holds
them still, and every pin bump has to be re-checked (see "Updating").

## Outputs

Harbor hardcodes `/logs/agent/` as the agent's log folder (the tmux pane log goes there whatever the
wrapper asks), so this agent writes to `/logs/agent/` rather than `/logs/terminus2/`, and it is
collected as `terminus2/`:

- `trajectory.json`: the whole run in Harbor's ATIF format, written by Terminus 2 after
  every turn and once more when the run ends, even when it fails. It is not sanitized, so it holds the
  task text.
- `summary.json`: `agent`, `upstream` (the contents of `upstream.json`), `outcome` (`completed` or
  `error`), `stop_reason`, `agent_exit_code` and `metrics`. It is written even when the run fails.
  `stop_reason` is `returned` when Terminus 2 finished, the exception's class name when it failed
  (for example `AuthenticationError`), and `invalid_options` when a kwarg could not be read.
  `metrics` holds the totals Terminus 2 recorded: `n_input_tokens` (including cached tokens),
  `n_output_tokens`, `n_cache_tokens`, `cost_usd` (null when litellm has no price for the model) and
  `metadata` (`n_episodes`, the number of turns, `api_request_times_msec` and
  `summarization_count`).

`terminus_2.pane`, the raw tmux pane log, stays in `/logs/agent/` too.

The run exits 0 when Terminus 2 finishes on its own: when it has confirmed the task complete, reached
`max_turns`, or its tmux session ended. Terminus 2 does not report which of these it was; `metadata`'s
`n_episodes` shows how many turns it took. Any exception (a bad API key, an unknown model, tmux
failing to start, Harbor failing to import) exits 1 with a one-line
`AgentError: terminus2 <ExceptionClass>` reason for Valkyrie, so the task is skipped rather than
graded. Only the class name is copied, never the message, since it can quote the task or the model.
The full traceback goes to stderr.

## Quirks

- **API keys are kept out of the tmux shell, best effort.** In Harbor the keys live in the harness
  outside the container. Here the harness shares the machine, so every command `LocalEnvironment` runs,
  including the one that starts the tmux server, gets the environment without any variable named in
  Harbor's provider table (API keys, base URLs and related settings such as `AWS_REGION` or
  `GOOGLE_APPLICATION_CREDENTIALS`) and without any variable ending in `_API_KEY`. That stops a
  routine `env` from printing a key into the pane log and the trajectory. It does not hide the keys
  from a determined agent: Valkyrie sets secrets as environment variables on the whole sandbox, so they
  can still be read, for example from `/proc/1/environ` or the wrapper's own `/proc/<pid>/environ`.
  Those settings are also missing for the task's own commands typed into the shell, as they would be
  under Harbor.
- The tmux session is left running when the agent finishes, as it is under Harbor, where the verifier
  runs while it is still there. A server the agent started for the task keeps running for grading.
- Terminus 2 talks to the model through litellm, so the usual provider variables apply. The
  `terminus2-run` process has no stdin, and its commands run as the sandbox's user (root).
- The agent's Python runs with `-E`, so the task's `PYTHONPATH`, `PYTHONHOME` and other `PYTHON*`
  variables cannot change which modules the harness loads. The shell the agent works in still has
  them, as the task set them.
- Terminal recording (asciinema) is off, so nothing beyond tmux is installed.
- The install was checked on Debian (`debian:bookworm-slim`, arm64), twice in one container, and on
  Fedora 42 (`dnf`); Alpine stops with the message above. Without a real API key, the run was checked
  only up to the first model call: install, tmux start, the `cd`, the key scrubbing and the
  `AgentError` path.

## Updating

```bash
uv run python scripts/bump_agent.py agents/terminus2
```

picks the newest Harbor release on the same major version that is at least seven days old, checks it
out in the submodule and rewrites `upstream.json`. Because the bridge relies on Harbor internals,
re-run its tests against the new Harbor before committing:

```bash
uv run --with ./agents/terminus2/harbor pytest tests/agents/test_terminus2_local_env.py tests/agents/test_terminus2_support.py
```

Then do one real run, from a branch whose name has no slash (see `CONTRIBUTING.md`):

```bash
valkyrie agent install https://github.com/<owner>/public-agent-registry/tree/<branch>/agents/terminus2 --name terminus2-test
valkyrie run start --benchmark terminal-bench --dataset terminal-bench-2.1 --agent terminus2-test \
  --model anthropic/claude-sonnet-4-6 -s ANTHROPIC_API_KEY <secret-ref> --concurrency 1 --slice :1
```
