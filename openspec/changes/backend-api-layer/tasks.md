# Tasks: Backend API Layer

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 2000-3000 lines (35+ new files) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: Foundation (Phase 1) → PR 2: APIs (Phase 2-4) → PR 3: Real-time + Docker (Phase 5-6) |
| Delivery strategy | auto-forecast |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main (resolved)
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | FastAPI base, config, DB session, health/ready, auth, tests | PR 1 | Base branch: main; includes conftest.py, test_auth.py |
| 2 | Regions + Analysis APIs with services, schemas, tests | PR 2 | Depends on PR 1; test_regions.py, test_analysis.py |
| 3 | Geo + Alerts APIs + Redis cache layer + tests | PR 3 | Depends on PR 2; test_geo.py, test_alerts.py |
| 4 | Jobs API + WebSocket + SSE + Docker + tests | PR 4 | Depends on PR 3; test_jobs.py, Dockerfile |

## Phase 1: Foundation (Backend Base + Health + Auth)

- [x] 1.1 Create `backend/__init__.py`, `backend/config.py` with Settings class (DATABASE_URL, REDIS_URL, API_KEY, ALLOWED_ORIGINS)
- [x] 1.2 Create `backend/db/__init__.py`, `backend/db/session.py` with create_async_engine() and async_sessionmaker()
- [x] 1.3 Create `backend/core/__init__.py`, `backend/core/auth.py` with verify_api_key() dependency
- [x] 1.4 Create `backend/main.py` with FastAPI app, lifespan (DB/Redis connect/disconnect), CORS middleware, structured logging
- [x] 1.5 Create `backend/dependencies.py` with get_db_session() shared dependency provider
- [x] 1.6 Add backend dependencies to `requirements.txt`: fastapi, uvicorn, asyncpg, redis, GeoAlchemy2, shapely, httpx, pytest-asyncio
- [ ] 1.7 Update `.env.example` with DATABASE_URL, REDIS_URL, API_KEY, ALLOWED_ORIGINS, BACKEND_API_KEY
- [x] 1.8 Create `backend/tests/__init__.py`, `backend/tests/conftest.py` with async fixtures, test client, API key override
- [x] 1.9 Create `backend/tests/test_auth.py` testing 401 without key, 200 with key per backend-api spec
- [ ] 1.10 Create `backend/tests/test_health.py` testing /health and /ready endpoints per backend-api spec scenarios

## Phase 2: Regions + Analysis APIs

- [x] 2.1 Create `backend/schemas/__init__.py`, `backend/schemas/regions.py` with RegionList, RegionDetail Pydantic models
- [x] 2.2 Create `backend/schemas/analysis.py` with AnalysisList, AnalysisDetail, AnalysisLatest, AnalysisSummary models
- [x] 2.3 Create `backend/db/models.py` with read-only ORM models: Region, AgentExecution (no writes)
- [x] 2.4 Create `backend/services/__init__.py`, `backend/services/region_service.py` with get_regions(), get_region_by_id()
- [x] 2.5 Create `backend/services/analysis_service.py` with get_executions(), get_execution_by_id(), get_latest_by_region(), get_summary()
- [x] 2.6 Create `backend/api/__init__.py`, `backend/api/v1/__init__.py`, `backend/api/v1/router.py` aggregating v1 routers
- [x] 2.7 Create `backend/api/v1/regions.py` with GET /regions/, GET /regions/{region_id} per regions-api spec
- [x] 2.8 Create `backend/api/v1/analysis.py` with GET /analysis/, /analysis/{id}, /analysis/latest/, /analysis/summary/ per analysis-api spec
- [x] 2.9 Create `backend/tests/test_regions.py` testing list and detail scenarios per regions-api spec
- [x] 2.10 Create `backend/tests/test_analysis.py` testing pagination, latest, summary scenarios per analysis-api spec

## Phase 3: Geo API + Cache Layer

