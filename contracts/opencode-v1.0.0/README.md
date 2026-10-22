# OpenCode v1.0.0 for Valkyrie

Valkyrie integration for [OpenCode](https://github.com/anomalyco/opencode), for coding and terminal tasks. Installs the original `opencode-ai` package and passes the task through stdin to `opencode run --format json`. The adapter collects native events and a small execution summary.

## Upstream and Runtime

| Item | Value |
| --- | --- |
| Native upstream | [anomalyco/opencode](https://github.com/anomalyco/opencode) |
| Native version | `opencode-ai@1.19.3` |
| Native commit | `e3c4eb242585dcd77be1a867391b7c25fd47ce52` |
| Integration release | `1.0.0` |
| Valkyrie agent name | `opencode-v1.0.0` |
| Environment | Linux x86_64 with glibc 2.28+, Bash and Python 3.12+; benchmark supplies task tools such as Git |
| Installed runtime | Node.js `22.19.0`, with SHA-256 verification; npm dependencies and platform binaries pinned in `package-lock.json` |
| Setup access | `nodejs.org`, `registry.npmjs.org` |
| Run access | Selected provider's API and upstream model metadata services |

## Configuration

See [contract.yaml](contract.yaml), [setup.sh](setup.sh), and [upstream.json](upstream.json). Dependency lifecycle scripts are disabled during `npm ci`; setup then explicitly invokes OpenCode's pinned postinstall script to select its native platform binary.

### Model and Provider

`--model` is required and passed unchanged to OpenCode. This first contract exposes these explicit routes:

| Model | Required credential |
| --- | --- |
| `openai/gpt-4.1` | `OPENAI_API_KEY` |
| `anthropic/claude-sonnet-4-5` | `ANTHROPIC_API_KEY` |
| `openrouter/openai/gpt-4.1` | `OPENROUTER_API_KEY` |

All three routes await runtime validation. Additional model identifiers require updating both the contract choices and the adapter's `MODELS` set. The explicit choices also keep model strings safe for Valkyrie's shell command substitution.

### Secrets

Pass the selected credential as a secret-store reference with `--secret ENV_VAR YOUR_CLOUD_SECRET_NAME`. No secret names or values are embedded in the contract.

### Valkyrie Options

None. The adapter has a fixed 600-second execution timeout, followed by a 10-second termination grace period. It uses fresh XDG configuration, data, state and cache directories for each task, disables automatic updates, and enables unattended tool permissions with `permission: allow` and `--auto`.

## Usage with Valkyrie

Configure [Valkyrie](https://github.com/vals-ai/Valkyrie) for the desired environment. Install this registry contract directory:

```bash
valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/codex-native-opencode-v1.0.0/contracts/opencode-v1.0.0
```

This command targets the PR branch; after merge, use `main` in its place. The native upstream is pinned at [agents/opencode-v1.0.0](../../agents/opencode-v1.0.0). Valkyrie installs the published native release from `setup.sh`; the upstream checkout is kept outside the install bundle. No separate integration repository is required.

Example for a later one-task smoke run; it has not been executed:

```bash
valkyrie run start \
  --benchmark terminal-bench \
  --agent opencode-v1.0.0 \
  --model openai/gpt-4.1 \
  --secret OPENAI_API_KEY YOUR_CLOUD_SECRET_NAME \
  --concurrency 1 \
  --slice 0:1
```

## Output Files

Final output path: `/logs/opencode-v1.0.0`.

| Path | Contents | Availability |
| --- | --- | --- |
| `trajectory.jsonl` | Native OpenCode stdout, including JSON events | Once native execution starts |
| `stderr.log` | Native diagnostic output | Once native execution starts |
| `final_message.txt` | Last completed native text event | After the adapter collects output; may be empty on failure |
| `summary.json` | Pinned version, requested model, exit codes, event count, completion status and elapsed time | After normal exit or adapter timeout |

Workspace edits stay in the benchmark's working directory. Native token/cost data stays in the trajectory; the adapter does not estimate usage. `task_success` in the summary is `null`: the benchmark evaluator determines correctness. Setup failures and forced sandbox termination may prevent output collection.

## Validation

| Check | Last verified result |
| --- | --- |
| Static source checks | Python/shell syntax, Valkyrie SDK contract validation and source bundling passed |
| Fresh installation | Not run; deferred |
| Valkyrie smoke run | Not run; deferred |
| Evidence | No runtime evidence yet |

## Known Limitations

- Initial packaging supports Linux x86_64 with glibc only. Python 3.12+ and Bash must already be available.
- Benchmark compatibility and all provider routes are untested. This is an integration candidate, not a verified release.
- Tools run unattended in the benchmark sandbox. Project-local OpenCode configuration can still affect native behavior.
- Session resumption, interactive authentication and multi-turn Valkyrie episodes are not exposed. The transient native session database is removed after execution; the JSON event stream is retained.
- Native error events or a missing terminal `step_finish` with reason `stop` cause failure even if the CLI exits zero.

## License

- Integration: [MIT](LICENSE).
- Native agent: [MIT at v1.19.3](https://github.com/anomalyco/opencode/blob/v1.19.3/LICENSE).
- Dependencies retain their own licenses; npm installs their included notices alongside the packages.
