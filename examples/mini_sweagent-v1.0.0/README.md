# Mini_sweagent-v1.0.0

Mini-SWE-agent contract for Valkyrie. The wrapper installs mini-SWE-agent, runs it against the task prompt with the local environment backend, and writes the trajectory under `/logs/mini_sweagent-v1.0.0`.

For mini-SWE-agent usage and project details, see [mini_sweagent/README.md](mini_sweagent/README.md).

## Configuration

- Secrets: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
- Model: required via `--model`
- Final output: `/logs/mini_sweagent-v1.0.0`

The model is passed through to `model.model_name` in the mini-SWE-agent config.

## Usage with valkyrie

We assume if you are here that you have [valkyrie](https://github.com/vals-ai/Valkyrie) installed. If not, navigate to the [main repository](https://github.com/vals-ai/Valkyrie) and get started.

Install the agent from github using valkyrie for future use.

```bash
valkyrie agent install path/to/github/url/examples/mini_sweagent-v1.0.0
```

Download the agent, visit the [documentation](https://github.com/vals-ai/Valkyrie/blob/dev/docs/CONTRACTS.md) on **contract.yaml** if you would like to make any modifications.

```bash
valkyrie agent download mini_sweagent-v1.0.0
```

Upload the agent after changes are made.

```bash
valkyrie agent push mini_sweagent-v1.0.0
```

Run a benchmark using mini-SWE-agent as the agent. Specify `--model <MODEL>` to set the model passed into mini-SWE-agent.

```bash
valkyrie run start --benchmark swebench --agent mini_sweagent-v1.0.0 --model openai/gpt-4o -s OPENAI_API_KEY <AWS KEYNAME> --concurrency 10 --slice :10
```

## Output Files

The run writes the mini-SWE-agent output directory to `/logs/mini_sweagent-v1.0.0`, including:

- `trajectory.json`
