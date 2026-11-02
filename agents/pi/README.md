# pi

[pi](https://github.com/earendil-works/pi) by Earendil Works, a minimal, extensible agent harness, run for Valkyrie in print mode as upstream ships it. The pinned upstream release is recorded in `upstream.json`.

## Configuration

- Secret: the API key of the model's provider, for example `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` or `DEEPSEEK_API_KEY`
- Model: `provider/id`, for example `anthropic/claude-sonnet-4-6` or `deepseek/deepseek-v4-pro`. `pi --list-models` lists them.
- Final output: `/logs/pi`
- pi needs a glibc-based task image (Debian or Ubuntu), not Alpine.

| Kwarg (`-k name value`) | Default | Meaning |
| --- | --- | --- |
| `thinking` | empty | pi's thinking level: `off`, `minimal`, `low`, `medium`, `high`, `xhigh` or `max`. Empty keeps pi's default. |

## Usage with valkyrie

We assume if you are here that you have [valkyrie](https://github.com/vals-ai/Valkyrie) installed. If not, navigate to the [main repository](https://github.com/vals-ai/Valkyrie) and get started.

Install the agent from github using valkyrie for future use

```bash
valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/main/agents/pi
```

Run a benchmark using pi as the agent, specify `--model <MODEL>` to change the underlying model

```bash
valkyrie run start --benchmark swebench --agent pi \
  --model deepseek/deepseek-v4-pro -s DEEPSEEK_API_KEY <secret-ref> \
  -k thinking high --concurrency 10 --slice :10
```

## Output Files

The run writes to `/logs/pi/`:

- `summary.json`: the agent, the upstream release that ran, the outcome and the stop reason
- `session.jsonl`: the whole session, one entry per line
- `final_message.txt`: pi's final reply
- `stderr.log`: what pi printed on stderr

List the collected ones for a run with `valkyrie run artifacts RUN_ID`.
