# Design: Backend API Layer

## Technical Approach

The Backend API Layer is a **read-only, async FastAPI service** that sits between the AI Core's PostgreSQL+PostGIS database and the Frontend dashboard. It does NOT import, depend on, or execute any AI Core logic — it only consumes existing DB tables through SQLAlchemy 2.0 async models.

The architecture follows a **layered hexagonal-like pattern**:

```
Request → FastAPI Router → Service Layer → ORM Models → PostgreSQL/PostGIS
                                                    ↓
Response ← Pydantic Schema ← Service Layer ← (GeoAlchemy2 + shapely for geo)
```

Key design constraint: the Backend is an **independent Docker service** sharing only the PostgreSQL and Redis infrastructure with AI Core. No module imports cross the boundary.

## Architecture Decisions

| Decision | Option A (chosen) | Option B (rejected) | Rationale |
|----------|-------------------|---------------------|-----------|
| DB access | SQLAlchemy 2.0 async + asyncpg | Raw asyncpg or psycopg2 async | SQLAlchemy provides ORM mapping for read-only models, easier testing, and GeoAlchemy2 integration for PostGIS |
| Auth | FastAPI dependency (`Depends()`) | Global middleware | Dependencies are overridable in tests via `app.dependency_overrides`; middleware is not. Enables clean migration to JWT later |
| Cache | Redis with TTL per endpoint pattern `{endpoint}:{region_id}:{date}` | In-memory cache or no cache | Redis survives restarts, supports pub/sub for invalidation, and scales to multiple replicas |
| Real-time jobs | WebSocket per `job_id` | Global WS channel or polling | Per-job isolation prevents event leakage; clients only receive events for their job |
| Real-time alerts | SSE via PostgreSQL LISTEN/NOTIFY | WebSocket for alerts | SSE is simpler for one-way broadcast; LISTEN/NOTIFY avoids polling and works with existing AI Core inserts |
| Config | pydantic-settings with env vars | YAML config files | Env vars work natively with Docker Compose; pydantic-settings provides validation and type safety |
| ORM models | Read-only mapped classes (no Alembic) | SQLAlchemy reflection at runtime | Reflection adds startup latency; explicit mapped classes are faster and serve as documentation of expected schema |
| GeoJSON output | GeoAlchemy2 + shapely conversion in service layer | Raw PostGIS `ST_AsGeoJSON()` in queries | shapely provides Python-side control over FeatureCollection structure and metadata injection |
| DB writes | Read-only (SELECT only) | Full CRUD | Backend never modifies AI Core tables; only exception: soft `acknowledge` flag on alerts (in-memory or separate tracking table if needed) |

## Data Flow

### Standard Request

```
Client ──→ [X-API-Key] ──→ FastAPI Router ──→ Cache Check (Redis)
                                                    │
                                              HIT: return cached
                                                    │
                                              MISS: Service → ORM → PostgreSQL
                                                              │
                                                        Pydantic Schema
                                                              │
                                                        Cache (Redis)
                                                              │
                                                        Response
```

### WebSocket (Job Progress)

```
Client ──→ POST /jobs/trigger/ ──→ returns job_id + ws_channel
                │
Client ──→ WS /ws/jobs/{job_id} ──→ WS Manager registers connection
                │
AI Core ──→ updates job in DB ──→ (optional NOTIFY) ──→ WS Manager emits event
                │
Client ←── { event: "job.progress", area, pct_complete }
```

### SSE (Alert Stream)

```
Client ──→ GET /alerts/stream/ (Accept: text/event-stream)
                │
Backend ──→ asyncpg connection: LISTEN new_alerts
                │
AI Core ──→ INSERT alert ──→ NOTIFY new_alerts, payload
                │
Backend ──→ receives NOTIFY ──→ SSE emit: event: new_alert
                │
Client ←── data: { alert_id, severity, region_id, event_type }
```

### Cache Flow

```
Request: GET /api/v1/geo/soil-moisture/?region_id=cordoba_pilot&date=2024-01-15
                │
Cache Key: "geo:soil-moisture:cordoba_pilot:2024-01-15"
                │
TTL: 600s (10 min for geo endpoints)
                │
Invalidation: pattern "geo:soil-moisture:cordoba_pilot:*" on new ETL cycle
```

## File Changes

### New Files

