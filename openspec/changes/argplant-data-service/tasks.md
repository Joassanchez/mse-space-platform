# Tasks: ARGPLANT Data Service API

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~2200 (across 5 PRs) |
| 800-line budget risk | Low (each PR ≤ 600 lines) |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Foundation ~500) → PR 2 (Agroclimate ~450) → PR 3 (Satellite ~550) → PR 4 (Agronomy+Economy ~450) → PR 5 (Ingestion ~250) |
| Delivery strategy | auto-chain |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: Low

### Branch Topology

```text
main
 └── feature/argplant-data-service          ← tracker (draft PR, no-merge)
      ↑ PR #1 base
      └── feature/argplant-data-service-01-foundation
           ↑ PR #2 base
           └── feature/argplant-data-service-02-agroclimate
                ↑ PR #3 base
                └── feature/argplant-data-service-03-satellite
                     ↑ PR #4 base
                     └── feature/argplant-data-service-04-agronomy-economy
                          ↑ PR #5 base
                          └── feature/argplant-data-service-05-ingestion
```

### Suggested Work Units

| Unit | Goal | PR | Base | Est. Lines |
|------|------|----|------|------------|
| 1 | Project scaffolding + shared infra + Docker + Alembic + test harness | PR 1 | tracker branch | ~500 |
| 2 | Agroclimate module (weather + POWER + rate limiting) | PR 2 | PR 1 branch | ~450 |
| 3 | Satellite module (SMAP + Sentinel + async download) | PR 3 | PR 2 branch | ~550 |
| 4 | Agronomy + Economy modules (catalogs + prices) | PR 4 | PR 3 branch | ~450 |
| 5 | Ingestion pipeline (arq worker + cron + job status) | PR 5 | PR 4 branch | ~250 |

---

## Phase 1: Foundation (PR #1 — ~500 lines)

### Project Scaffolding

- [x] 1.1 Create `pyproject.toml` with dependencies: fastapi, uvicorn, httpx, sqlalchemy[asyncio], asyncpg, alembic, redis, arq, pydantic-settings, pyyaml, tenacity, slowapi, pytest, pytest-asyncio, ruff.
  - **Files**: `pyproject.toml`
  - **Spec**: N/A (infra)
  - **Lines**: ~40
  - **Verify**: `pip install -e .` succeeds

- [x] 1.2 Create `Dockerfile` (multi-stage: python-slim base, copy pyproject.toml, install deps, copy argplant/, CMD uvicorn).
  - **Files**: `Dockerfile`
  - **Spec**: N/A
  - **Lines**: ~25
  - **Verify**: `docker build -t argplant .` succeeds

- [x] 1.3 Create `docker-compose.yml` with services: `db` (postgis/postgis:16-3.4), `redis` (redis:7-alpine), `api` (build ., ports 8000, depends_on db+redis healthy), `worker` (same image, command: arq worker). Include healthchecks and volume mounts.
  - **Files**: `docker-compose.yml`
  - **Spec**: N/A
  - **Lines**: ~35
  - **Verify**: `docker compose config` validates

- [x] 1.4 Create `Makefile` with targets: `up`, `down`, `test`, `lint`, `seed`, `migrate`, `migration`.
  - **Files**: `Makefile`
  - **Spec**: N/A
  - **Lines**: ~15
  - **Verify**: `make --dry-run up` shows correct commands

- [x] 1.5 Create `.env.example` with all config keys from design (DATABASE_URL, REDIS_URL, API keys, coords).
  - **Files**: `.env.example`
  - **Spec**: N/A
  - **Lines**: ~20
  - **Verify**: File present with all keys documented

### Shared Infrastructure

- [x] 1.6 Create `argplant/__init__.py` (empty) and `argplant/shared/__init__.py` (empty).
  - **Files**: `argplant/__init__.py`, `argplant/shared/__init__.py`
  - **Spec**: N/A
  - **Lines**: ~2
  - **Verify**: Package importable