- [ ] 3.1 Create `backend/schemas/geo.py` with GeoFeatureCollection, GeoMetadata, GeoFeature Pydantic models
- [ ] 3.2 Create `backend/db/models.py` add GeoLayer ORM model with PostGIS geometry columns
- [ ] 3.3 Create `backend/core/cache.py` with CacheManager: get(), set(), invalidate(), pattern_delete()
- [ ] 3.4 Create `backend/services/geo_service.py` with queries for regions, soil-moisture, risk-zones, alerts, flood-extent using GeoAlchemy2
- [ ] 3.5 Create `backend/api/v1/geo.py` with GET /geo/regions/, /soil-moisture/, /risk-zones/, /alerts/, /flood-extent/ per geo-api spec
- [ ] 3.6 Add cache middleware to router with TTL per endpoint pattern (analysis: 300s, geo: 600s, regions: 3600s)
- [ ] 3.7 Create `backend/tests/test_geo.py` testing GeoJSON validity, feature structure, metadata per geo-api spec scenarios
- [ ] 3.8 Create `backend/tests/test_cache.py` testing cache hit/miss, TTL expiration, pattern invalidation per backend-cache spec

## Phase 4: Alerts API + SSE Stream

- [ ] 4.1 Create `backend/schemas/alerts.py` with AlertList, AlertDetail, AlertCount, AlertSSEEvent Pydantic models
- [ ] 4.2 Create `backend/db/models.py` add Alert ORM model with severity, event_type, is_active, geometry columns
- [ ] 4.3 Create `backend/services/alert_service.py` with get_alerts(), get_alert_by_id(), get_active_count(), acknowledge_alert(), stream_new_alerts()
- [ ] 4.4 Create `backend/api/v1/alerts.py` with GET /alerts/, /alerts/{id}, /active/count/, PATCH /alerts/{id}/acknowledge/, GET /alerts/stream/ (SSE) per alerts-api spec
- [ ] 4.5 Add PostgreSQL LISTEN/NOTIFY integration in alert_service for SSE stream using asyncpg
- [ ] 4.6 Create `backend/tests/test_alerts.py` testing severity sorting, active count, acknowledge, SSE stream per alerts-api spec

## Phase 5: Jobs API + WebSocket

- [ ] 5.1 Create `backend/schemas/jobs.py` with JobList, JobDetail, JobTriggerRequest, JobTriggerResponse, JobLog Pydantic models
- [ ] 5.2 Create `backend/db/models.py` add IngestionJob ORM model with status, progress_pct, ws_channel columns
- [ ] 5.3 Create `backend/core/ws_manager.py` with ConnectionManager: register(), disconnect(), broadcast_to_job()
- [ ] 5.4 Create `backend/services/job_service.py` with get_jobs(), get_job_by_id(), trigger_job(), get_logs()
- [ ] 5.5 Create `backend/api/v1/jobs.py` with GET /jobs/, /jobs/{id}, /jobs/{id}/logs/, POST /jobs/trigger/, WS /ws/jobs/{job_id} per jobs-api spec
- [ ] 5.6 Add WebSocket endpoint handler with job.started, job.progress, job.completed, job.failed event emission
- [ ] 5.7 Create `backend/tests/test_jobs.py` testing job list, trigger, logs, WebSocket lifecycle per jobs-api spec scenarios

## Phase 6: Docker Integration

- [ ] 6.1 Create `backend/Dockerfile` with python:3.11-slim, uvicorn, no GDAL (backend doesn't process geo)
- [ ] 6.2 Update `docker-compose.yml` add backend service (port 8000) and redis service (port 6379) on geoai_network
- [ ] 6.3 Create `backend/requirements.txt` with backend-specific dependencies pinned to versions
- [ ] 6.4 Verify docker-compose build succeeds for backend service
- [ ] 6.5 Verify /health endpoint returns 200 with db: connected, redis: connected in Docker environment

## Phase 7: Polish + Full Test Suite

- [ ] 7.1 Run full test suite with `pytest -v` and verify all 31 requirements, 42 scenarios pass
- [ ] 7.2 Verify GeoJSON validity for all /geo/ endpoints with jsonschema validation
- [ ] 7.3 Verify WebSocket event emission with httpx AsyncClient WS connection
- [ ] 7.4 Verify SSE stream emits events on PostgreSQL NOTIFY trigger
- [ ] 7.5 Update README.md with backend API documentation, endpoints list, authentication requirements
- [ ] 7.6 Remove any temporary code, TODOs, or debug logging from production code
- [ ] 7.7 Verify all cache TTLs match spec (analysis: 5min, geo: 10min, alerts/count: 1min, regions: 60min)
