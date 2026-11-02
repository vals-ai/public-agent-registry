# mini_swe_agent

[mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) by the SWE-agent team, the minimal AI software engineering agent, run for Valkyrie as upstream ships it. The pinned upstream release is recorded in `upstream.json`.

## Configuration

- Secret: the API key of the model's provider, for example `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `GEMINI_API_KEY`
- Model: a [litellm](https://docs.litellm.ai/docs/providers) name that includes the provider, for example `anthropic/claude-sonnet-4-6` or `openai/gpt-5.4`
- Final output: `/logs/mini_swe_agent`
- On SWE-bench, pass `-k config benchmarks/swebench.yaml`.

| Kwarg (`-k name value`) | Default | Meaning |
| --- | --- | --- |
| `config` | `mini.yaml` | mini-swe-agent config. Use `benchmarks/swebench.yaml` for SWE-bench. |
| `cost_limit` | empty | USD cap. Empty keeps upstream's default, `0` disables the cap. |
| `step_limit` | empty | Maximum agent steps. Empty keeps upstream's default. |
| `cost_tracking` | empty | Set to `ignore_errors` for models litellm has no price for. |

## Usage with valkyrie

We assume if you are here that you have [valkyrie](https://github.com/vals-ai/Valkyrie) installed. If not, navigate to the [main repository](https://github.com/vals-ai/Valkyrie) and get started.

Install the agent from github using valkyrie for future use

```bash
valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/main/agents/mini_swe_agent
```

Run a benchmark using mini_swe_agent as the agent, specify `--model <MODEL>` to change the underlying model

```bash
valkyrie run start --benchmark swebench --agent mini_swe_agent \
  --model anthropic/claude-sonnet-4-6 -s ANTHROPIC_API_KEY <secret-ref> \
  -k config benchmarks/swebench.yaml --concurrency 10 --slice :10
```

## Output Files

The run writes to `/logs/mini_swe_agent/`:

- `summary.json`: the agent, the upstream release that ran, the outcome and the stop reason
- `trajectory.json`: the full run, step by step

List them for a run with `valkyrie run artifacts RUN_ID`.
