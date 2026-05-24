 # Delta for geospatial-persistence

 ## ADDED Requirements

 ### Requirement: Generic Persistence Components

 The system MUST decouple persistence using generic `ProcessedLayerRepository` and `GeospatialProcessingJobRepository` components, ensuring the data model accommodates future sources beyond SMAP.

 #### Scenario: Persist data from new source

 - GIVEN processing results from a non-SMAP source
 - WHEN the persistence layer is invoked
 - THEN it MUST successfully record the job and layer without schema modifications

 ### Requirement: Job Completes With Warnings

 The system MUST record the state as `completed_with_warnings` if the raster was generated successfully but non-critical issues occurred during processing.

 #### Scenario: Job completes with non-fatal warnings

 - GIVEN a GeoTIFF was generated successfully but non-critical warnings were emitted
 - WHEN the orchestrator finalizes the job
 - THEN it MUST record the state as `completed_with_warnings`
 - AND persist the warnings

 ### Requirement: Deterministic File Creation

 Idempotent reprocessing MUST NOT create a second physical file unless a new processing version is explicitly requested.

 #### Scenario: Idempotent path generation

 - GIVEN an existing GeoTIFF on disk for a specific version
 - WHEN a redundant processing job runs
 - THEN it MUST NOT create a duplicate physical file

 ## MODIFIED Requirements

 ### Requirement: Idempotency Verification (RF-12)

 The system MUST prevent duplicate processing for the same combination of `raw_file_id`, `variable_name`, and `processing_version`. Explicit reprocessing MUST require a new `processing_version`, and the system MUST NOT silently overwrite an existing layer.

 #### Scenario: Attempt to process an already completed file

 - GIVEN a raw file and variable that have already been processed
 - WHEN the pipeline is triggered for this combination
 - THEN it MUST detect the existing record, skip the processing, and mark the job as `skipped`

 #### Scenario: Request explicit reprocessing

 - GIVEN a raw file that has already been processed
 - WHEN the system is explicitly configured to reprocess it
 - THEN it MUST require a new `processing_version`
 - AND MUST NOT silently overwrite an existing layer or record
