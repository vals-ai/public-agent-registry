# opencode

[opencode](https://github.com/anomalyco/opencode) by Anomaly, the open source AI coding agent, run for Valkyrie as upstream ships it. The pinned upstream release is recorded in `upstream.json`.

## Configuration

- Secret: the API key of the model's provider, for example `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` or `DEEPSEEK_API_KEY`
- Model: `provider/id`, for example `anthropic/claude-sonnet-4-6` or `deepseek/deepseek-v4-pro`
- Final output: `/logs/opencode`
- Only model ids in opencode's own catalog are accepted. `opencode models` lists them.

| Kwarg (`-k name value`) | Default | Meaning |
| --- | --- | --- |
| `variant` | empty | The provider's reasoning effort, for example `high`. Empty keeps the provider's default. |

## Usage with valkyrie

We assume if you are here that you have [valkyrie](https://github.com/vals-ai/Valkyrie) installed. If not, navigate to the [main repository](https://github.com/vals-ai/Valkyrie) and get started.

Install the agent from github using valkyrie for future use

```bash
valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/main/agents/opencode
```

Run a benchmark using opencode as the agent, specify `--model <MODEL>` to change the underlying model

```bash
valkyrie run start --benchmark swebench --agent opencode \
  --model anthropic/claude-sonnet-4-6 -s ANTHROPIC_API_KEY <secret-ref> \
  -k variant high --concurrency 10 --slice :10
```

## Output Files

The run writes to `/logs/opencode/`:

- `summary.json`: the agent, the upstream release that ran, the outcome and the stop reason
- `session.json`: the whole session, with messages, tool calls and results
- `events.jsonl`: opencode's JSON event stream
- `stderr.log`: what opencode printed on stderr

List the collected ones for a run with `valkyrie run artifacts RUN_ID`.
