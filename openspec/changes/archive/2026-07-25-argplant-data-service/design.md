# Design: ARGPLANT Data Service API

## Architecture Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Monorepo layout | `argplant.modules.{name}` packages | Greenfield, zero deps. Enables later extraction to services. |
| Async HTTP client | `httpx.AsyncClient` with connection pooling | Concurrent external API calls for agroclimate/satellite. |
| Task queue | `arq` (Redis) over Celery | Lightweight, async-native, no broker overhead. One dep for cache+queue. |
| Satellite storage abstraction | `StorageBackend` protocol class | Local FS now, MinIO/S3 swap later without code changes. |
| Rate limiting | `slowapi` or Redis sliding-window middleware | IP-based, transparent; no auth stack. |
| Seed data loading | Module-level `load_seeds()` called at FastAPI startup event | Fails fast on malformed fixtures; keeps catalog modules stateless. |
| Degradation pattern | `X-Stale: true` header + stale cache return on external API failure | Preserves UX; signals to model layer that data may be outdated. |

## Package Structure

```
argplant/
├── main.py                          # FastAPI app, router mounts, startup events
├── shared/
│   ├── config.py                    # Pydantic-Settings (Settings model)
│   ├── database.py                  # SQLAlchemy async engine + session
│   ├── cache.py                     # Redis client (aioredis) + cache helpers
│   ├── storage.py                   # StorageBackend protocol + LocalStorage impl
│   └── middleware.py                # IP rate limiter, X-Stale header injector
├── modules/
│   ├── agroclimate/
│   │   ├── router.py                # GET /weather, GET /power
│   │   ├── service.py               # WeatherService, PowerService
│   │   ├── repository.py            # WeatherSnapshotRepo (CRUD)
│   │   ├── client.py                # OpenWeatherClient, NasaPowerClient
│   │   └── models.py                # SQLAlchemy + Pydantic models
│   ├── satellite/
│   │   ├── router.py                # GET /smap, GET /sentinel/search, POST /{id}/download
│   │   ├── service.py               # SmapService, SentinelService
│   │   ├── repository.py            # SatelliteSceneRepo
│   │   ├── client.py                # EarthdataClient, CdseClient
│   │   ├── models.py
│   │   └── tasks.py                 # arq download job function
│   ├── agronomy/
│   │   ├── router.py                # GET /crops, GET /crops/{id}/stages
│   │   ├── service.py               # CropCatalogService
│   │   ├── models.py
│   │   └── seed_data.py             # Startup loader from YAML fixtures
│   ├── economy/
│   │   ├── router.py                # GET /prices
│   │   ├── service.py               # PriceService
│   │   ├── repository.py            # PriceSeriesRepo
│   │   ├── client.py                # MagypClient
│   │   ├── models.py
│   │   └── seed_data.py             # Product/port ID mappings
│   └── ingestion/
│       ├── router.py                # GET /jobs/{job_id}
│       ├── worker.py                # arq Worker entry point
│       ├── cron.py                  # arq cron schedule (daily pulls)
│       └── models.py                # IngestionJob model
├── data/
│   ├── agronomy/                    # YAML fixtures (crops, bbch_stages)
│   ├── economy/                     # YAML fixtures (products, ports)
│   └── satellite/                   # Raw downloads: {platform}/{scene_id}/
├── migrations/                      # Alembic
├── tests/
│   ├── unit/                        # per-module service/repo tests
│   ├── integration/                 # FastAPI TestClient + real DB/Redis
│   └── conftest.py                  # async fixtures, test DB, mock clients
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── Makefile
└── README.md
```

## Module Interfaces

### agroclimate-data

