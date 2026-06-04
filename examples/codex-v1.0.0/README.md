# Codex-v1.0.0

Codex agent contract for Valkyrie. The wrapper installs the OpenAI Codex CLI, runs `codex exec --json` against the task prompt, and collects the streamed output into standard `/logs` artifacts.

## Configuration

- Secret: `OPENAI_API_KEY`
- Default model: `gpt-5.3-codex`
- Final output: `/logs`

Supported model choices are defined in `contract.yaml`.

## Usage with valkyrie

We assume if you are here that you have [valkyrie](https://github.com/vals-ai/Valkyrie) installed. If not, navigate to the [main repository](https://github.com/vals-ai/Valkyrie) and get started.

Install the agent from github using valkyrie for future use

```bash
valkyrie agent install path/to/github/url/examples/codex-v1.0.0
```

Download the agent, visit the [documentation](https://github.com/vals-ai/Valkyrie/blob/dev/docs/CONTRACTS.md) on **contract.yaml** if you would like to make any modifications.

```bash
valkyrie agent download codex-v1.0.0
```

Upload the agent after changes are made

```bash
valkyrie agent push codex-v1.0.0
```

Run a benchmark using codex as the agent, specify `--model <MODEL>` to change the underlying model that powers codex. Append to the contract or change it to allow any codex compatible model when running codex.

```bash
valkyrie run start --benchmark swebench --agent codex-v1.0.0 -s OPENAI_API_KEY <AWS KEYNAME> --concurrency 10 --slice :10
```

## Output Files

The run writes:

- `summary.json`
- `metrics_total.json`
- `final_message.txt`
- `trajectory.jsonl`
- `raw_output.txt`

See [agent_output_example](agent_output_example/) for a sample output directory.
