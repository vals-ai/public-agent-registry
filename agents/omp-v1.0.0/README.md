# Oh My Pi v1.0.0 for Valkyrie

Valkyrie integration for [Oh My Pi (OMP)](https://github.com/can1357/oh-my-pi), for coding and terminal tasks. Installs OMP's original prebuilt release and passes the task through stdin to `omp --print --mode json`. The adapter collects native events and a small execution summary.

## Upstream and Runtime

| Item | Value |
| --- | --- |
| Native upstream | [can1357/oh-my-pi](https://github.com/can1357/oh-my-pi) |
| Native version | `18.12.6` |
| Native commit | `45c35e40c46166dc726ccc52f5d27f40f2449f99` |
| Integration release | `1.0.0` |
| Valkyrie agent name | `omp-v1.0.0` |
| Environment | Linux x86_64 with glibc, Bash and Python 3.12+; benchmark supplies task tools such as Git |
| Installed runtime | Native `omp-linux-x64` binary; no separate Bun installation |
| Setup access | `build.stencil.so` and its release download storage |
| Run access | Selected provider's API and any services used by OMP's native tools |

[upstream.json](upstream.json) records the binary's SHA-256. Setup checks the release service's commit and checksum against that pin, verifies the downloaded binary, and checks its reported version.

## Configuration

See [contract.yaml](contract.yaml) and [setup.sh](setup.sh).

### Model and Provider

`--model` is required. This first contract exposes these explicit routes:

| Model | Required credential |
| --- | --- |
| `openai/gpt-4.1` | `OPENAI_API_KEY` |
| `anthropic/claude-sonnet-4-5` | `ANTHROPIC_API_KEY` |
| `openrouter/openai/gpt-4.1` | `OPENROUTER_API_KEY` |

The adapter splits the first `/` into OMP's `--provider` and `--model` arguments. Additional model identifiers require updating both the contract choices and the adapter's `MODELS` set. The explicit choices also keep model strings safe for Valkyrie's shell command substitution.

### Secrets

Pass the selected credential as a secret-store reference with `--secret ENV_VAR YOUR_CLOUD_SECRET_NAME`. No secret names or values are embedded in the contract.

### Valkyrie Options

None. The adapter has a fixed 600-second execution timeout, followed by a 10-second termination grace period. It starts a fresh in-memory session with an isolated agent directory, disables ambient extensions and skills, uses `--approval-mode yolo`, and disables title generation, interactive UI and automatic QA reporting.

## Usage with Valkyrie

Configure [Valkyrie](https://github.com/vals-ai/Valkyrie) for the desired environment. Install this agent directory:

```bash
valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/codex-native-omp-v1.0.0/agents/omp-v1.0.0
```

This command targets the PR branch; after merge, use `main` in its place. This directory contains the contract, setup, README and adapter needed to install the integration. `setup.sh` installs the published upstream release pinned in [upstream.json](upstream.json), verifying its SHA-256 checksum. No source submodule is needed.

Run one task:

```bash
valkyrie run start \
  --benchmark terminal-bench \
  --agent omp-v1.0.0 \
  --model openrouter/openai/gpt-4.1 \
  --secret OPENROUTER_API_KEY YOUR_CLOUD_SECRET_NAME \
  --concurrency 1 \
  --slice 0:1
```

## Output Files

Final output path: `/logs/omp-v1.0.0`.

| Path | Contents | Availability |
| --- | --- | --- |
| `trajectory.jsonl` | Native OMP stdout, including JSON session events | Once native execution starts |
| `stderr.log` | Native diagnostic output | Once native execution starts |
| `final_message.txt` | Text from the last completed assistant message | After the adapter collects output; may be empty on failure |
| `summary.json` | Pinned version, requested model, exit codes, event count, completion status and elapsed time | After normal exit or adapter timeout |

Workspace edits stay in the benchmark's working directory. Native token/cost data stays in the trajectory; the adapter does not estimate usage. `task_success` in the summary is `null`: the benchmark evaluator determines correctness. Setup failures and forced sandbox termination may prevent output collection.

## Validation

| Check | Last verified result |
| --- | --- |
| Static source checks | Python/shell syntax, Valkyrie SDK contract validation and source bundling passed |

## Known Limitations

- Initial packaging supports Linux x86_64 with glibc only. The upstream binary's shared-library requirements still need verification in the target benchmark image.
- Tools run unattended in the benchmark sandbox. OMP retains its native built-in tools and project configuration discovery; native auxiliary model roles are not overridden by this integration.
- Session resumption, interactive authentication, custom extensions and multi-turn Valkyrie episodes are not exposed.
- A missing native completion event is reported as failure even if the CLI exits zero. Native retries remain controlled by OMP.

## License

- Integration: [MIT](LICENSE).
- Native agent: [MIT at the pinned commit](https://github.com/can1357/oh-my-pi/blob/45c35e40c46166dc726ccc52f5d27f40f2449f99/LICENSE).
- Native third-party components retain their licenses; see [upstream notices](https://github.com/can1357/oh-my-pi/blob/45c35e40c46166dc726ccc52f5d27f40f2449f99/THIRD-PARTY-NOTICES.txt).
