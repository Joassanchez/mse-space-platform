 # geospatial-orchestration Specification
 
 ## Purpose
 
 Orquestación del pipeline ETL geoespacial, descubrimiento de archivos y manejo del estado de los trabajos. Implementa extensibilidad aislando componentes genéricos de implementaciones concretas como SMAP.
 
 ## Requirements
 
 ### Requirement: Extensible Orchestration Architecture
 
 The system MUST decouple orchestration logic from specific data sources, defining a `GeospatialOrchestrator` that uses generic interfaces (`GeospatialReader`, `GeospatialValidator`) while supporting concrete implementations like `SMAPHDF5Reader` and `SMAPValidationService`.
 
 #### Scenario: Add a new geospatial source
 
 - GIVEN a future source with its own reader, validator and variable configuration
 - WHEN the source is registered in the geospatial pipeline
 - THEN the system MUST reuse the generic raster processing, GeoTIFF writing, job tracking and persistence components
 - AND it MUST NOT require rewriting the core orchestration or persistence model
 
 ### Requirement: Raw File Discovery
 
 The system MUST discover raw files with `completed` status from the PostgreSQL database that are pending geospatial processing.
 
 #### Scenario: Discover pending files
 
 - GIVEN raw files in `completed` status without associated geospatial processing jobs
 - WHEN the orchestrator queries for files to process
 - THEN it MUST return the pending files
 - AND support an optional `--limit` flag to restrict the batch size
 
### Requirement: End-to-End Pipeline Execution

The system MUST orchestrate the complete data processing pipeline through the `SMAPGeospatialService`. The orchestrator MAY emit audit events at key processing boundaries (batch start, job success, job failure) without altering the existing pipeline logic.

#### Scenario: Execute full pipeline via CLI

- GIVEN a trigger from the CLI
- WHEN the orchestrator executes the SMAP pipeline
- THEN raw files are discovered, processed, and persisted — the download phase is handled by Módulo 1 (ingestion), not by the geospatial pipeline
- AND corresponding audit events are recorded for the batch execution in `audit_logs`
 
 ### Requirement: Pipeline Event Auditing

The orchestrator SHOULD record minimal lifecycle events (start, complete, fail) at key processing boundaries via `audit_logs`. A failure to register an audit event MUST NOT interrupt or break the pipeline — the orchestrator SHOULD log the audit error and continue processing. The `entity_type`, `action`, and `actor_type` values MUST use centralized constants or an enum, not raw string literals scattered across the code.

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

### Requirement: Job State Management and Error Isolation
 
 The system MUST create jobs and update their state (pending, running, completed, completed_with_warnings, failed, skipped). Errors in one file MUST NOT break the processing of other files in the batch.
 
 #### Scenario: Controlled error handling in batch processing
 
 - GIVEN a batch of raw files where one file is corrupted
 - WHEN the orchestrator processes the batch
 - THEN it MUST mark the corrupted file's job as `failed`
 - AND continue processing the remaining files successfully
