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
 
 The system MUST orchestrate the complete pipeline (discovery, reading, validation, processing, writing, and persistence) using `SMAPGeospatialService` as the first concrete implementation.
 
 #### Scenario: Execute full pipeline via CLI
 
 - GIVEN a valid SMAP raw file in the database
 - WHEN the CLI command `python -m src.geospatial.cli.process_smap` is executed
 - THEN it MUST run the full ETL pipeline for SMAP files
 - AND support processing a specific `raw_file_id` argument
 
 ### Requirement: Job State Management and Error Isolation
 
 The system MUST create jobs and update their state (pending, running, completed, completed_with_warnings, failed, skipped). Errors in one file MUST NOT break the processing of other files in the batch.
 
 #### Scenario: Controlled error handling in batch processing
 
 - GIVEN a batch of raw files where one file is corrupted
 - WHEN the orchestrator processes the batch
 - THEN it MUST mark the corrupted file's job as `failed`
 - AND continue processing the remaining files successfully