- [x] 1.7 Create `argplant/shared/config.py` — `Settings(BaseSettings)` with all fields from design: DATABASE_URL, REDIS_URL, OPENWEATHER_API_KEY, POWER_TIMEOUT, EARTHDATA creds, CDSE creds, RATE_LIMIT config, SATELLITE_STORAGE_PATH, INGESTION_COORDS, LOG_LEVEL, CORS_ORIGINS. Use `SettingsConfigDict(env_file=".env")`.
  - **Files**: `argplant/shared/config.py`
  - **Spec**: All modules (shared config)
  - **Lines**: ~45
  - **Verify**: `Settings()` loads with defaults; env override works

- [x] 1.8 Create `argplant/shared/database.py` — async SQLAlchemy engine via `create_async_engine`, `async_sessionmaker`, `get_session()` async generator dependency.
  - **Files**: `argplant/shared/database.py`
  - **Spec**: N/A (shared)
  - **Lines**: ~30
  - **Verify**: Engine connects to test DB in pytest

- [x] 1.9 Create `argplant/shared/cache.py` — Redis client wrapper with `get_json()`, `set_json(key, value, ttl)`, `get_stale(key)` (checks extended TTL key), `delete(key)`. Uses `redis.asyncio`.
  - **Files**: `argplant/shared/cache.py`
  - **Spec**: agroclimate-data (cache), economy-prices (cache)
  - **Lines**: ~50
  - **Verify**: Unit test: set/get/stale/delete roundtrip with fakeredis

- [x] 1.10 Create `argplant/shared/storage.py` — `StorageBackend` Protocol class with `save(path, data)`, `exists(path)`, `get_path(path)`. `LocalStorage` implementation using `Path.mkdir(parents=True)`.
  - **Files**: `argplant/shared/storage.py`
  - **Spec**: satellite-data (storage abstraction)
  - **Lines**: ~35
  - **Verify**: Unit test: save + exists + get_path on tempdir

- [x] 1.11 Create `argplant/shared/middleware.py` — IP rate limiter using Redis sliding window (INCR + EXPIRE). Configurable via `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS`. Returns 429 + `Retry-After`. Also: `X-Stale` header injection helper.
  - **Files**: `argplant/shared/middleware.py`
  - **Spec**: agroclimate-data (IP-Based Rate Limiting)
  - **Lines**: ~55
  - **Verify**: Integration test: 61st request returns 429

### Application Entry Point

- [x] 1.12 Create `argplant/main.py` — FastAPI app with CORS middleware, rate limiter middleware, lifespan event that initializes DB engine, Redis pool, and calls seed loaders. Mount placeholder routers (commented until modules exist). Include `/health` endpoint.
  - **Files**: `argplant/main.py`
  - **Spec**: N/A (app bootstrap)
  - **Lines**: ~50
  - **Verify**: `uvicorn argplant.main:app` starts; `/health` returns 200

### Database Migrations

- [x] 1.13 Create Alembic config: `alembic.ini`, `migrations/env.py` (async-compatible), `migrations/versions/001_initial.py` with all tables from design: `locations`, `weather_snapshots`, `satellite_scenes`, `price_series`, `ingestion_jobs` + indexes.
  - **Files**: `alembic.ini`, `migrations/env.py`, `migrations/versions/001_initial.py`, `migrations/script.py.mako`
  - **Spec**: N/A (all modules)
  - **Lines**: ~120
  - **Verify**: `alembic upgrade head` on test DB creates all tables

### Test Harness

- [x] 1.14 Create `tests/conftest.py` — async fixtures: `test_db` (create/drop tables), `test_session`, `test_redis` (fakeredis), `test_client` (httpx.AsyncClient with app), `mock_settings`. Include `pytest.ini` or `pyproject.toml` section for pytest-asyncio mode=auto.
  - **Files**: `tests/__init__.py`, `tests/conftest.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`
  - **Spec**: N/A (test infra)
  - **Lines**: ~60
  - **Verify**: `pytest --collect-only` discovers tests

- [x] 1.15 Create `tests/unit/test_shared.py` — tests for config defaults, cache set/get/stale, storage save/exists, rate limiter logic.
  - **Files**: `tests/unit/test_shared.py`
  - **Spec**: agroclimate-data (Rate Limiting), shared cache/storage
  - **Lines**: ~80
  - **Verify**: `pytest tests/unit/test_shared.py` all pass