| Layer | Signature / Path | Details |
|-------|-----------------|---------|
| Router | `GET /api/v1/agroclimate/weather?lat=&lon=` | → `WeatherResponse` (temp, humidity, wind_speed, conditions, timestamp). Cache key: `weather:{lat}:{lon}`. |
| Router | `GET /api/v1/agroclimate/power?lat=&lon=&start_date=&end_date=&parameters=` | → `PowerResponse` (daily arrays per param). Cache key includes all params. |
| Service | `WeatherService.get(lat, lon) -> WeatherResponse` | Check cache → fetch → normalize → store → return. |
| Service | `PowerService.get(lat, lon, start, end, params) -> PowerResponse` | Same pattern; units normalized to metric. |
| Repository | `WeatherSnapshotRepo.upsert(snapshot)` | `weather_snapshots` table. |
| Client | `OpenWeatherClient.current(lat, lon)` | httpx GET to `/data/2.5/weather`. API key from config. Timeout 10s. |
| Client | `NasaPowerClient.daily(lat, lon, start, end, params)` | httpx GET to POWER REST API. No auth for basic. Timeout 15s. |

### satellite-data

| Layer | Signature / Path | Details |
|-------|-----------------|---------|
| Router | `GET /api/v1/satellite/smap?bbox=&start_date=&end_date=` | → `list[SmSceneMeta]`. |
| Router | `GET /api/v1/satellite/sentinel/search?bbox=&start_date=&end_date=&platform=&max_cloud_cover=` | → `list[SentinelSceneMeta]`. |
| Router | `POST /api/v1/satellite/sentinel/{id}/download` | → 202 `{job_id, status: "queued"}`. Enqueues arq job. |
| Service | `SmService.search(bbox, start, end) -> list[SmSceneMeta]` | Delegates to earthaccess. |
| Service | `SentinelService.search(...) -> list[SentinelSceneMeta]` | CDSE STAC API via httpx. |
| Service | `SentinelService.enqueue_download(scene_id)` | Validates scene, creates job, enqueues to arq. |
| Repository | `SatelliteSceneRepo.upsert(meta)` | `satellite_scenes` table. |
| Client | `EarthdataClient` | Token mgmt via earthaccess lib. Auth: EARTHDATA_USERNAME/PASSWORD. |
| Client | `CdseClient` | Token refresh via OAuth2. Auth: CDSE_USERNAME/PASSWORD. |
| Tasks | `download_sentinel(ctx, scene_id)` | arq job: download → store → update status. Dead letter queue on 3x failure. |

### agronomy-catalog

| Layer | Signature / Path | Details |
|-------|-----------------|---------|
| Router | `GET /api/v1/agronomy/crops` | → `list[Crop]`. In-memory from startup seed. |
| Router | `GET /api/v1/agronomy/crops/{id}/stages` | → `list[GrowthStage]`. Returns BBCH, Kc, thresholds. |
| Service | `CropCatalogService.list_crops()`, `.get_stages(crop_id)` | Reads from in-memory dict loaded at startup. |
| Seed | `load_agronomy_seeds()` | Reads `data/agronomy/crops.yaml`, `data/agronomy/bbch_stages.yaml`. Fails startup on parse error. |

### economy-prices

| Layer | Signature / Path | Details |
|-------|-----------------|---------|
| Router | `GET /api/v1/economy/prices?producto=&puerto=&desde=&hasta=` | → `PriceSeriesResponse`. Cache key: `prices:{prod}:{port}:{desde}:{hasta}`. TTL 1h. |
| Service | `PriceService.get(producto, puerto, desde, hasta)` | Check cache → MAGyP fetch → normalize → store. Maps numeric IDs to names via seed data. Validates product/port. |
| Repository | `PriceSeriesRepo.upsert(series)` | `price_series` table. |
| Client | `MagypClient.fetch(producto, puerto, desde, hasta)` | httpx POST to Monitor de Granos endpoint. No auth. Timeout 10s. |
| Seed | `load_economy_seeds()` | Reads `data/economy/products.yaml`, `data/economy/ports.yaml`. |

### data-ingestion-pipeline

| Layer | Signature / Path | Details |
|-------|-----------------|---------|
| Router | `GET /api/v1/jobs/{job_id}` | → `JobStatus`. Status + result path / error. |
| Worker | `arq.Worker` in `worker.py` | Connects to Redis. Registers task functions from modules. |
| Cron | `arq.cron` decorators | `@cron(hour=6)`: daily weather pull; `@cron(hour=7)`: price refresh; `@cron(hour=3)`: satellite catalog sync. |

## Data Models

### PostgreSQL Tables

