# Delta for geospatial-audit

## ADDED Requirements

### Requirement: AI Workflow Event Types (MUST)

The `audit_logs` system MUST support the following new `entity_type` values for AI workflows: `ai_workflow`, `ai_agent`, `ai_tool_call`. The corresponding `action` values MUST include: `workflow_start`, `workflow_complete`, `workflow_failed`, `agent_start`, `agent_complete`, `agent_failed`, `tool_call_start`, `tool_call_complete`, `tool_call_failed`. These values MUST be added to the centralized constants/enums used for audit events.

#### Scenario: Record agent execution lifecycle

- GIVEN an AI agent executing in a workflow
- WHEN the agent starts
- THEN an audit log entry is created with `entity_type=ai_agent`, `action=agent_start`
- WHEN the agent completes
- THEN an audit log entry is created with `entity_type=ai_agent`, `action=agent_complete`

### Requirement: AI Metadata in Audit Payload (SHOULD)

Audit log entries for AI workflows SHOULD include the following in the `metadata` JSONB column: `workflow_id`, `agent_id`, `model` (LLM model used), `token_usage` (prompt + completion tokens), `duration_ms`, and `input_preview` (truncated input for debugging).

#### Scenario: Enriched audit log for AI step

- GIVEN a completed AI agent execution
- WHEN the audit entry is created
- THEN the metadata JSONB contains workflow_id, agent_id, model, token_usage, and duration_ms
- AND the input_preview is truncated to 500 characters

### Requirement: Non-Fatal Audit Preservation (MUST)

The existing non-fatal audit behavior MUST be preserved for all new AI event types. A failure to record any AI workflow audit event MUST NOT interrupt agent execution or workflow completion.

#### Scenario: AI audit failure is non-fatal

- GIVEN an AI workflow that produces an audit log entry
- WHEN the audit persistence fails
- THEN the agent execution continues without interruption
- AND the error is logged via the existing logging mechanism