- [x] 1.16 Create `tests/integration/test_health.py` — test `/health` endpoint returns 200 via TestClient.
  - **Files**: `tests/integration/test_health.py`
  - **Spec**: N/A
  - **Lines**: ~10
  - **Verify**: `pytest tests/integration/test_health.py` passes

---

## Phase 2: Agroclimate Module (PR #2 — ~450 lines)

### Models

- [x] 2.1 Create `argplant/modules/__init__.py` and `argplant/modules/agroclimate/__init__.py`.
  - **Files**: `argplant/modules/__init__.py`, `argplant/modules/agroclimate/__init__.py`
  - **Spec**: N/A
  - **Lines**: ~2
  - **Verify**: Package importable

- [x] 2.2 Create `argplant/modules/agroclimate/models.py` — SQLAlchemy model `WeatherSnapshot` (location_id, temp, humidity, wind_speed, conditions, source, data JSONB, captured_at). Pydantic schemas: `WeatherResponse`, `PowerResponse`, `PowerParameter`. Location model.
  - **Files**: `argplant/modules/agroclimate/models.py`
  - **Spec**: Weather Forecast Retrieval, Agroclimatic Parameters Retrieval
  - **Lines**: ~65
  - **Verify**: Models importable; schema validation works

### HTTP Clients

- [x] 2.3 Create `argplant/modules/agroclimate/client.py` — `OpenWeatherClient` with `current(lat, lon)` method: httpx GET to `/data/2.5/weather`, API key from settings, 10s timeout, tenacity retry (3x, exponential, 5xx only). `NasaPowerClient` with `daily(lat, lon, start, end, params)`: GET to POWER REST API, 15s timeout, retry. Both return normalized dicts.
  - **Files**: `argplant/modules/agroclimate/client.py`
  - **Spec**: Weather Forecast Retrieval, Agroclimatic Parameters Retrieval
  - **Lines**: ~80
  - **Verify**: Unit test with httpx.MockTransport: correct URL construction, retry on 500

### Repository

- [x] 2.4 Create `argplant/modules/agroclimate/repository.py` — `WeatherSnapshotRepo` with `upsert(session, snapshot)` and `get_latest(session, location_id)`. Uses SQLAlchemy async queries.
  - **Files**: `argplant/modules/agroclimate/repository.py`
  - **Spec**: Weather Forecast Retrieval (persistence)
  - **Lines**: ~40
  - **Verify**: Unit test: upsert + get_latest roundtrip with test DB

### Service

- [x] 2.5 Create `argplant/modules/agroclimate/service.py` — `WeatherService.get(lat, lon)`: check cache → fetch from OpenWeatherClient → normalize → repo.upsert → cache.set → return WeatherResponse. On API fail: check stale cache → return with stale flag or 503. `PowerService.get(lat, lon, start, end, params)`: same pattern with 24h TTL.
  - **Files**: `argplant/modules/agroclimate/service.py`
  - **Spec**: Weather Forecast Retrieval (cache miss + stale), Agroclimatic Parameters Retrieval
  - **Lines**: ~90
  - **Verify**: Unit test: mocked client + fakeredis → cache HIT/MISS/stale paths

### Router

- [x] 2.6 Create `argplant/modules/agroclimate/router.py` — `GET /api/v1/agroclimate/weather` (lat, lon query params) → WeatherResponse + X-Cache header. `GET /api/v1/agroclimate/power` (lat, lon, start_date, end_date, parameters) → PowerResponse. Wire into `main.py` lifespan and router mount.
  - **Files**: `argplant/modules/agroclimate/router.py`, modify `argplant/main.py`
  - **Spec**: Weather Forecast Retrieval (all scenarios), Agroclimatic Parameters Retrieval, IP-Based Rate Limiting
  - **Lines**: ~50
  - **Verify**: Integration test: GET weather returns 200 with correct schema; X-Cache header present

### Tests

