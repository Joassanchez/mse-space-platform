# Tasks: Módulo 1 - Ingesta de Datos SMAP

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~650-750 lines |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Slice 1 first (core PR), Slice 2 (PostgreSQL) como cambio separado posterior |
| Delivery strategy | single-pr (para Slice 1); Slice 2 es un cambio independiente post-verificación |
| Chain strategy | size:exception (800-line budget accepted) |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size:exception
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Apply order | Notes |
|------|------|-------------|-------|
| 1 | **Slice 1**: Core + JSON metadata | Ahora (sdd-apply) | ~550 lines; tests included; no DB; este es el primer cambio |
| 2 | **Slice 2**: PostgreSQL | Posterior, solo tras verificar Slice 1 | ~150 lines; cambio independiente, nuevo ciclo SDD |

---

## Phase 1: Project Setup & Configuration (~2h)

- [x] 1.1 Create `src/`, `data/raw/`, `data/processed/`, `data/metadata/`, `tests/` directory structure
- [x] 1.2 Create `requirements.txt` with: earthaccess, pydantic, h5py, rich, pytest, python-dotenv, pyyaml
- [x] 1.3 Create `.env.example` with EARTHDATA_USERNAME, EARTHDATA_PASSWORD, MAX_DAYS_RANGE=7
- [x] 1.4 Create `data/.gitignore` ignoring `raw/` and `processed/` directories
- [x] 1.5 Create `src/config/sources.yaml` with SMAP config (bbox, max_days_range, product_id)
- [x] 1.6 Create `src/config/config_loader.py` with Pydantic models for YAML validation

## Phase 2: Core Interfaces & Base Connector (~3h)

- [x] 2.1 Create `src/__init__.py`, `src/ingestion/__init__.py`, `src/storage/__init__.py`, `src/models/__init__.py`, `src/jobs/__init__.py`
- [x] 2.2 Create `src/ingestion/base_connector.py` with abstract `BaseIngestionConnector` class
- [x] 2.3 Define abstract methods: `search()`, `download()`, `validate()`, `extract_metadata()`, `register()`
- [x] 2.4 Create `src/models/job_models.py` with JobState enum, RawFile (include: granule_id, source_product_id, remote_url, acquisition_date, file_name, size_bytes, checksum_sha256, file_path, ready_for_etl), IngestionJob Pydantic models

## Phase 3: SMAP Connector Implementation (~6h)

- [x] 3.1 Create `src/ingestion/smap/__init__.py` and `smap_connector.py`
- [x] 3.2 Implement earthaccess authentication using EARTHDATA_USERNAME/PASSWORD env vars
- [x] 3.3 Implement `search(bbox, start_date, end_date)` method querying SPL4SMGP.008 products
- [x] 3.4 Add date range validation (reject if > MAX_DAYS_RANGE, default 7)
- [x] 3.5 Add bbox validation (lon -180..180, lat -90..90)
- [x] 3.6 Create `src/ingestion/smap/smap_downloader.py` with download logic
- [x] 3.7 Implement `--search-only` flag: list results without downloading, job completed without ready_for_etl
- [x] 3.8 Implement idempotency using composite key: `(source_product_id OR file_name + size_bytes)` — check if already registered by source_product_id or by (file_name + size). If found, compare SHA-256 against metadata.json and skip if match
- [x] 3.9 Handle orphan files: if file exists on disk (by name + size) but no metadata entry, compute checksum and register without re-downloading
- [x] 3.10 Download files to `data/raw/smap/YYYY/MM/` using product acquisition date (not execution date)

## Phase 4: Storage & Metadata Repository (~4h)

- [x] 4.1 Create `src/storage/raw_storage.py` with RawStorage class for filesystem operations
- [x] 4.2 Implement SHA-256 checksum calculation for downloaded files
- [x] 4.3 Create `src/storage/metadata_repository.py` with MetadataRepository class (JSON-based for Slice 1)
- [x] 4.4 Implement `save_job(job: IngestionJob)` writing to `data/metadata/job_{id}.json`
- [x] 4.5 Implement `get_job(job_id: str)` reading from JSON file
- [x] 4.6 Implement `check_file_registered(file_name: str, job_id: str)` for idempotency checks

## Phase 5: Job Management & State Machine (~3h)

- [x] 5.1 Create `src/jobs/job_manager.py` with JobManager class
- [x] 5.2 Implement state transitions with clear rules:
  - `pending` → `running`: job starts
  - `running` → `completed`: ALL files downloaded + validated successfully
  - `running` → `completed_with_warnings`: ≥1 file OK, ≥1 file failed after retries (partial success)
  - `running` → `failed`: 0 files downloaded (all failed), OR authentication error, OR search error
- [x] 5.3 Implement `ready_for_etl` logic:
  - `true` if job is `completed` OR `completed_with_warnings` (≥1 file valid and ready)
  - `false` if job is `failed`, `pending`, `running`, or `--search-only` mode (no files to process)
- [x] 5.4 Implement error handling with retry logic for download failures (max 3 retries, exponential backoff)
- [x] 5.5 Log detailed error per file: which file failed, why, how many retries attempted

## Phase 6: CLI Entry Point (~2h)

- [x] 6.1 Create `src/jobs/run_smap_ingestion.py` as main entry point
- [x] 6.2 Add CLI args: --bbox, --start-date, --end-date, --search-only, --config
- [x] 6.3 Wire JobManager → SmapConnector → RawStorage → MetadataRepository
- [x] 6.4 Add rich console output for job progress and final status

## Phase 7: Testing (~4h)

- [x] 7.1 Create `tests/unit/test_config_loader.py` testing YAML parsing and validation
- [x] 7.2 Create `tests/unit/test_job_state_machine.py` testing state transitions
- [x] 7.3 Create `tests/unit/test_idempotency.py` testing checksum match/orphan/no-file scenarios
- [x] 7.4 Create `tests/unit/test_date_range_validation.py` testing MAX_DAYS_RANGE enforcement
- [x] 7.5 Create `tests/unit/test_smap_connector.py` mocking earthaccess library
- [x] 7.6 Create `tests/integration/conftest.py` with `pytest.skip_if_no_credentials()` helper that checks for `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD` env vars and skips all integration tests if missing
- [x] 7.7 Create `tests/integration/test_earthdata_auth.py` (marked @pytest.mark.integration, auto-skip if no credentials)
- [x] 7.8 Create `tests/integration/test_smap_search.py` (marked @pytest.mark.integration, auto-skip if no credentials, limited to 1 file)

## Phase 8: Slice 2 — PostgreSQL (~5h)

- [x] 8.1 Create `docker-compose.yml` with PostgreSQL 15+ service (no PostGIS)
- [x] 8.2 Create `src/storage/metadata_repository_pg.py` with PostgreSQLMetadataRepository
- [x] 8.3 Create `migrations/001_create_tables.sql` with data_sources, datasets, ingestion_jobs, raw_files tables
- [x] 8.4 Create `scripts/migrate_metadata_to_pg.py` to migrate JSON files to PostgreSQL
- [x] 8.5 Create `tests/integration/test_postgresql_repository.py` (requires Docker, marked @pytest.mark.integration)
