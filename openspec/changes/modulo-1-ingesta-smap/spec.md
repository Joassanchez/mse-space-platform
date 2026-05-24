# Delta for Módulo 1 - Ingesta de Datos SMAP

## ADDED Requirements

### Requirement: Data Ingestion (data-ingestion)

The system MUST provide a declarative configuration mechanism for data sources via YAML.
The system MUST support a base interface `BaseIngestionConnector` for extensible connector implementations.
The system MUST NOT version `data/raw/` and `data/processed/` directories (enforced via `.gitignore`).
The system MUST enforce a configurable maximum date range for ingestion requests, with a DEFAULT of 7 days, to prevent mass downloads. The limit MUST be overridable via configuration (`sources.yaml` or environment variable `MAX_DAYS_RANGE`).
The system MUST support a bounding box (bbox) parameter to filter searches. The bbox MUST ONLY be used for search filtering and MUST NOT imply geospatial clipping or reprojection of the raw data.

#### Scenario: Requesting ingestion within the configured max range
- GIVEN a valid bbox and a date range within the configured limit (default: 7 days)
- WHEN the ingestion job is triggered
- THEN the system MUST proceed with the ingestion process

#### Scenario: Requesting ingestion exceeding the configured max range
- GIVEN a date range that exceeds the configured limit (default: 7 days)
- WHEN the ingestion job is triggered
- THEN the system MUST reject the request and return an error indicating the limit was exceeded
- AND the error MUST include the current configured limit value

#### Scenario: Overriding the max range via configuration
- GIVEN a configuration with `MAX_DAYS_RANGE=14` and a date range of 10 days
- WHEN the ingestion job is triggered
- THEN the system MUST accept the request (10 ≤ 14)
- AND proceed with the ingestion process

### Requirement: SMAP Connector (smap-connector)

The system MUST implement a connector for NASA Earthdata using the `earthaccess` library.
The system MUST authenticate using `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD` environment variables.
The system MUST search for SPL4SMGP.008 products within the specified bbox and date range.
The system MUST support a `--search-only` flag to list results without downloading.
The system MUST download the identified HDF5 files into the `data/raw/smap/YYYY/MM/` directory if `--search-only` is not provided. The `YYYY/MM` subdirectory MUST be derived from the **product's acquisition/timestamp date**, NOT from the execution date.
The system MUST calculate a SHA-256 checksum for each downloaded file.
The system MUST ensure idempotency by checking if a file with the same name and size exists locally before downloading.
If it exists locally, the system MUST verify the local checksum against the one stored in the metadata registry.
If the checksum matches, the system MUST skip the download and mark the file as `already_downloaded`.
The system MUST NOT assume a remote checksum is available prior to downloading.

#### Scenario: Running in search-only mode
- GIVEN valid search parameters and the `--search-only` flag
- WHEN the SMAP connector executes
- THEN the system MUST list the found products
- AND the system MUST NOT download any files
- AND the system MUST NOT set `ready_for_etl` (there are no files to process)
- AND the job state MUST be `completed` (search succeeded) without `ready_for_etl`

#### Scenario: Downloading a new file
- GIVEN a valid search result for a file not present locally
- WHEN the download phase executes
- THEN the system MUST extract the product's acquisition date from the search result metadata
- AND the system MUST download the HDF5 file to `data/raw/smap/<YYYY>/<MM>/` using the product acquisition date
- AND the system MUST calculate its SHA-256 checksum

#### Scenario: Idempotency — file exists locally with matching checksum in metadata
- GIVEN a file that already exists locally with the correct size and matching checksum in `metadata.json`
- WHEN the download phase executes
- THEN the system MUST skip the download
- AND mark the file as `already_downloaded`

#### Scenario: Idempotency — file exists locally but no metadata registered
- GIVEN a file that already exists locally (orphan file, no entry in `metadata.json`)
- WHEN the download phase executes
- THEN the system MUST compute the SHA-256 checksum of the local file
- AND register the file with its checksum in `metadata.json`
- AND mark the file as `already_downloaded` (without re-downloading)

### Requirement: Metadata Registry (metadata-registry)

**For Slice 1 (~21h effort):**
The system MUST register raw file metadata and checksums in a `metadata.json` file per ingestion job.
The system MUST NOT use a database (including SQLite) in Slice 1.

**For Slice 2 (~5h effort):**
The system MUST support migrating the metadata registry to a PostgreSQL database.
The system MUST NOT use PostGIS extensions in Module 1.

#### Scenario: Registering metadata in Slice 1
- GIVEN a successfully downloaded or verified file
- WHEN the metadata registry operates in Slice 1 mode
- THEN the system MUST write the file's metadata and checksum into the job's `metadata.json`

