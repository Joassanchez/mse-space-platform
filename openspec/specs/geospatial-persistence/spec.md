# geospatial-persistence Specification

## Purpose
Registro de jobs y capas procesadas en PostgreSQL con idempotencia.

## Requirements

### Requirement: Processed Layer Persistence (RF-10)
The system MUST record metadata for every successfully processed layer in PostgreSQL.

#### Scenario: Successfully record a processed layer
- GIVEN a successfully generated GeoTIFF and its calculated statistics
- WHEN the persistence service is called
- THEN it MUST create a new record in `processed_geospatial_layers` linking back to the raw file

### Requirement: Processing Job Tracking (RF-11, RF-14, RF-15)
The system MUST record the execution state (`pending`, `running`, `completed`, `failed`, etc.) and any errors of each pipeline job in `geospatial_processing_jobs`.

#### Scenario: Job completes with errors
- GIVEN a job that fails during validation
- WHEN the orchestrator finalizes the job
- THEN it MUST record the state as `failed` and log the specific error message

### Requirement: Idempotency Verification (RF-12)
The system MUST prevent duplicate processing for the same combination of `raw_file_id`, `variable_name`, and `processing_version`.

#### Scenario: Attempt to process an already completed file
- GIVEN a raw file and variable that have already been processed
- WHEN the pipeline is triggered for this combination
- THEN it MUST detect the existing record, skip the processing, and mark the job as `skipped`

#### Scenario: Request explicit reprocessing
- GIVEN a raw file that has already been processed
- WHEN the system is explicitly configured to reprocess it
- THEN it MUST overwrite or create a new processing record as per the versioning strategy
