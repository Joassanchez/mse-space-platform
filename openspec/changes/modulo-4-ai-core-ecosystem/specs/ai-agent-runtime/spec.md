# ai-agent-runtime Specification

## Purpose

Entorno de ejecución controlada para agentes plugin-based con registro dinámico, validación de manifest, contratos de interfaz, límites de ejecución y validación de outputs estructurados.

## Requirements

### Requirement: Plugin Registration via Manifest (MUST)

Every agent MUST be registered via a manifest file declaring: `id`, `name`, `version`, `capabilities`, `required_tools`, `input_schema`, `output_schema`, `prompt_ref`. The runtime MUST validate the manifest structure before loading the agent.

#### Scenario: Register valid agent

- GIVEN a valid manifest with complete schema declarations
- WHEN the runtime loads the agent
- THEN the agent is registered and discoverable via `list_agents()`
- AND its capabilities are indexed for workflow routing

#### Scenario: Register invalid manifest

- GIVEN a manifest missing required fields (`output_schema`, `capabilities`)
- WHEN the runtime attempts to load it
- THEN it MUST raise a `ManifestValidationError`
- AND the agent MUST NOT be registered

### Requirement: Execution Limits (MUST)

The runtime MUST enforce configurable limits per agent execution: `max_steps`, `max_tokens`, `timeout_seconds`. Agents MUST NOT exceed these limits.

#### Scenario: Agent exceeds step limit

- GIVEN an agent configured with `max_steps: 10`
- WHEN the agent exceeds 10 execution steps
- THEN the runtime MUST terminate the agent
- AND return a `ExecutionLimitError` with the step count

### Requirement: Structured Output Validation (MUST)

Every agent MUST produce outputs matching its declared `output_schema`. The runtime MUST validate the output before passing it to the Response Consolidation layer.

#### Scenario: Valid structured output

- GIVEN an agent with declared output_schema
- WHEN the agent returns a result matching the schema
- THEN the runtime accepts the output and passes it downstream

#### Scenario: Invalid output schema

- GIVEN an agent that returns an output not matching its declared schema
- WHEN the runtime validates it
- THEN it MUST return a `ValidationError`
- AND the agent execution is marked as failed

### Requirement: Reference Agent Support (MAY)

The runtime MAY ship with reference (dummy/mock/example) agents to validate the plugin system. These agents MUST be clearly documented as reference implementations, NOT domain-specific agents.

#### Scenario: Load reference agent

- GIVEN a reference agent manifest in the configured agent directory
- WHEN the runtime starts
- THEN it MAY load the reference agent alongside user-defined agents
- AND the agent type MUST be marked as `reference`