- [x] 2.7 Create `tests/unit/test_agroclimate_service.py` — test WeatherService: cache hit path, cache miss + API success, API fail + stale cache, API fail + cold cache → 503. Test PowerService: parameter normalization, date range validation.
  - **Files**: `tests/unit/test_agroclimate_service.py`
  - **Spec**: Weather Forecast Retrieval (all scenarios), Agroclimatic Parameters Retrieval
  - **Lines**: ~80
  - **Verify**: All scenarios pass with mocked clients

- [x] 2.8 Create `tests/integration/test_agroclimate_router.py` — test endpoints via httpx.AsyncClient: fresh forecast (200 + X-Cache: HIT), cache miss (200 + X-Cache: MISS), stale fallback (200 + X-Stale: true), rate limit exceeded (429 + Retry-After), POWER parameters (200 + metric values).
  - **Files**: `tests/integration/test_agroclimate_router.py`
  - **Spec**: Weather Forecast Retrieval (all scenarios), Agroclimatic Parameters Retrieval, IP-Based Rate Limiting
  - **Lines**: ~70
  - **Verify**: All integration scenarios pass

---

## Phase 3: Satellite Module (PR #3 — ~550 lines)

### Models

- [x] 3.1 Create `argplant/modules/satellite/__init__.py` and `argplant/modules/satellite/models.py` — SQLAlchemy `SatelliteScene` (scene_id, platform, bbox JSONB, acquisition_date, cloud_cover, metadata JSONB, file_path). Pydantic: `SmSceneMeta`, `SentinelSceneMeta`, `DownloadResponse`.
  - **Files**: `argplant/modules/satellite/__init__.py`, `argplant/modules/satellite/models.py`
  - **Spec**: SMAP Soil Moisture Metadata Search, Sentinel Catalog Search, Async Sentinel Download
  - **Lines**: ~60
  - **Verify**: Models importable; schema validation

### Clients

- [x] 3.2 Create `argplant/modules/satellite/client.py` — `EarthdataClient`: uses earthaccess lib for token mgmt, `search_sm(bbox, start, end)` returns SMAP granule metadata. `CdseClient`: OAuth2 token refresh, `search_sentinel(bbox, start, end, platform, max_cloud)` via STAC API, `download(scene_id, storage)` streams file to storage.
  - **Files**: `argplant/modules/satellite/client.py`
  - **Spec**: SMAP Soil Moisture Metadata Search, Sentinel Catalog Search, Async Sentinel Download
  - **Lines**: ~100
  - **Verify**: Unit test: mocked responses → correct parsing; token refresh logic

### Repository

- [x] 3.3 Create `argplant/modules/satellite/repository.py` — `SatelliteSceneRepo` with `upsert(session, scene)`, `get_by_scene_id(session, scene_id)`, `search(session, platform, bbox, start, end)`.
  - **Files**: `argplant/modules/satellite/repository.py`
  - **Spec**: SMAP/Sentinel metadata persistence
  - **Lines**: ~45
  - **Verify**: Unit test: upsert + search roundtrip

### Service

- [x] 3.4 Create `argplant/modules/satellite/service.py` — `SmapService.search(bbox, start, end)`: delegate to EarthdataClient → normalize → repo.upsert → return list[SmSceneMeta]. `SentinelService.search(...)`: CdseClient STAC search → normalize → repo.upsert. `SentinelService.enqueue_download(scene_id)`: validate scene exists → create ingestion_job record → enqueue arq job → return job_id.
  - **Files**: `argplant/modules/satellite/service.py`
  - **Spec**: SMAP Soil Moisture Metadata Search, Sentinel Catalog Search, Async Sentinel Download (queue)
  - **Lines**: ~80
  - **Verify**: Unit test: mocked clients → correct normalization; enqueue creates job record

### Tasks

- [x] 3.5 Create `argplant/modules/satellite/tasks.py` — `download_sentinel(ctx, scene_id)` arq job function: lookup scene → CdseClient.download → storage.save → update scene.file_path → update job status to completed. On failure: retry up to 3x (arq max_tries), then status → failed with error in result JSONB.
  - **Files**: `argplant/modules/satellite/tasks.py`
  - **Spec**: Async Sentinel Download (download lifecycle), data-ingestion-pipeline (Async Satellite Download Jobs)
  - **Lines**: ~55
  - **Verify**: Unit test: mocked download → file saved, status updated

