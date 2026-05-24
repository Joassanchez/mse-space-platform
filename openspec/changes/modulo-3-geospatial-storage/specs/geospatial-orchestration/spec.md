# Delta for Geospatial Orchestration

## ADDED Requirements

### Requirement: Pipeline Event Auditing
The orchestrator SHOULD record minimal lifecycle events (start, complete, fail) at key processing boundaries via `audit_logs`. A failure to register an audit event MUST NOT interrupt or break the pipeline — the orchestrator SHOULD log the audit error and continue processing.

#### Scenario: Audit pipeline start
- GIVEN a batch of raw files ready for processing
- WHEN the pipeline begins processing the batch
- THEN an audit entry is created in `audit_logs` for the batch start
- AND the `entity_type`, `action`, and `actor_type` values use centralized constants or an enum, not raw string literals scattered across the code

#### Scenario: Audit registration failure is non-fatal
- GIVEN a pipeline that fails to write an audit log entry
- WHEN the orchestrator catches the audit failure
- THEN the pipeline MUST continue processing without interruption
- AND the audit error is logged for diagnostics

## MODIFIED Requirements

### Requirement: End-to-End Pipeline Execution
The system MUST orchestrate the complete data processing pipeline through the `SMAPGeospatialService`. The orchestrator MAY emit audit events at key processing boundaries (batch start, job success, job failure) without altering the existing pipeline logic.
(Previously: MUST orchestrate complete pipeline via SMAPGeospatialService)

#### Scenario: Execute full pipeline via CLI
- GIVEN a trigger from the CLI
- WHEN the orchestrator executes the SMAP pipeline
- THEN raw files are discovered, processed, and persisted — the download phase is handled by Módulo 1 (ingestion), not by the geospatial pipeline
- AND corresponding audit events are recorded for the batch execution in `audit_logs`