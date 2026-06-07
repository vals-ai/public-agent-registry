# Claude_code-v1.0.0

Claude Code agent contract for Valkyrie. The wrapper installs the Claude Code CLI, runs `claude -p --verbose --output-format stream-json` against the task prompt, and collects the streamed output into standard `/logs` artifacts.

## Configuration

- Secret: `ANTHROPIC_API_KEY`
- Default model: `anthropic/claude-sonnet-4-20250514`
- Final output: `/logs`

The default model is defined in `contract.yaml`.

## Usage with valkyrie

We assume if you are here that you have [valkyrie](https://github.com/vals-ai/Valkyrie) installed. If not, navigate to the [main repository](https://github.com/vals-ai/Valkyrie) and get started.

Install the agent from github using valkyrie for future use.

```bash
valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/jf/agent-checkpoint/examples/claude_code-v1.0.0
```

Download the agent, visit the [documentation](https://github.com/vals-ai/Valkyrie/blob/dev/docs/CONTRACTS.md) on **contract.yaml** if you would like to make any modifications.

```bash
valkyrie agent download claude_code-v1.0.0
```

Upload the agent after changes are made.

```bash
valkyrie agent push claude_code-v1.0.0
```

Run a benchmark using Claude Code as the agent. Specify `--model <MODEL>` to change the underlying model that powers Claude Code. Append to the contract or change it to allow any Claude Code compatible model when running Claude Code.

```bash
valkyrie run start --benchmark swebench --agent claude_code-v1.0.0 -s ANTHROPIC_API_KEY <CLOUD_KEYNAME> --concurrency 10 --slice :10
```

## Output Files

The run writes:

- `summary.json`
- `metrics_total.json`
- `final_message.txt`
- `trajectory.jsonl`
- `raw_output.txt`

See [agent_output_example](agent_output_example/) for a sample output directory.
