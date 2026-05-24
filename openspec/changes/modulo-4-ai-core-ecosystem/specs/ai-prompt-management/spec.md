# ai-prompt-management Specification

## Purpose

Gestión centralizada de prompts, templates versionables, system prompt maestro e inyección contextual para agentes.

## Requirements

### Requirement: Centralized Prompt Registry (MUST)

The system MUST maintain a centralized registry of all prompts used by agents. Prompts MUST be stored as versioned templates, not hardcoded in agent code.

#### Scenario: Load prompt by key and version

- GIVEN a prompt registered with key `risk_analysis` at version `v2`
- WHEN the prompt manager loads it
- THEN it returns the `v2` template
- AND it includes the template metadata (version, description, expected variables)

#### Scenario: Version fallback

- GIVEN a request for prompt version `v3` that does not exist
- WHEN the prompt manager resolves it
- THEN it SHOULD return the latest available version
- AND include a `version_fallback: true` flag

### Requirement: System Prompt Maestro (MUST)

The system MUST define a base system prompt (maestro) that applies to all agents. The maestro MUST define: global identity, output format rules, constraints, and fallback behavior. Individual agent prompts extend — they MUST NOT contradict — the maestro.

#### Scenario: Maestro applied to every agent

- GIVEN a configured system prompt maestro
- WHEN any agent executes
- THEN the maestro is prepended to the agent's specific prompt
- AND if there is a contradiction, the maestro takes precedence

### Requirement: Context Injection (SHOULD)

The prompt manager SHOULD support variable injection into templates. Variables MUST be validated against the template's declared `expected_variables` before injection.

#### Scenario: Inject context into template

- GIVEN a prompt template with `{{region_name}}` and `{{soil_moisture}}` variables
- WHEN context is injected with valid values
- THEN the rendered prompt contains the actual values
- AND missing variables produce a `MissingVariableWarning`

### Requirement: Template Storage (MAY)

Prompts MAY be stored as files (e.g., `data/prompts/`) or in PostgreSQL. The storage backend MUST be configurable.

#### Scenario: File-based storage

- GIVEN prompts stored as `.md` files in `data/prompts/`
- WHEN the prompt manager starts
- THEN it indexes all prompt files by key
- AND reloads changed files without restart
