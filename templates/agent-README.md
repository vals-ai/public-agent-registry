<!-- Copy this file to contracts/<agent-name>/README.md for native upstream
integrations. Keep the original agent repository pinned as a Git submodule at
agents/<agent-name>. Self-contained agent submodules may keep this README beside
their contract.yaml instead. Replace placeholders before publishing and preserve
the section order. Describe implemented behavior and actual validation only.
The integration release and native upstream version are separate.
-->

# {{Agent name}} v{{integration version}} for Valkyrie

Valkyrie integration for [{{native agent name}}](https://github.com/UPSTREAM_OWNER/UPSTREAM_REPO), for {{supported task types}}. Installs {{native package/repository}} and runs {{native CLI or SDK entry point}}. {{Briefly describe any adapter behavior, such as passing the task file and collecting output.}}

## Upstream and Runtime

| Item | Value |
| --- | --- |
| Native upstream | [{{agent name}}](https://github.com/UPSTREAM_OWNER/UPSTREAM_REPO) |
| Native version | {{exact package version or full commit SHA installed by setup.sh}} |
| Integration release | {{integration version}} |
| Valkyrie agent name | {{exact name from contract.yaml}} |
| Environment | {{required OS, architecture, runtimes and system tools; distinguish what setup installs from what the benchmark image must provide}} |
| Setup access | {{public package registries/repositories downloaded during installation}} |
| Run access | {{provider API or other services contacted during execution}} |

## Configuration

Configuration is defined in [contract.yaml](contract.yaml); installation is defined in [setup.sh](setup.sh).

### Model and Provider

- Model: {{required or default value; show the exact format accepted by --model}}.
- Routing: {{how the integration passes or translates the model name to the native agent and selects the provider}}.
- Provider support: {{tested providers and any additional documented but untested routes}}.

<!-- State OpenRouter support only when the integration exposes a working route.
Do not assume every upstream provider is supported by the Valkyrie adapter.
Use an actual compatible model in the run example below. -->

### Secrets

| Environment variable | Required when | Purpose |
| --- | --- | --- |
| {{PROVIDER_API_KEY}} | {{selected provider or condition}} | {{provider authentication}} |

Pass secret-store references with `--secret ENV_VAR YOUR_CLOUD_SECRET_NAME`. Repeat the flag for multiple secrets. {{If no secrets are needed, replace the table and this paragraph with "None" and remove the flag from the run example.}}

### Valkyrie Options

| Option | Type | Default | Effect |
| --- | --- | --- | --- |
| {{contract kwargs key}} | {{type}} | {{default or required}} | {{what changes in the native invocation}} |

<!-- Include only kwargs actually exposed by contract.yaml. Show an exact
--kwarg KEY VALUE example for supported options, or write "None" if there are
no kwargs. Keep any native-only CLI documentation separately labeled. -->

## Usage with Valkyrie

Install and configure [Valkyrie](https://github.com/vals-ai/Valkyrie) first, including the secret-store references required by the selected provider.

Install this integration:

```bash
valkyrie agent install 'https://github.com/vals-ai/public-agent-registry/tree/main/contracts/AGENT_DIRECTORY'
```

<!-- Replace AGENT_DIRECTORY with the versioned contract directory name. For a
self-contained integration, use its agents/ path instead of contracts/. Publish
the main-branch command only once that path is available; before merge, use a
public candidate registry commit instead of main. A direct public integration
repository URL is also valid if the contract is at that repository's root. -->

Run one task:

```bash
valkyrie run start \
  --benchmark 'BENCHMARK_NAME' \
  --agent 'CONTRACT_AGENT_NAME' \
  --model 'EXACT_SUPPORTED_MODEL_IDENTIFIER' \
  --secret 'PROVIDER_API_KEY_ENV_NAME' 'YOUR_CLOUD_SECRET_NAME' \
  --concurrency 1 \
  --slice 0:1
```

<!-- Fill in a supported benchmark, actual contract name, tested model and
credential environment variable. Leave only the user's secret-store name as
a placeholder in the published command. Add --dataset if needed. Use
--task-ids instead of --slice when a specific task is needed to reproduce the
documented smoke run. Do not run a slice and task selector together. -->

## Output Files

Final output path: `{{exact contract final_output path, or not provided}}`.

| Path | Contents | Availability |
| --- | --- | --- |
| {{path relative to final_output}} | {{native trajectory, final answer, log or normalized summary}} | {{always, success only or condition}} |

<!-- List only artifacts this integration actually produces. Identify native
formats versus any normalized summaries. Document the source and units of
token/cost metrics if provided; missing metrics are unavailable, not zero.
Outputs are optional under the registry rules: write "None" when absent.
Mention task-workspace edits when they are part of the benchmark result. -->

## Validation

| Check | Last verified result |
| --- | --- |
| Fresh installation | {{date, environment and result, or not run}} |
| Valkyrie smoke run | {{date, benchmark/dataset version, task ID, provider/model and result, or not run}} |
| Evidence | {{public PR, sanitized log or shareable artifact reference}} |

<!-- Link evidence that identifies the tested integration and registry commits.
Distinguish successful execution from benchmark task success. Report the scope
actually tested; one smoke run does not establish benchmark performance.
Never mark a planned run as passed. -->

## Known Limitations

- {{Task/environment/provider constraints and any untested routes that matter to users.}}
- {{Integration behavior that differs from the native defaults, such as headless execution, tool permissions or workspace handling.}}

<!-- Keep useful recovery steps here for known failure modes. If there are no
known limitations, state the tested scope rather than promising universal support. -->

## License

- Integration: {{license and link to its license file}}.
- Native agent: {{license and link to the upstream license at the pinned release/ref}}.
- Third-party notices: {{link if present, otherwise not applicable}}.
