# Models Overview

This page provides an overview of all available model classes in mini-SWE-agent.

## Model Classes

| Class | Shortcut | Endpoint | Toolcalls | Description |
|-------|----------|----------|-----------|-------------|
| [`OpenRouterModel`](openrouter.md) | `openrouter` | `/completion` | ✅ | [OpenRouter](https://openrouter.ai/) API integration |
| [`OpenRouterTextbasedModel`](openrouter.md) | `openrouter_textbased` | `/completion` | ❌ | OpenRouter with text-based actions |
| [`OpenRouterResponseModel`](openrouter.md) | `openrouter_response` | `/response` | ✅ | OpenRouter Responses API with native tool calling |
| [`RequestyModel`](requesty.md) | `requesty` | `/completion` | ✅ | [Requesty](https://requesty.ai/) API integration |
| [`DeterministicModel`](test_models.md) | `deterministic` | N/A | ❌ | Returns predefined outputs (for testing) |
| [`RouletteModel`](extra.md) | — | Meta | ❌ | Randomly selects from multiple models |
| [`InterleavingModel`](extra.md) | — | Meta | ❌ | Alternates between models in sequence |

{% include-markdown "../../_footer.md" %}
