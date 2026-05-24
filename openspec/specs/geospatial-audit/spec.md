# Geospatial Audit Specification

## Purpose
Defines a transversal technical audit logging mechanism for analytical entities and system events, operating independently of human users. The audit mechanism MUST be non-invasive: a failure to write an audit entry MUST NOT block or alter the originating operation.

## Requirements

### Requirement: Technical Audit Logging
The system SHOULD record significant state changes and pipeline lifecycle events (start, complete, fail) in the `audit_logs` table. The `entity_type`, `action`, and `actor_type` values MUST use centralized constants, enums, or a shared model — raw string literals MUST NOT be scattered across the codebase. A failure to write an audit entry MUST NOT break the calling operation; the error SHOULD be logged and the operation continues.

#### Scenario: Log analytical entity generation
- GIVEN a successfully calculated indicator or risk assessment
- WHEN the entity is persisted
- THEN an audit log entry SHOULD be created with the corresponding `entity_type` and `action` using centralized constants
- AND the `actor_type` is recorded as `system` or `agent` via a shared enum

#### Scenario: Audit failure is non-fatal
- GIVEN a pipeline that fails to persist an audit log entry
- WHEN the audit write operation fails
- THEN the originating operation MUST complete without interruption
- AND the audit error is logged using the existing logging mechanism

#### Scenario: Metadata preservation
- GIVEN a complex state transition with contextual payload
- WHEN the audit entry is created
- THEN the context is saved in the `metadata` JSONB column for future inspection