### Router

- [x] 3.6 Create `argplant/modules/satellite/router.py` — `GET /api/v1/satellite/smap` (bbox, start_date, end_date) → list[SmSceneMeta]. `GET /api/v1/satellite/sentinel/search` (bbox, start_date, end_date, platform, max_cloud_cover) → list[SentinelSceneMeta]. `POST /api/v1/satellite/sentinel/{id}/download` → 202 {job_id, status: "queued"} or 404. Wire into main.py.
  - **Files**: `argplant/modules/satellite/router.py`, modify `argplant/main.py`
  - **Spec**: SMAP Soil Moisture Metadata Search, Sentinel Catalog Search, Async Sentinel Download
  - **Lines**: ~55
  - **Verify**: Integration test: SMAP search returns 200; Sentinel search with cloud filter; POST download returns 202; unknown scene returns 404

### Tests

- [x] 3.7 Create `tests/unit/test_satellite_service.py` — test SmapService/SentinelService: search normalization, enqueue creates job, download task lifecycle (queued → completed/failed).
  - **Files**: `tests/unit/test_satellite_service.py`
  - **Spec**: All satellite scenarios
  - **Lines**: ~75
  - **Verify**: All unit tests pass

- [x] 3.8 Create `tests/integration/test_satellite_router.py` — test all three endpoints via TestClient with mocked external APIs.
  - **Files**: `tests/integration/test_satellite_router.py`
  - **Spec**: All satellite scenarios
  - **Lines**: ~65
  - **Verify**: All integration scenarios pass

---

## Phase 4: Agronomy + Economy Modules (PR #4 — ~450 lines)

### Agronomy — Seed Data

- [ ] 4.1 Create `data/agronomy/crops.yaml` with soy and corn entries (id, name, scientific_name). Create `data/agronomy/bbch_stages.yaml` with BBCH stages including kc, temp_min, temp_max, temp_opt per stage.
  - **Files**: `data/agronomy/crops.yaml`, `data/agronomy/bbch_stages.yaml`
  - **Spec**: Seed Data at Startup, Crop Listing, Crop Stage Detail
  - **Lines**: ~60
  - **Verify**: YAML parses correctly; BBCH 60 = flowering, BBCH 79 present

### Agronomy — Module

- [ ] 4.2 Create `argplant/modules/agronomy/__init__.py`, `argplant/modules/agronomy/models.py` — Pydantic: `Crop`, `GrowthStage`. No SQLAlchemy models (in-memory only).
  - **Files**: `argplant/modules/agronomy/__init__.py`, `argplant/modules/agronomy/models.py`
  - **Spec**: Crop Listing, Crop Stage Detail
  - **Lines**: ~30
  - **Verify**: Schemas validate correctly

- [ ] 4.3 Create `argplant/modules/agronomy/seed_data.py` — `load_agronomy_seeds()`: reads `data/agronomy/crops.yaml` + `bbch_stages.yaml`, populates module-level dict. Raises on missing/malformed files (fails startup).
  - **Files**: `argplant/modules/agronomy/seed_data.py`
  - **Spec**: Seed Data at Startup
  - **Lines**: ~35
  - **Verify**: Unit test: valid fixtures load; missing file raises

- [ ] 4.4 Create `argplant/modules/agronomy/service.py` — `CropCatalogService.list_crops()`, `.get_stages(crop_id)`: reads from in-memory dict.
  - **Files**: `argplant/modules/agronomy/service.py`
  - **Spec**: Crop Listing, Crop Stage Detail
  - **Lines**: ~25
  - **Verify**: Unit test: list returns soy+corn; get_stages returns BBCH data; unknown crop → None

