# geospatial-persistence Specification

## Purpose
Registro de jobs y capas procesadas en PostgreSQL con idempotencia.

## Requirements

### Requirement: Processed Layer Persistence (RF-10)
The system MUST record every processed layer in PostgreSQL. The system MUST maintain the native raster bounds in `bbox NUMERIC[]` — this column preserves the original CRS bounds and MUST NOT be replaced or removed. A new `footprint_geometry GEOMETRY(Polygon, 4326)` column MAY be added as optional storage for EPSG:4326 coverage queries.

#### Scenario: Successfully record a processed layer
- GIVEN a processed GeoTIFF with calculated statistics
- WHEN the persistence service is called
- THEN it creates a new record in `processed_geospatial_layers`
- AND it populates `bbox` with the native CRS bounds (preserved and unchanged)
- AND it MAY optionally populate `footprint_geometry` as an EPSG:4326 Polygon when the CRS transformation is safe

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

### Requirement: Data Source Lineage
The system MUST link processed geospatial layers to their original data source via `data_source_id`.

#### Scenario: Record lineage for processed layer
- GIVEN a raw file with resolvable lineage to `data_sources` (via the existing `source_id` or `source_code` relationship)
- WHEN a new processed layer is persisted
- THEN `data_source_id` MUST be populated referencing the `data_sources` table when the lineage is resolvable
- AND existing records MAY keep `data_source_id` as NULL — no destructive migration is required

### Requirement: Optional Footprint Geometry
The system SHOULD add a `footprint_geometry GEOMETRY(Polygon, 4326)` column with a GIST index to `processed_geospatial_layers`. Populating this column is OPTIONAL and MUST only be attempted when the native CRS can be safely transformed to EPSG:4326.

#### Scenario: Schema includes footprint_geometry
- GIVEN the Módulo 3 migration is applied
- THEN `processed_geospatial_layers` has the `footprint_geometry` column and a GIST index
- AND existing records have `footprint_geometry` as NULL — no backfill required

#### Scenario: Populate footprint when safe to transform
- GIVEN a processed layer with a known native CRS (e.g., EPSG:6933) and valid raster bounds
- WHEN the CRS transformation to EPSG:4326 is technically safe
- THEN `footprint_geometry` MAY be populated as an EPSG:4326 Polygon representing the raster coverage
- AND if the transformation is unreliable or the CRS is missing, the column MUST remain NULL
