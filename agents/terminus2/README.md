# terminus2

Terminus 2, the terminal agent built into [Harbor](https://github.com/harbor-framework/harbor), run for Valkyrie as upstream ships it. It was built for Terminal-Bench. The pinned upstream release is recorded in `upstream.json`.

## Configuration

- Secret: the API key of the model's provider, for example `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `GEMINI_API_KEY`
- Model: a [litellm](https://docs.litellm.ai/docs/providers) name that includes the provider, for example `anthropic/claude-sonnet-4-6` or `gemini/gemini-2.5-pro`
- Final output: `/logs/agent`
- Run it on `--benchmark terminal-bench`, in a glibc-based task image (Debian, Ubuntu or Fedora), not Alpine.

| Kwarg (`-k name value`) | Default | Meaning |
| --- | --- | --- |
| `max_turns` | empty | Maximum agent turns. Empty keeps upstream's default, no practical limit. |
| `temperature` | empty | Sampling temperature. Empty sends none, so the provider's default applies. |
| `parser` | empty | How replies are parsed: `json` or `xml`. Empty keeps upstream's default, `json`. |
| `reasoning_effort` | empty | `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max` or `default`. Empty sends none. |

## Usage with valkyrie

We assume if you are here that you have [valkyrie](https://github.com/vals-ai/Valkyrie) installed. If not, navigate to the [main repository](https://github.com/vals-ai/Valkyrie) and get started.

Install the agent from github using valkyrie for future use

```bash
valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/main/agents/terminus2
```

Run a benchmark using terminus2 as the agent, specify `--model <MODEL>` to change the underlying model

```bash
valkyrie run start --benchmark terminal-bench --dataset terminal-bench-2.1 --agent terminus2 \
  --model anthropic/claude-sonnet-4-6 -s ANTHROPIC_API_KEY <secret-ref> \
  -k max_turns 50 --concurrency 10 --slice :10
```

## Output Files

The run writes to `/logs/agent/`:

- `summary.json`: the agent, the upstream release that ran, the outcome, the stop reason and token and cost totals
- `trajectory.json`: the whole run, turn by turn
- `terminus_2.pane`: the terminal log

List the collected ones for a run with `valkyrie run artifacts RUN_ID`.