| File | Description |
|------|-------------|
| `backend/__init__.py` | Package marker |
| `backend/main.py` | FastAPI app, lifespan (DB/Redis connect/disconnect), middleware (CORS, logging) |
| `backend/config.py` | `Settings` class via pydantic-settings: DATABASE_URL, REDIS_URL, API_KEY, ALLOWED_ORIGINS |
| `backend/dependencies.py` | `get_db_session()`, `verify_api_key()`, shared dependency providers |
| `backend/api/__init__.py` | Package marker |
| `backend/api/v1/__init__.py` | Package marker |
| `backend/api/v1/router.py` | Aggregates all v1 routers under `/api/v1` prefix |
| `backend/api/v1/analysis.py` | GET /analysis/, /analysis/{id}, /analysis/latest/, /analysis/summary/ |
| `backend/api/v1/alerts.py` | GET /alerts/, /alerts/{id}, /alerts/active/count/, PATCH /alerts/{id}/acknowledge/, GET /alerts/stream/ (SSE) |
| `backend/api/v1/geo.py` | GET /geo/regions/, /geo/soil-moisture/, /geo/risk-zones/, /geo/alerts/, /geo/flood-extent/ |
| `backend/api/v1/jobs.py` | GET /jobs/, /jobs/{id}, /jobs/{id}/logs/, POST /jobs/trigger/, WS /ws/jobs/{job_id} |
| `backend/api/v1/regions.py` | GET /regions/, /regions/{region_id} |
| `backend/schemas/__init__.py` | Package marker |
| `backend/schemas/analysis.py` | Pydantic models: AnalysisList, AnalysisDetail, AnalysisLatest, AnalysisSummary |
| `backend/schemas/alerts.py` | Pydantic models: AlertList, AlertDetail, AlertCount, AlertSSEEvent |
| `backend/schemas/geo.py` | Pydantic models: GeoFeatureCollection, GeoMetadata, GeoFeature (generic) |
| `backend/schemas/jobs.py` | Pydantic models: JobList, JobDetail, JobTriggerRequest, JobTriggerResponse, JobLog |
| `backend/schemas/regions.py` | Pydantic models: RegionList, RegionDetail |
| `backend/services/__init__.py` | Package marker |
| `backend/services/analysis_service.py` | Queries agent_executions, builds analysis responses |
| `backend/services/alert_service.py` | Queries alerts table, handles SSE via asyncpg LISTEN |
| `backend/services/geo_service.py` | Queries PostGIS via GeoAlchemy2, converts to GeoJSON FeatureCollection |
| `backend/services/job_service.py` | Queries/manages ingestion_jobs, triggers on-demand jobs |
| `backend/services/region_service.py` | Queries regions table |
| `backend/db/__init__.py` | Package marker |
| `backend/db/session.py` | `create_async_engine()`, `async_sessionmaker()`, `get_session()` |
| `backend/db/models.py` | Read-only SQLAlchemy models: AgentExecution, Alert, IngestionJob, Region, GeoLayer |
| `backend/core/__init__.py` | Package marker |
| `backend/core/auth.py` | `verify_api_key()` dependency function |
| `backend/core/cache.py` | `CacheManager` wrapper: get, set, invalidate, pattern delete |
| `backend/core/ws_manager.py` | `ConnectionManager`: register, disconnect, broadcast to job_id |
| `backend/tests/__init__.py` | Package marker |
| `backend/tests/conftest.py` | Async fixtures: test DB session, mock Redis, test client, API key override |
| `backend/tests/test_analysis.py` | Analysis endpoint tests |
| `backend/tests/test_alerts.py` | Alerts endpoint + SSE tests |
| `backend/tests/test_geo.py` | Geo endpoint + GeoJSON validity tests |
| `backend/tests/test_jobs.py` | Jobs endpoint + WebSocket tests |
| `backend/tests/test_regions.py` | Regions endpoint tests |
| `backend/tests/test_auth.py` | Auth dependency tests (401 without key, 200 with key) |
| `backend/Dockerfile` | Lightweight FastAPI image: python:3.11-slim, no GDAL needed (backend doesn't process geo) |
| `backend/requirements.txt` | Backend-specific deps (fastapi, uvicorn, asyncpg, redis, GeoAlchemy2, shapely, httpx, pytest-asyncio) |

### Modified Files

| File | Change |
|------|--------|
| `docker-compose.yml` | Add `backend` service (port 8000) and `redis` service (port 6379); both on `geoai_network` |
| `requirements.txt` | Append: fastapi>=0.110, uvicorn[standard]>=0.27, asyncpg>=0.29, redis[hiredis]>=5.0, GeoAlchemy2>=0.14, shapely>=2.0, httpx>=0.25, pytest-asyncio>=0.23 |
| `.env.example` | Add: DATABASE_URL, REDIS_URL, API_KEY, ALLOWED_ORIGINS, BACKEND_API_KEY |

## Interfaces / Contracts

### Authentication
- All endpoints require `X-API-Key` header matching `API_KEY` env var
- Exempt: `GET /health`, `GET /ready`
- Implemented as `Depends(verify_api_key)` on the v1 router, not per-endpoint

### Response Envelope
```python
# Standard list response
class PaginatedResponse(BaseModel):
    items: list[T]
    total: int
    page: int
    limit: int

# Health
class HealthResponse(BaseModel):
    status: Literal["ok"]
    db: Literal["connected"]
    redis: Literal["connected"]

# Readiness
class ReadyResponse(BaseModel):
    status: Literal["ready", "unavailable"]
    db: Literal["connected", "disconnected"]
    redis: Literal["connected", "disconnected"]
```

### GeoJSON Contract
All `/geo/` endpoints return valid `FeatureCollection`:
```json
{
  "type": "FeatureCollection",
  "metadata": { "date": "...", "source": "...", "confidence": 0.0 },
  "features": [
    { "type": "Feature", "geometry": {...}, "properties": {...} }
  ]
}
```

### WebSocket Protocol
```json
{ "event": "job.started", "job_id": "...", "started_at": "...", "areas": [...] }
{ "event": "job.progress", "job_id": "...", "area": "...", "pct_complete": 50 }
{ "event": "job.completed", "job_id": "...", "finished_at": "...", "result_url": "..." }
{ "event": "job.failed", "job_id": "...", "error_message": "...", "failed_at": "..." }
```

### SSE Protocol
```
event: new_alert
data: {"alert_id": "...", "severity": "critical", "region_id": "...", "event_type": "..."}
```

### Cache Key Pattern
`{endpoint_short}:{region_id}:{date_param}` — e.g., `geo:soil-moisture:cordoba_pilot:2024-01-15`

### Cache TTL Defaults
| Endpoint Pattern | TTL |
|-----------------|-----|
| `/analysis/` | 300s (5 min) |
| `/geo/` | 600s (10 min) |
| `/alerts/active/count` | 60s (1 min) |
| `/regions/` | 3600s (60 min) |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Service layer logic with mocked `AsyncSession` | `pytest-asyncio`, `unittest.mock.AsyncMock` for session.execute() |
| Unit | Auth dependency rejects/accepts API key | Override dependency in test app |
| Unit | Cache get/set/invalidate with mocked Redis | `fakeredis` or mock `redis.asyncio.Redis` |
| Unit | WS Manager register/disconnect/broadcast | Instantiate `ConnectionManager` directly |
| Integration | Full endpoint responses via `httpx.AsyncClient` | Test DB with real PostgreSQL (testcontainers) or SQLite fallback |
| Integration | GeoJSON validity of /geo/ responses | Parse response, validate `type == "FeatureCollection"`, check geometry structure |
| Integration | Cache hit/miss headers | First request = miss, second = hit with `X-Cache: HIT` header |
| Integration | WebSocket event emission | Connect via `httpx.AsyncClient` WS, trigger job, verify events |
| Integration | SSE event emission | Connect to SSE stream, simulate NOTIFY, verify event received |

**Test infrastructure**: `pytest-asyncio` mode `auto`, `httpx.AsyncClient` with `base_url`, dependency overrides for auth. Real PostgreSQL via `testcontainers-python` preferred; SQLite fallback for unit-only tests (no PostGIS support).

## Migration / Rollout

**No database migration required.** The Backend reads existing AI Core tables. Two optional PostgreSQL views (`v_latest_analysis_by_region`, `v_active_alerts_geo`) may be created at startup if they don't exist, but these are read-only and non-destructive.

**Phased rollout** (per PRD Section 14):
1. Etapa 1: FastAPI base + /health + /ready
2. Etapa 2: /regions/ + /analysis/latest/
3. Etapa 3: /geo/ endpoints
4. Etapa 4: /alerts/ + Redis cache
5. Etapa 5: /jobs/trigger/ + WebSocket
6. Etapa 6: SSE /alerts/stream/ + CORS prod

Each phase is independently deployable and testable.

## Open Questions

- [ ] **Alert acknowledge persistence**: The PRD mentions PATCH /alerts/{id}/acknowledge as "soft-state in Backend only." Should this be stored in-memory (lost on restart), in Redis, or in a new lightweight table? Recommendation: Redis with TTL matching the alert's active window.
- [ ] **Job trigger mechanism**: POST /jobs/trigger/ creates a job record, but the actual AI Core execution is triggered how? Via a shared DB table the AI Core polls, or via Redis pub/sub? Recommendation: insert into `ingestion_jobs` with `on_demand=true` flag; AI Core polls for pending jobs.
- [ ] **GeoAlchemy2 model definitions**: The exact column names and geometry types in `geo_layers` table need to be confirmed against the AI Core's actual schema before writing ORM models.

## Next Step

Ready for tasks (sdd-tasks).
