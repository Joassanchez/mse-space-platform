# ai-observability Specification

## Purpose

Registro de logs, traces y métricas para workflows de IA. Extiende el sistema `audit_logs` existente del Módulo 3 con metadata específica de ejecución de agentes.

## Requirements

### Requirement: Agent Execution Tracing (MUST)

Every agent execution MUST produce a trace record containing: `agent_id`, `workflow_id`, `step_number`, `input_summary`, `output_summary`, `duration_ms`, `status`, `token_usage`. Traces MUST be persisted to the database.

#### Scenario: Single agent trace

- GIVEN a single agent execution in a workflow
- WHEN the agent completes
- THEN a trace record is created with agent_id, duration, status, and token_usage
- AND the trace is linked to the parent workflow via `workflow_id`

### Requirement: Workflow-Level Audit (MUST)

The system MUST record workflow lifecycle events in `audit_logs`: `workflow_start`, `workflow_complete`, `workflow_failed`, `workflow_step_complete`. Each event MUST include `workflow_id`, `agent_id` (if applicable), and a structured `metadata` JSONB payload.

#### Scenario: Workflow completion logged

- GIVEN a multi-step workflow that completes successfully
- WHEN the workflow finishes
- THEN an audit_log entry is created with action `workflow_complete`
- AND the metadata includes total_duration_ms, step_count, and total_tokens

### Requirement: Error and Failure Recording (MUST)

The observability layer MUST record all agent and workflow errors. Failed steps MUST preserve the partial output and error message for debugging.

#### Scenario: Agent step failure

- GIVEN an agent that fails during execution
- WHEN the runtime catches the error
- THEN a trace record is created with status `failed` and the error message
- AND the workflow-level audit log records `workflow_step_failed`

### Requirement: Metrics Collection (SHOULD)

The system SHOULD collect aggregate metrics: executions per agent, average latency, error rate, token usage per provider. These metrics MAY be exposed via a lightweight metrics endpoint.

#### Scenario: Aggregate metrics available

- GIVEN a system with multiple agent executions
- WHEN metrics are queried
- THEN they return execution_count, p50/p95 latency, error_rate, and total_tokens per agent

### Requirement: Non-Fatal Audit (MUST)

A failure to write a trace or audit event MUST NOT interrupt agent execution or workflow completion. The runtime MUST log the failure and continue.

#### Scenario: Trace write failure

- GIVEN an agent execution that completes successfully
- WHEN the trace persistence fails (e.g., DB unavailable)
- THEN the agent result is still returned to the workflow
- AND a warning is logged
