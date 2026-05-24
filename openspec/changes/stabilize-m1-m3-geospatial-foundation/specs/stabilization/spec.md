# stabilization — Delta Specification

## Purpose

Correcciones de estabilización sobre capacidades existentes de los Módulos 1, 2 y 3.
Extiende las specs base en `openspec/specs/`.

## Requirements

### R-C2-1: ProcessedLayer INSERT con data_source_id (C2)

**Extends:** `geospatial-persistence/spec.md` — Requirement: Data Source Lineage

The system MUST persist `data_source_id` when inserting into `processed_geospatial_layers`.

- `ProcessedLayerRepositoryImpl.insert()` MUST include `data_source_id` in the INSERT columns.
- The orchestrator (`_process_single_file`) MUST resolve and pass `data_source_id` when constructing the `ProcessedLayer`.
- The value MUST be obtained from the `data_sources` table via `source_code` lookup, or propagated from `raw_file` context.
- If resolution fails, `data_source_id` MUST be logged as a warning and left as NULL (non-fatal).

#### Scenario: Persist data_source_id on insert

- GIVEN a raw_file associated with a known data source (e.g. source_code="SMAP")
- WHEN the orchestrator persists the processed layer
- THEN `data_source_id` in `processed_geospatial_layers` MUST reference the correct `data_sources.id`
- AND existing records without `data_source_id` MUST NOT be affected

### R-C2-2: ProcessedLayer INSERT con footprint_geometry (C2)

**Extends:** `geospatial-persistence/spec.md` — Requirement: Optional Footprint Geometry

The system SHOULD persist `footprint_geometry` as an EPSG:4326 Polygon when the native CRS is safely transformable.

- The `ProcessedLayer` construction MUST attempt to build `footprint_geometry` from `metadata.bounds` and `metadata.crs`.
- If `metadata.crs` is transformable to EPSG:4326 using pyproj/rasterio, the 4-corner bbox MUST be converted to a Polygon.
- If transformation is unsafe, the CRS is missing, or `bounds` are unavailable, `footprint_geometry` MUST be NULL.
- The decision to set NULL MUST be explicit (not accidental omission).

#### Scenario: Build footprint_geometry when transformable (EPSG:6933)

- GIVEN a raster with CRS "EPSG:6933" (EASE-Grid 2.0) and valid bounds
- WHEN the ProcessedLayer is constructed
- THEN `footprint_geometry` SHOULD be a valid Polygon in EPSG:4326
- AND the bbox corners MUST be transformed from EPSG:6933 to EPSG:4326

#### Scenario: Leave NULL when CRS is not transformable

- GIVEN a raster with CRS that cannot be safely transformed to EPSG:4326
- WHEN the ProcessedLayer is constructed
- THEN `footprint_geometry` MUST be NULL
- AND a warning SHOULD be logged

### R-C2-3: get_by_raw_file_and_variable devuelve campos nuevos (C2)

**Extends:** `geospatial-persistence/spec.md` — Requirement: Processed Layer Persistence

The system MUST return `data_source_id` and `footprint_geometry` when reading processed layers.

- `ProcessedLayerRepositoryImpl.get_by_raw_file_and_variable()` MUST populate both fields from the DB result.
- The `ProcessedLayer` dataclass already has both fields as `Optional` — no model changes needed.

### R-C1-1: Eliminar hasattr fallback en GeoTIFFWriter (C1)

**Extends:** `geotiff-writing/spec.md` — Requirement: Spatial Metadata Inclusion

The system MUST NOT rely on `GeospatialMetadata.nodata_value` (which does not exist) as a fallback.