- [ ] 4.5 Create `argplant/modules/agronomy/router.py` — `GET /api/v1/agronomy/crops` → list[Crop]. `GET /api/v1/agronomy/crops/{id}/stages` → list[GrowthStage] or 404. Wire into main.py lifespan (call load_agronomy_seeds).
  - **Files**: `argplant/modules/agronomy/router.py`, modify `argplant/main.py`
  - **Spec**: Crop Listing, Crop Stage Detail, Seed Data at Startup
  - **Lines**: ~30
  - **Verify**: Integration test: list crops returns 200; soy stages include BBCH 60; unknown crop → 404

### Economy — Seed Data

- [ ] 4.6 Create `data/economy/products.yaml` (soy=18, corn, wheat, sunflower with IDs). Create `data/economy/ports.yaml` (Rosario=23 + others).
  - **Files**: `data/economy/products.yaml`, `data/economy/ports.yaml`
  - **Spec**: Product and Port ID Mapping
  - **Lines**: ~25
  - **Verify**: YAML parses; soy→18, Rosario→23 confirmed

### Economy — Module

- [ ] 4.7 Create `argplant/modules/economy/__init__.py`, `argplant/modules/economy/models.py` — SQLAlchemy `PriceSeries` (producto_id, puerto_id, fecha, minimo, maximo, promedio, modal). Pydantic: `PriceSeriesResponse`, `PricePoint`.
  - **Files**: `argplant/modules/economy/__init__.py`, `argplant/modules/economy/models.py`
  - **Spec**: Daily Price Series Retrieval
  - **Lines**: ~40
  - **Verify**: Models importable

- [ ] 4.8 Create `argplant/modules/economy/seed_data.py` — `load_economy_seeds()`: reads product/port YAML, populates ID-to-name mapping dict.
  - **Files**: `argplant/modules/economy/seed_data.py`
  - **Spec**: Product and Port ID Mapping
  - **Lines**: ~25
  - **Verify**: Unit test: mappings loaded correctly

- [ ] 4.9 Create `argplant/modules/economy/client.py` — `MagypClient.fetch(producto, puerto, desde, hasta)`: httpx POST to Monitor de Granos endpoint, 10s timeout, tenacity retry. Returns raw dict.
  - **Files**: `argplant/modules/economy/client.py`
  - **Spec**: Daily Price Series Retrieval
  - **Lines**: ~40
  - **Verify**: Unit test: mocked POST → correct parsing

- [ ] 4.10 Create `argplant/modules/economy/repository.py` — `PriceSeriesRepo.upsert(session, series)`, `get_series(session, producto_id, puerto_id, desde, hasta)`.
  - **Files**: `argplant/modules/economy/repository.py`
  - **Spec**: Daily Price Series Retrieval (persistence)
  - **Lines**: ~35
  - **Verify**: Unit test: upsert + query roundtrip

- [ ] 4.11 Create `argplant/modules/economy/service.py` — `PriceService.get(producto, puerto, desde, hasta)`: validate product/port IDs → check cache → MagypClient.fetch → normalize → repo.upsert → cache.set. On fail: stale cache + X-Stale or 503.
  - **Files**: `argplant/modules/economy/service.py`
  - **Spec**: Daily Price Series Retrieval (all scenarios)
  - **Lines**: ~55
  - **Verify**: Unit test: cache hit/miss/stale paths; unknown product → 400

- [ ] 4.12 Create `argplant/modules/economy/router.py` — `GET /api/v1/economy/prices` (producto, puerto, desde, hasta) → PriceSeriesResponse or 400 for unknown IDs. Wire into main.py.
  - **Files**: `argplant/modules/economy/router.py`, modify `argplant/main.py`
  - **Spec**: Daily Price Series Retrieval, Product and Port ID Mapping
  - **Lines**: ~30
  - **Verify**: Integration test: valid query returns 200; unknown product → 400; stale fallback

### Tests

- [ ] 4.13 Create `tests/unit/test_agronomy.py` — test seed loading, CropCatalogService list/stages, unknown crop handling.
  - **Files**: `tests/unit/test_agronomy.py`
  - **Spec**: Crop Listing, Crop Stage Detail, Seed Data at Startup
  - **Lines**: ~35
  - **Verify**: All pass

