# ai-llm-abstraction Specification

## Purpose

Abstracción provider-agnostic para modelos LLM vía LiteLLM. Desacopla agentes y herramientas del proveedor concreto (OpenAI, Claude, Gemini, Azure OpenAI, futuros).

## Requirements

### Requirement: Provider-Agnostic Interface (MUST)

The system MUST define a provider-agnostic interface `LLMService` with at minimum a `generate(prompt, context, config) -> LLMResponse` method. All agents and tools MUST use this interface — they MUST NOT call LiteLLM or any provider SDK directly.

#### Scenario: Generate response via abstraction

- GIVEN a configured LLMService with a provider (e.g., OpenAI)
- WHEN `generate()` is called with a prompt
- THEN it MUST return a structured response with `content`, `model`, `usage` (token counts), and `latency_ms`
- AND the caller does NOT know which provider was used

### Requirement: Provider Configuration (MUST)

Providers MUST be configurable via environment variables or config files. The system MUST support at least OpenAI and one additional provider (Claude or Gemini).

#### Scenario: Switch provider

- GIVEN a system configured with OpenAI
- WHEN the config changes to point to Claude (via env var)
- THEN subsequent `generate()` calls use Claude
- AND no code changes are required

### Requirement: Error Handling and Retry (SHOULD)

The `LLMService` SHOULD implement retry with exponential backoff for transient errors (rate limits, timeouts). It MUST NOT retry on authentication or invalid request errors.

#### Scenario: Rate limit retry

- GIVEN an LLM provider returning a 429 rate limit error
- WHEN `generate()` is called
- THEN the service SHOULD retry up to `max_retries` times with backoff
- AND return the response on success

#### Scenario: Auth error is not retried

- GIVEN an LLM provider returning a 401 auth error
- WHEN `generate()` is called
- THEN the service MUST NOT retry
- AND it MUST raise an `AuthenticationError`

### Requirement: Cost Tracking (MAY)

The `LLMService` MAY track per-request cost using LiteLLM's cost calculation. If enabled, cost MUST be included in the response metadata.

#### Scenario: Cost included in response

- GIVEN cost tracking is enabled
- WHEN `generate()` returns
- THEN the response MUST include `cost_usd` in the metadata
