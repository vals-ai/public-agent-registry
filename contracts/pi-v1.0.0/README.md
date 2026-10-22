# Pi v1.0.0 for Valkyrie

Valkyrie integration for [Pi](https://github.com/earendil-works/pi), for coding and terminal tasks. Installs the original `@earendil-works/pi-coding-agent` package and passes the task through stdin to Pi's non-interactive JSON mode. The adapter collects native events and a small execution summary.

## Upstream and Runtime

| Item | Value |
| --- | --- |
| Native upstream | [earendil-works/pi](https://github.com/earendil-works/pi) |
| Native version | `@earendil-works/pi-coding-agent@1.4.0` |
| Native commit | `4a080252f06caf63a525d7873c5d94d3c23887e0` |
| Integration release | `1.0.0` |
| Valkyrie agent name | `pi-v1.0.0` |
| Environment | Linux x86_64 with glibc 2.28+, Bash and Python 3.12+; benchmark supplies task tools such as Git |
| Installed runtime | Node.js `22.19.0`, with SHA-256 verification; npm dependencies pinned in `package-lock.json` |
| Setup access | `nodejs.org`, `registry.npmjs.org` |
| Run access | Selected provider's API; OpenRouter may also retrieve the authorized model catalog |

## Configuration

See [contract.yaml](contract.yaml), [setup.sh](setup.sh), and [upstream.json](upstream.json).

### Model and Provider

`--model` is required. This first contract exposes these explicit routes:

| Model | Required credential |
| --- | --- |
| `openai/gpt-4.1` | `OPENAI_API_KEY` |
| `anthropic/claude-sonnet-4-5` | `ANTHROPIC_API_KEY` |
| `openrouter/openai/gpt-4.1` | `OPENROUTER_API_KEY` |

The adapter splits the first `/` into Pi's `--provider` and `--model` arguments. All three routes await runtime validation. Additional model identifiers require updating both the contract choices and the adapter's `MODELS` set. The explicit choices also keep model strings safe for Valkyrie's shell command substitution.

### Secrets

Pass the selected credential as a secret-store reference with `--secret ENV_VAR YOUR_CLOUD_SECRET_NAME`. No secret names or values are embedded in the contract.

### Valkyrie Options

None. The adapter has a fixed 600-second execution timeout, followed by a 10-second termination grace period. It starts a fresh in-memory session and disables ambient extensions, skills, prompt templates and approval of project-local configuration. Native built-in tools remain available.

## Usage with Valkyrie

Configure [Valkyrie](https://github.com/vals-ai/Valkyrie) for the desired environment. Install this registry contract directory:

```bash
valkyrie agent install https://github.com/vals-ai/public-agent-registry/tree/codex-native-pi-v1.0.0/contracts/pi-v1.0.0
```

This command targets the PR branch; after merge, use `main` in its place. The native upstream is pinned at [agents/pi-v1.0.0](../../agents/pi-v1.0.0). Valkyrie installs the published native release from `setup.sh`; the upstream checkout is kept outside the install bundle. No separate integration repository is required.

Example for a later one-task smoke run; it has not been executed:

```bash
valkyrie run start \
  --benchmark terminal-bench \
  --agent pi-v1.0.0 \
  --model openai/gpt-4.1 \
  --secret OPENAI_API_KEY YOUR_CLOUD_SECRET_NAME \
  --concurrency 1 \
  --slice 0:1
```

## Output Files

Final output path: `/logs/pi-v1.0.0`.

| Path | Contents | Availability |
| --- | --- | --- |
| `trajectory.jsonl` | Native Pi stdout, including JSON session events | Once native execution starts |
| `stderr.log` | Native diagnostic output | Once native execution starts |
| `final_message.txt` | Text from the last completed assistant message | After the adapter collects output; may be empty on failure |
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
- The adapter runs in the benchmark's existing working directory and grants Pi its normal native tool access. Project configuration excluded by `--no-approve` will not take effect.
- Session resumption, interactive authentication, custom extensions and multi-turn Valkyrie episodes are not exposed.
- A missing native completion event is reported as failure even if the CLI exits zero. Native retries remain controlled by Pi.

## License

- Integration: [MIT](LICENSE).
- Native agent: [MIT at v1.4.0](https://github.com/earendil-works/pi/blob/v1.4.0/LICENSE).
- Dependencies retain their own licenses; npm installs their included notices alongside the packages.