- [ ] 4.14 Create `tests/unit/test_economy_service.py` — test PriceService: cache paths, ID validation, stale fallback.
  - **Files**: `tests/unit/test_economy_service.py`
  - **Spec**: Daily Price Series Retrieval, Product and Port ID Mapping
  - **Lines**: ~40
  - **Verify**: All pass

- [ ] 4.15 Create `tests/integration/test_agronomy_economy_router.py` — test all agronomy + economy endpoints via TestClient.
  - **Files**: `tests/integration/test_agronomy_economy_router.py`
  - **Spec**: All agronomy/economy scenarios
  - **Lines**: ~50
  - **Verify**: All integration scenarios pass

---

## Phase 5: Ingestion Pipeline (PR #5 — ~250 lines)

### Worker

- [ ] 5.1 Create `argplant/modules/ingestion/__init__.py` and `argplant/modules/ingestion/models.py` — SQLAlchemy `IngestionJob` (job_type, status, params JSONB, result JSONB, timestamps). Pydantic: `JobStatus` response schema.
  - **Files**: `argplant/modules/ingestion/__init__.py`, `argplant/modules/ingestion/models.py`
  - **Spec**: Job Status Endpoint, Async Satellite Download Jobs
  - **Lines**: ~35
  - **Verify**: Models importable

- [ ] 5.2 Create `argplant/modules/ingestion/worker.py` — `WorkerSettings` class for arq: Redis connection, task functions list (download_sentinel from satellite.tasks, ingest_weather, ingest_prices, sync_satellite_catalog). Startup/shutdown hooks.
  - **Files**: `argplant/modules/ingestion/worker.py`
  - **Spec**: Scheduled Daily Ingestion, Async Satellite Download Jobs
  - **Lines**: ~35
  - **Verify**: Worker starts with `arq argplant.modules.ingestion.worker.WorkerSettings`

### Cron

- [ ] 5.3 Create `argplant/modules/ingestion/cron.py` — arq cron definitions: `@cron(hour=6)` daily weather pull for PERGAMINO_COORDS, `@cron(hour=7)` price refresh, `@cron(hour=3)` satellite catalog sync. Each calls the respective service and warms cache. On failure: log error, preserve stale cache.
  - **Files**: `argplant/modules/ingestion/cron.py`
  - **Spec**: Scheduled Daily Ingestion, Graceful Degradation on External API Failure
  - **Lines**: ~50
  - **Verify**: Unit test: cron functions call correct services; failure preserves stale cache

### Router

- [ ] 5.4 Create `argplant/modules/ingestion/router.py` — `GET /api/v1/jobs/{job_id}` → JobStatus (200) or 404. Queries ingestion_jobs table. Wire into main.py.
  - **Files**: `argplant/modules/ingestion/router.py`, modify `argplant/main.py`
  - **Spec**: Job Status Endpoint
  - **Lines**: ~25
  - **Verify**: Integration test: completed job returns 200 with file_path; unknown job → 404

### Tests

- [ ] 5.5 Create `tests/unit/test_ingestion.py` — test cron functions with mocked services, worker settings validation, job status transitions.
  - **Files**: `tests/unit/test_ingestion.py`
  - **Spec**: Scheduled Daily Ingestion, Async Satellite Download Jobs, Graceful Degradation
  - **Lines**: ~50
  - **Verify**: All pass

- [ ] 5.6 Create `tests/integration/test_ingestion_router.py` — test job status endpoint, end-to-end: queue download → check status → verify completed.
  - **Files**: `tests/integration/test_ingestion_router.py`
  - **Spec**: Job Status Endpoint, Async Satellite Download Jobs
  - **Lines**: ~40
  - **Verify**: All integration scenarios pass

- [ ] 5.7 Create `tests/integration/test_e2e.py` — end-to-end smoke test: start app, hit all module endpoints, verify response schemas. Verify `/docs` serves OpenAPI.
  - **Files**: `tests/integration/test_e2e.py`
  - **Spec**: All success criteria
  - **Lines**: ~30
  - **Verify**: Full smoke test passes; `/docs` accessible
