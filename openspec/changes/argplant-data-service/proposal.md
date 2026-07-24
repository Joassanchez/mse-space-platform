# Proposal: ARGPLANT Data Service API

## Intent

Agricultural producers and agronomists in Argentina's Pampa Húmeda lack a unified, programmatic source of agroclimatic, satellite, and economic data. Today they aggregate soil moisture, weather, crop parameters, and grain prices manually from disparate portals (NASA, Copernicus, MAGyP, INTA).

ARGPLANT Data Service API consolidates these into a single, free, async REST API with a **dual purpose**:

1. **Primary — Internal consumer**: Serves as the data ingestion and normalization layer for the full ARGPLANT AI pipeline. The downstream model layer queries this API with structured input (region, coordinates, lot, crop, analysis date, operation) and receives aggregated, normalized data ready for anomaly detection and prediction.
2. **Fallback — Standalone product**: If the full project (model → prediction → communication layers) is not completed within timeline, this API can be wrapped with a polished frontend and presented as an independent, publicly consumable agricultural data service — "ARGPLANT Data Service". The OpenAPI docs at `/docs` serve as both developer documentation and a live demo.

## Scope

### In Scope
- **Agroclimatic module**: NASA POWER (agroclimatic parameters) and OpenWeather (forecast/current) — fully functional
- **Satellite module**: SMAP soil moisture metadata (earthaccess) and Sentinel-1/2 catalog search + async download (CDSE) — fully functional
- **Agronomic module**: Static reference catalogs — BBCH stages, Kc coefficients, temperature thresholds — seeded from FAO-56/INTA literature
- **Economic module**: MAGyP Monitor de Granos daily price series (soy, corn, wheat, sunflower) — stubbed with core endpoint
- **Shared infra**: PostgreSQL, Redis (TTL cache), arq task queue, Pydantic-Settings v2 config, modular FastAPI routers
- IP-based rate limiting (no full auth system)
- OpenAPI/Swagger docs at `/docs` for demo/presentation
- Geography: INTA Pergamino case study area (Pampa Húmeda)

### Out of Scope
- Model, prediction, and communication layers
- SAOCOM (CONAE access gated), SNM (no stable API)
- Full Argentina coverage (Pergamino only for MVP)
- Auth system beyond IP rate limiting
- MinIO/S3 storage (local filesystem; abstracted behind interface)
- Frontend applications

## Capabilities

### New Capabilities
- `agroclimate-data`: Weather forecasts (OpenWeather) and agroclimatic parameters — solar radiation, temperature, humidity, precipitation (NASA POWER). Endpoints: `/api/v1/agroclimate/weather`, `/api/v1/agroclimate/power`.
- `satellite-data`: SMAP soil moisture metadata and Sentinel-1/2 catalog search with async download. Endpoints: `/api/v1/satellite/smap`, `/api/v1/satellite/sentinel/search`, `/api/v1/satellite/sentinel/{id}/download`.
- `agronomy-catalog`: Static reference lookup tables — BBCH phenological stages, Kc coefficients, temperature thresholds. Endpoints: `/api/v1/agronomy/crops`, `/api/v1/agronomy/crops/{id}/stages`.
- `economy-prices`: Daily commodity price series from MAGyP Monitor de Granos. Endpoint: `/api/v1/economy/prices`.
- `data-ingestion-pipeline`: Shared arq + Redis task queue for scheduled pulls, satellite download jobs, and cache warming.

### Modified Capabilities
None — greenfield project.

## Approach

Modular monorepo (Approach B from exploration). Four internal packages — `argplant.modules.{agroclimate,satellite,agronomy,economy}` — each with router, service, repository, and HTTP client. Async `httpx` for concurrent external API calls. Satellite downloads run as arq background tasks. Redis cache with TTL (1h forecasts, 24h historical). Raw satellite files stored locally behind a storage interface for future MinIO migration. Config centralized via Pydantic-Settings v2.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `argplant/` | New | Root package |
| `argplant/modules/agroclimate/` | New | NASA POWER + OpenWeather |
| `argplant/modules/satellite/` | New | SMAP + Sentinel-1/2 |
| `argplant/modules/agronomy/` | New | Static catalogs (seed data) |
| `argplant/modules/economy/` | New | MAGyP price series |
| `argplant/shared/` | New | Config, DB, cache, storage, arq |
| `argplant/main.py` | New | FastAPI entry point |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| SMAP 36 km resolution too coarse for fields | High | Sentinel-1 SAR backscatter as soil moisture proxy |
| CDSE download quotas | Med | Scheduled off-peak pulls; Pergamino-only tile scope |
| OpenWeather free tier rate limits | Med | Aggressive Redis caching; stale flag on cold cache |
| MAGyP endpoint changes product/port IDs | Low | Reverse-engineer ID mapping; monitor endpoint |
| Async/httpx debugging complexity | Low | Isolate async in client adapters; sync business logic |

## Rollback Plan

Greenfield on orphan branch `feature/argplant-data-service`. Rollback: merge main, delete feature branch. All infra is containerized (Docker Compose) — no persistent production state.

## Dependencies

- Earthdata login (SMAP) + CDSE registration (Sentinel)
- OpenWeather API key (free tier)
- MAGyP public endpoint (no auth required)
- Docker Compose (PostgreSQL, Redis)

## Success Criteria

- [ ] Agroclimatic module serves weather + POWER parameters for INTA Pergamino coordinates
- [ ] Satellite module returns SMAP metadata and Sentinel catalog results for Pergamino bounding box
- [ ] Agronomic module serves BBCH stages, Kc coefficients, and temperature thresholds
- [ ] Economic module returns daily soy/corn prices from MAGyP
- [ ] arq background pipeline executes at least one daily ingestion job
- [ ] OpenAPI docs accessible at `/docs` with all endpoints documented and usable as live demo
- [ ] API is frontend-ready: all responses are JSON, CORS configured, rate limiting transparent
- [ ] API can be demonstrated standalone (via Swagger UI) without requiring the model/prediction layers
- [ ] IP-based rate limiting active on all public endpoints
- [ ] All external credentials loaded via Pydantic-Settings (no hard-coded keys)