- The `hasattr(metadata, 'nodata_value')` check in `_write_to_tmp()` MUST be removed.
- The `nodata_value` parameter in `write()` is the single source of truth for nodata metadata.
- If `nodata_value` is None, the GeoTIFF MUST be written without nodata metadata (caller's responsibility).
- The orchestrator already passes `nodata_value=extracted.nodata_value` — this MUST be preserved.

#### Scenario: nodata written correctly in GeoTIFF

- GIVEN a processed array with known nodata_value (e.g. -9999.0)
- WHEN GeoTIFFWriter.write() is called with that nodata_value
- THEN the resulting GeoTIFF MUST report the nodata value in its metadata
- AND the fallback path (hasattr) MUST NOT be used

### R-C3-1: Corregir autoasignación en smap_reader.py (C3)

**Extends:** `hdf5-reading/spec.md`

The system MUST NOT contain dead self-assignments in coordinate transform logic.

- Line `y_coords = y_coords` in `_build_transform_from_coords()` MUST be changed to `y_1d = y_coords`.
- The behavior for 1D y_coord arrays MUST remain functionally identical.

#### Scenario: 1D coordinates handled correctly

- GIVEN a 1D y_coordinate array
- WHEN `_build_transform_from_coords()` processes it
- THEN `y_1d` MUST contain the original y_coords array
- AND the dead self-assignment MUST NOT execute

### R-A1-1: Conexión PostgreSQL compartida (A1)

A shared `get_connection()` function MUST be extracted to a common module.

- A new file `src/geospatial/infrastructure/persistence/connection.py` MUST define `get_connection()` (public).
- `postgres_repositories.py` MUST import `get_connection` from the new module and MUST keep `_get_connection` as a public alias for backward compatibility.
- All 7 Module 3 repos (`regions_repo.py`, `data_sources_repo.py`, `indicators_repo.py`, `risk_assessments_repo.py`, `alerts_repo.py`, `economic_impacts_repo.py`, `audit_repo.py`) MUST import `get_connection` from the shared module.

#### Scenario: Shared connection function callable from all repos

- GIVEN any persistence repository
- WHEN it needs a database connection
- THEN it MUST obtain it via `get_connection()` from `connection.py`
- AND the function signature and behavior MUST be identical to the previous `_get_connection()`

### R-A2-1: Flag --metadata-backend en CLI (A2)

**Extends:** Capability `smap-ingestion`

The CLI MUST allow choosing the metadata persistence backend.

- `run_smap_ingestion.py` MUST accept `--metadata-backend {json|postgresql}`.
- Default: `json` (preserves existing development workflow).
- `JobManager` MUST accept the backend choice and instantiate the correct repository.
- Production recommendation: `postgresql`.

#### Scenario: Run with JSON backend (default)

- GIVEN no `--metadata-backend` flag
- WHEN `run_smap_ingestion.py` starts
- THEN it MUST use `MetadataRepository` (JSON) as today

#### Scenario: Run with PostgreSQL backend

- GIVEN `--metadata-backend postgresql`
- WHEN `run_smap_ingestion.py` starts
- THEN it MUST use `PostgreSQLMetadataRepository`
- AND it MUST fail gracefully if PostgreSQL is unavailable

### R-A3-1: Separar sources.yaml (evaluar)

**IF** the separation of `sources.yaml` into domain-specific files can be done without modifying `config_loader.py` parsing logic, THEN:
- `sources:` section SHOULD remain in `sources.yaml` (or move to `ingestion-sources.yaml`)
- `geospatial:` section SHOULD move to `geospatial-sources.yaml`
- `config_loader.py` MUST load both files when both exist

**IF** the separation requires refactoring `config_loader.py`, THEN this requirement is deferred to a future iteration and MUST be documented as technical debt.

## Capabilities Modified

| Capability | Spec extended | Requirements added |
|---|---|---|
| `geospatial-persistence` | `openspec/specs/geospatial-persistence/spec.md` | R-C2-1, R-C2-2, R-C2-3, R-A1-1 |
| `geotiff-writing` | `openspec/specs/geotiff-writing/spec.md` | R-C1-1 |
| `hdf5-reading` | `openspec/specs/hdf5-reading/spec.md` | R-C3-1 |
| `smap-ingestion` | — | R-A2-1 |
| `config` | — | R-A3-1 |