#### Scenario: Registering metadata in Slice 2
- GIVEN a successfully downloaded or verified file
- WHEN the metadata registry operates in Slice 2 mode
- THEN the system MUST persist the file's metadata into the PostgreSQL database

### Requirement: Job Management (job-management)

The system MUST track the state of each ingestion job.
The system MUST support the following job states: `pending`, `running`, `completed`, `completed_with_warnings`, `failed`.
The system MUST set `ready_for_etl = true` when at least one file is successfully downloaded and validated (even if some files failed).
The system MUST set `ready_for_etl = false` when no files were downloaded (all failed, or `--search-only` mode).
The system MUST gracefully handle and log authentication, search, download, and validation errors.

#### Scenario: Successful ingestion job
- GIVEN a triggered ingestion job where all files download and validate successfully
- WHEN the job finishes
- THEN the system MUST transition the job state to `completed`
- AND the system MUST set `ready_for_etl = true`

#### Scenario: Ingestion job with a download error — partial success
- GIVEN a triggered ingestion job where SOME files download successfully and SOME fail after retries
- WHEN the job finishes
- THEN the system MUST transition the job state to `completed_with_warnings`
- AND the system MUST set `ready_for_etl = true` (the valid files are ready)
- AND the system MUST log each failed file with its error message
- AND successfully downloaded files MUST still be registered in metadata

#### Scenario: Ingestion job with critical failure — no files downloaded
- GIVEN a triggered ingestion job where ALL downloads fail after retries
- OR the authentication step fails entirely
- OR the search step returns an unrecoverable error
- WHEN the job finishes
- THEN the system MUST transition the job state to `failed`
- AND the system MUST set `ready_for_etl = false`
- AND the system MUST log a clear error message explaining the root cause

## Testing Strategy

### Unit Tests (mocked, no external dependencies)
These MUST run offline without credentials or network access. The `earthaccess` library MUST be mocked.

| Test scope | What to test | Mock target |
|------------|-------------|-------------|
| Config loading | YAML parsing, validation, missing fields | None (pure logic) |
| BaseIngestionConnector | Interface contract enforces search/download/validate/register | None (abstract) |
| Idempotency logic | File exists + checksum match → skip; file exists + no metadata → register; file missing → download | Filesystem |
| Metadata JSON | Read/write `metadata.json`, checksum storage, state transitions | Filesystem |
| Job state machine | Transitions: pending→running→completed, pending→running→failed | None (pure logic) |
| Date range validation | Reject over limit, accept within limit, respect config override | None (pure logic) |
| Bbox validation | Valid coordinates pass, invalid bbox rejected | None (pure logic) |

### Integration Tests (require Earthdata credentials)
These MUST be tagged/pytest-marked (`pytest -m integration`) and MUST NOT run by default in CI without credentials.

| Test scope | What to test | Requirements |
|------------|-------------|-------------|
| Earthdata auth | Login with valid credentials succeeds; login with invalid credentials fails | `EARTHDATA_USERNAME`/`PASSWORD` env vars |
| Search + search-only | Real search returns results for valid bbox; `--search-only` lists without downloading | Network + credentials |
| Full download (limited) | Download 1 file within 7-day range, verify checksum, verify directory structure | Network + credentials |
| Idempotency (integration) | Run same search twice, second run skips existing files | Network + credentials |

### Test exclusions
- Unit tests MUST NOT require PostgreSQL, Docker, or network access under any circumstances.
- Integration tests against NASA Earthdata MUST respect rate limits (max 5 requests per minute in test suite).

## Acceptance Criteria

### Slice 1 (Core + JSON metadata)
- SMAP configuration in YAML is loaded and validated.
- Authentication against NASA Earthdata succeeds using environment variables.
- Search for SPL4SMGP.008 returns results for valid bbox and dates.
- `--search-only` mode lists results without downloading.
- HDF5 files are downloaded to `data/raw/smap/YYYY/MM/`.
- File downloads are idempotent (skipped if file exists and local checksum matches `metadata.json`).
- `data/raw/` is correctly ignored via `.gitignore`.
- Each file has a SHA-256 checksum registered in a per-job `metadata.json`.
- Ingestion jobs generate correct states and emit `ready_for_etl = true` upon success.
- Date range is configurable with a default of 7 days.
- New connector designs are supported without modifying core logic.
- NO database (not even SQLite) is used.

### Slice 2 (PostgreSQL)
- Tables `data_sources`, `datasets`, `ingestion_jobs`, `raw_files` are created in plain PostgreSQL.
- PostGIS is NOT used.
- `metadata.json` data is successfully migrated to PostgreSQL without data loss.
- Metadata queries operate against PostgreSQL.
- Docker Compose setup successfully spins up local PostgreSQL.