```sql
-- Shared
CREATE TABLE locations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    lat         DOUBLE PRECISION NOT NULL,
    lon         DOUBLE PRECISION NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- agroclimate
CREATE TABLE weather_snapshots (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID REFERENCES locations(id),
    temp        DOUBLE PRECISION,
    humidity    INTEGER,
    wind_speed  DOUBLE PRECISION,
    conditions  TEXT,
    source      TEXT NOT NULL DEFAULT 'openweather',  -- openweather | power
    data        JSONB NOT NULL,                       -- full raw response
    captured_at TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_weather_loc_time ON weather_snapshots(location_id, captured_at);

-- satellite
CREATE TABLE satellite_scenes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scene_id        TEXT NOT NULL UNIQUE,
    platform        TEXT NOT NULL,                     -- sentinel-1 | sentinel-2 | smap
    bbox            JSONB NOT NULL,                    -- [min_lon, min_lat, max_lon, max_lat]
    acquisition_date TIMESTAMPTZ NOT NULL,
    cloud_cover     DOUBLE PRECISION,                  -- NULL for SAR/SMAP
    metadata        JSONB NOT NULL,                    -- full STAC/CMR metadata
    file_path       TEXT,                              -- local path after download
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_sat_scenes_platform ON satellite_scenes(platform, acquisition_date);

-- agronomy (in-memory + optional PG for persisting edits)
-- Loaded from YAML at startup; DB tables optional for runtime CRUD.

-- economy
CREATE TABLE price_series (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    producto_id INTEGER NOT NULL,
    puerto_id   INTEGER NOT NULL,
    fecha       DATE NOT NULL,
    minimo      DOUBLE PRECISION,
    maximo      DOUBLE PRECISION,
    promedio    DOUBLE PRECISION,
    modal       DOUBLE PRECISION,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(producto_id, puerto_id, fecha)
);

-- ingestion
CREATE TABLE ingestion_jobs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type    TEXT NOT NULL,                          -- download | ingest | cache_warm
    status      TEXT NOT NULL DEFAULT 'queued',         -- queued | running | completed | failed
    params      JSONB NOT NULL,
    result      JSONB,                                 -- {file_path, error, ...}
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_jobs_status ON ingestion_jobs(status);
```

### Redis Keys & TTL

| Key Pattern | TTL | Content |
|-------------|-----|---------|
| `weather:{lat}:{lon}` | 1h | JSON `WeatherResponse` (current + 5-day forecast) |
| `power:{lat}:{lon}:{start}:{end}:{params_hash}` | 24h | JSON `PowerResponse` |
| `prices:{prod}:{port}:{desde}:{hasta}` | 1h | JSON `PriceSeriesResponse` |
| `rate:{ip}:{window}` | sliding | IP request counter (for rate limiter) |
| `arq:job:{job_id}` | 24h | arq job state (managed by arq) |

### File System Layout

```
data/satellite/
├── sentinel-1/{scene_id}/
│   ├── manifest.safe
│   └── measurement/...
├── sentinel-2/{scene_id}/
│   ├── B02.jp2, B03.jp2, B04.jp2, B08.jp2 ...
│   └── MTD_MSIL2A.xml
└── smap/{granule_ur}/
    └── SMAP_L3_SM_P_*.h5
```

## Data Flow

**Sync flow** (weather/power/prices):
```
Client → Router → Service → [Cache hit? → return JSON]
   ↓ (miss)
   httpx Client → External API → Service.normalize() → Repository.upsert() → Cache.set() → Response
   ↓ (API fail + stale cache)
   Cache.get(stale=True) → Response + X-Stale: true
```

**Async flow** (satellite download):
```
Client → POST /download → Router → Service.enqueue_download(scene_id)
   → arq.enqueue_job('download_sentinel', scene_id)
   → Response 202 {job_id, status: "queued"}

arq Worker picks job:
   downloading → CdseClient.download(scene_id, storage) → save to data/satellite/
   → DB update (file_path) → status: completed
   (on failure 3x → DeadLetter → status: failed)

Client: GET /jobs/{job_id} → status + result
```

