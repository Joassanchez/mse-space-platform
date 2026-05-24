 # Tasks: Módulo 2 — ETL Geoespacial SMAP

 ## Review Workload Forecast

 | Field | Value |
 |-------|-------|
 | Estimated changed lines | ~900-1100 lines (10 new files + tests + migration + config) |
 | 800-line budget risk | High |
 | Chained PRs recommended | Yes |
 | Delivery strategy | single-pr-default → stacked-slices |
 | Chain strategy | stacked-to-main |

 Decision needed before apply: No (user approved stacked-to-main)
 Chained PRs recommended: Yes
 Chain strategy: stacked-to-main
 800-line budget risk: High

 ### Suggested Work Units

 | Unit | Goal | PR | Base | Est. lines |
 |------|------|----|------|------------|
 | 1 | Codebase inspection + Foundation (domain, migration, config, __init__) | PR 1 | main | ~250-300 |
 | 2 | Core implementations (reader, validator, writer, raster processing, repos, requirements) | PR 2 | main | ~400-500 |
 | 3 | Orchestration + CLI + Tests + Documentation | PR 3 | main | ~300-350 |

 ---

 ## Slice 1 — Foundation (PR #1)

 ### Phase 0: Codebase Inspection

 - [x] 0.1 Inspect `migrations/001_create_tables.sql`: confirm `raw_files` table name, columns, PK type, FK patterns
 - [x] 0.2 Inspect `src/storage/metadata_repository_pg.py`: review `_get_connection()` utility, env vars pattern, psycopg2 usage
 - [x] 0.3 Inspect `src/config/sources.yaml` and `config_loader.py`: review existing config convention (YAML + Pydantic)
 - [x] 0.4 Inspect `Dockerfile`: check if libhdf5-dev is present, note if GDAL deps will be needed for rasterio

 ### Phase 1: Foundation (Domain + Migration + Config)

 - [x] 1.1 Create `src/geospatial/__init__.py`
 - [x] 1.2 Create `src/geospatial/domain/__init__.py`
 - [x] 1.3 Create `src/geospatial/domain/errors.py` with `ValidationError`, `ReadError`, `WriteError`, `IdempotencySkip`
 - [x] 1.4 Create `src/geospatial/domain/models.py` with dataclasses: `ExtractedVariable` (data, attributes, units, nodata_value, acquisition_date), `GeospatialMetadata` (crs, transform, bounds, resolution, width, height), `RasterProcessingResult` (data, metadata, statistics, warnings), `ProcessedLayer` (raw_file_id, variable_name, file_path, crs, bbox, stats, acquisition_date, processing_version), `GeospatialProcessingJob` (raw_file_id, source_code, status, timestamps, error_message, warnings)
 - [x] 1.5 Create `src/geospatial/domain/interfaces.py` with ABCs: `GeospatialReader`, `GeospatialValidator`, `RawFileDiscoveryRepository`, `GeospatialProcessingJobRepository`, `ProcessedLayerRepository`
 - [x] 1.6 Create `migrations/002_create_tables.sql` with:
   - `geospatial_processing_jobs` (id PK, raw_file_id FK → raw_files(id), source_code, status CHECK, started_at, finished_at, error_message, warnings TEXT[], created_at)
   - `processed_geospatial_layers` (id SERIAL PK, processing_job_id FK → geospatial_processing_jobs(id), raw_file_id FK → raw_files(id), source_code, variable_name, file_path, crs, bbox NUMERIC[], resolution_x/y, width, height, nodata_value, min/max/mean_value, valid/nodata_pixel_count, acquisition_date, processing_version, created_at)
   - `UNIQUE(raw_file_id, variable_name, processing_version)`
   - `UNIQUE(file_path)`
 - [x] 1.7 Follow existing config convention: add geospatial section to `src/config/sources.yaml` (variables list, ROI settings, nodata value, processing_version), mirroring existing SMAP config pattern
 - [x] 1.8 Add `rasterio` to `requirements.txt`; review if `libgdal-dev` or equivalent is needed in Dockerfile for rasterio build

 ---

 ## Slice 2 — Core Implementations (PR #2)

 ### Phase 2: Infrastructure + Application

 - [x] 2.1 Create `src/geospatial/infrastructure/__init__.py`
 - [x] 2.2 Create `src/geospatial/infrastructure/hdf5/__init__.py`
 - [x] 2.3 Create `src/geospatial/infrastructure/hdf5/smap_reader.py` with `SMAPHDF5Reader` implementing `GeospatialReader` (open via h5py, extract_variable returns ExtractedVariable, get_metadata returns GeospatialMetadata with CRS derivado/validado desde metadata del archivo)
 - [x] 2.4 Create `src/geospatial/application/__init__.py`
 - [x] 2.5 Create `src/geospatial/application/smap_validation_service.py` with `SMAPValidationService` implementing `GeospatialValidator` (validate_structure: file exists, legible HDF5, grupos mínimos; validate_variable: dimensiones esperadas desde config/metadata, rangos físicos, metadata espacial mínima)
 - [x] 2.6 Create `src/geospatial/infrastructure/raster/__init__.py`
 - [x] 2.7 Create `src/geospatial/infrastructure/raster/geotiff_writer.py` with `GeoTIFFWriter`:
   - escribe a `.tmp` en el mismo directorio destino
   - solo hace `os.rename()` (atomic move) a ruta final si escritura + validación básica OK
   - si falla, elimina `.tmp` y propaga error
   - genera output path determinístico: `data/processed/{source}/{variable}/{YYYY}/{MM}/{source}_{variable}_{acquisition_datetime}_{processing_version}.tif`
   - agnóstico de fuente (no depende de SMAP)
 - [x] 2.8 Create `src/geospatial/application/raster_processing_service.py` con `RasterProcessingService`:
   - manejo de nodata (reemplazar fill value por NaN si corresponde)
   - construir CRS y transform desde GeospatialMetadata
   - ROI clipping: si deshabilitado → raster completo; si habilitado → reproyectar geometría ROI (EPSG:4326) al CRS del raster antes de recortar; si ROI path inválido → error controlado
   - calcular estadísticas (min, max, mean, valid/nodata pixel count)
   - agnóstico de fuente
 - [x] 2.9 Create `src/geospatial/infrastructure/persistence/__init__.py`
 - [x] 2.10 Create `src/geospatial/infrastructure/persistence/postgres_repositories.py` con 3 implementaciones PostgreSQL:
   - `RawFileDiscoveryRepository`: `find_completed(source, limit)`, `find_by_id(raw_file_id)`
   - `GeospatialProcessingJobRepository`: `create(job)`, `update_status(job_id, status, error)`, `exists_by_raw_file_variable(raw_file_id, variable, version)`
   - `ProcessedLayerRepository`: `insert(layer)`, `get_by_raw_file_and_variable(raw_file_id, variable, version)`

 ---

 ## Slice 3 — Orchestration + CLI + Tests (PR #3)

 ### Phase 3: Orchestration + CLI

 - [x] 3.1 Create `src/geospatial/application/orchestrator.py` with `GeospatialOrchestrator` coordinating pipeline: discovery → idempotency check → create job → read → validate → process raster → write GeoTIFF (temp → atomic move) → persist layer → finalize job. Usa ports, no implementaciones concretas. Maneja errores por archivo sin romper batch.
 - [x] 3.2 Create `src/geospatial/cli/__init__.py`
 - [x] 3.3 Create `src/geospatial/cli/process_smap.py` with CLI:
   - `--limit N` (default: todos)
   - `--raw-file-id ID` (procesar específico)
   - `--processing-version VER` (default: v1)
   - `--roi-enabled` (default: true)
   - `--roi-path PATH` (default: de config)
   - exit codes: 0 = OK, 1 = fallos, 2 = config/args inválidos
 - [x] 3.4 Wire `src/geospatial/__init__.py` exports for all subpackages

 ### Phase 4: Testing

 - [x] 4.1 Unit: `tests/geospatial/unit/test_smap_reader.py` — mock h5py, test open, extract_variable, get_metadata, invalid file error
 - [x] 4.2 Unit: `tests/geospatial/unit/test_smap_validation_service.py` — test structure validation, range validation, missing metadata
 - [x] 4.3 Unit: `tests/geospatial/unit/test_raster_processing_service.py` — synthetic numpy arrays, test nodata, CRS, transform, ROI clipping enabled/disabled
 - [x] 4.4 Unit: `tests/geospatial/unit/test_geotiff_writer.py` — test .tmp write, atomic move, clean up on failure, deterministic path generation
 - [x] 4.5 Unit: `tests/geospatial/unit/test_repositories.py` — mock psycopg2, test CRUD, idempotency check, exists_by_raw_file_variable
 - [x] 4.6 Integration: `tests/geospatial/integration/test_pipeline.py` — real HDF5 + PostgreSQL; process file, verify GeoTIFF opens in rasterio, verify DB records
 - [x] 4.7 Integration: `tests/geospatial/integration/test_idempotency.py` — process same file twice: first = completed, second = skipped, no duplicate .tif on disk, unique constraint verified

 ### Phase 5: Documentation + Verification

 - [x] 5.1 Add docstrings to all public methods in orchestrator and CLI
 - [x] 5.2 Verify migration applies cleanly: `psql -U mse_user -d mse_platform -f migrations/002_create_tables.sql` (noted, not executed)
 - [x] 5.3 Run full test suite: `pytest tests/geospatial/unit/ -v` → 77 unit tests passing (target 40+ exceeded)
 - [x] 5.4 Add pytest markers for integration tests (mark.integration) with auto-skip