**Scheduled flow** (cron):
```
arq Cron @ 3/6/7 UTC → arq.enqueue_job('ingest_daily', module)
   → Service.get_for_coords(PERGAMINO_COORDS)
   → External API → normalize → Repository → Cache warm
   On failure: log error, preserve stale cache
```

## Error Handling & Resilience

| Mechanism | Implementation |
|-----------|---------------|
| Retry | `tenacity` on httpx clients: 3 retries, exponential backoff (1s → 2s → 4s), only on 5xx/network errors. |
| Stale cache | Service layer checks for stale cache (within 24h) on API failure; returns with `X-Stale: true`. Cold cache + failure = 503. |
| Timeouts | OpenWeather: 10s, NASA POWER: 15s, MAGyP: 10s, CDSE: 30s. Configured per client. |
| arq Dead Letter | `max_tries=3` on download jobs. After 3 failures, status → `failed`, error stored in `result` JSONB. |
| Rate limiter | IP-based sliding window via Redis `INCR` + `EXPIRE`. Default: 60 req/min per IP. Returns 429 + `Retry-After`. |

## Configuration Schema (`shared/config.py`)

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://argplant:argplant@localhost:5432/argplant"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # OpenWeather
    OPENWEATHER_API_KEY: str = ""
    OPENWEATHER_TIMEOUT: int = 10

    # NASA POWER
    POWER_TIMEOUT: int = 15

    # Earthdata (SMAP)
    EARTHDATA_USERNAME: str = ""
    EARTHDATA_PASSWORD: str = ""

    # CDSE (Sentinel)
    CDSE_USERNAME: str = ""
    CDSE_PASSWORD: str = ""

    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Storage
    SATELLITE_STORAGE_PATH: Path = Path("data/satellite")

    # Ingestion
    INGESTION_COORDS_LAT: float = -33.89
    INGESTION_COORDS_LON: float = -60.57
    INGESTION_BBOX: str = "-61,-34,-60,-33"

    # Misc
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["*"]
```

## Development Environment

### Docker Compose

```yaml
services:
  db:
    image: postgis/postgis:16-3.4
    environment: {POSTGRES_USER: argplant, POSTGRES_PASSWORD: argplant, POSTGRES_DB: argplant}
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck: {test: pg_isready -U argplant, interval: 5s}

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck: {test: redis-cli ping, interval: 5s}

  api: &api
    build: .
    ports: ["8000:8000"]
    env_file: .env
    depends_on: {db: {condition: service_healthy}, redis: {condition: service_healthy}}
    volumes: ["./data:/app/data"]

  worker:
    <<: *api
    ports: []
    command: arq argplant.modules.ingestion.worker.WorkerSettings

volumes:
  pgdata:
```

### Makefile

```makefile
up:        docker compose up -d
down:      docker compose down
test:      docker compose run --rm api pytest tests/ -v
lint:      docker compose run --rm api ruff check .
seed:      docker compose exec api python -c "from argplant.modules.agronomy.seed_data import load_agronomy_seeds; from argplant.modules.economy.seed_data import load_economy_seeds; load_agronomy_seeds(); load_economy_seeds()"
migrate:   docker compose run --rm api alembic upgrade head
migration: docker compose run --rm api alembic revision --autogenerate -m "$(name)"
```

## Testing Strategy

| Layer | What | Tool |
|-------|------|------|
| Unit: Service | Mocked clients, real repos with test DB | `pytest` + `pytest-asyncio` |
| Unit: Repository | Test DB (PostgreSQL in Docker) | `pytest` + SQLAlchemy async |
| Integration: Router | `httpx.AsyncClient(app, ...)` + test DB/Redis | `pytest` + `httpx` |
| Integration: arq jobs | Test arq worker with real Redis | `pytest` + `arq.worker` |

## Migration / Rollout

No migration required (greenfield). Alembic manages schema from day 1. Feature branch `feature/argplant-data-service` until MVP ready.

## Open Questions

- [ ] Confirm MAGyP product IDs for corn, wheat, sunflower (soy=18 confirmed; port=23 for Rosario confirmed)
- [ ] CDSE token refresh strategy: OAuth2 client credentials flow vs. manual token rotation via config
- [ ] SMAP granules: download full HDF5 or metadata-only for MVP?
