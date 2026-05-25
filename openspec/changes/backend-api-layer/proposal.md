# Proposal: Backend API Layer

## Intent

Implementar una API REST asíncrona con FastAPI que exponga resultados de agentes, capas geoespaciales, alertas y gestión de jobs para el Frontend dashboard, según lo especificado en `docs/PRD_backend_api_layer.md`. El Backend NO ejecuta lógica de agentes ni procesamiento geoespacial — consume exclusivamente PostgreSQL+PostGIS con modelos de solo lectura.

## Scope

### In Scope
- FastAPI base app con lifespan, middleware, health/readiness endpoints
- Async DB session vía SQLAlchemy 2.0 async + asyncpg
- Schemas Pydantic v2 para todos los endpoints (analysis, alerts, geo, jobs, regions)
- Endpoints REST: /analysis/, /alerts/, /geo/, /jobs/, /regions/
- WebSocket canal por job_id para notificación en tiempo real
- SSE stream de alertas activas vía LISTEN/NOTIFY de PostgreSQL
- Redis cache layer con TTL por endpoint e invalidación por tag
- API Key estática como FastAPI dependency
- ORM models de solo lectura sobre tablas existentes del AI Core
- Docker Compose integration (nuevo servicio backend)
- Tests async con pytest-asyncio + httpx

### Out of Scope
- JWT / roles de usuario (post-MVP)
- MVT vector tiles (etapa 2)
- Endpoints de área Económico-Productivo (requiere agentes completados)
- Rate limiting avanzado por usuario
- Exportación PDF desde Backend

## Capabilities

### New Capabilities
- `backend-api`: Capa base FastAPI — app, lifespan, middleware, dependencies, health/readiness
- `analysis-api`: Endpoints de resultados de agentes (/analysis/)
- `alerts-api`: Endpoints de alertas activas (/alerts/) + SSE stream
- `geo-api`: Endpoints de capas geoespaciales GeoJSON (/geo/)
- `jobs-api`: Endpoints de gestión de jobs (/jobs/) + WebSocket
- `regions-api`: Endpoints de regiones configuradas (/regions/)
- `backend-cache`: Redis cache layer con TTL por endpoint e invalidación

### Modified Capabilities
- None

## Approach

Estructura hexagonal-like por capas siguiendo el PRD:

```
backend/
├── main.py              # App FastAPI, lifespan, middleware
├── config.py            # pydantic-settings
├── dependencies.py      # DB session, auth, shared deps
├── api/v1/              # Routers: analysis, alerts, geo, jobs, regions
├── schemas/             # Pydantic response models
├── services/            # Queries a DB, construyen responses
├── db/                  # AsyncSession factory + ORM models (read-only)
├── core/                # auth, cache, ws_manager
└── tests/               # pytest-asyncio + httpx
```

El Backend comparte DB con AI Core pero NO importa módulos del mismo. Se agrega como servicio independiente en docker-compose.yml.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/` | New | Todo el módulo nuevo: ~20 archivos |
| `docker-compose.yml` | Modified | Agregar servicio backend + redis |
| `requirements.txt` | Modified | Agregar fastapi, uvicorn, asyncpg, redis, etc. |
| `Dockerfile` | Modified | Entrypoint alternativo para backend |
| `.env.example` | Modified | Variables backend (API_KEY, REDIS_URL, etc.) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Modelos ORM desactualizados vs DB real | Medium | Usar reflection o sync con migraciones existentes |
| Cache invalidation compleja sin eventos del AI Core | Medium | Usar TTL generoso + invalidación manual como fallback |
| WebSocket/SSE en entorno Docker con múltiples réplicas | Low | Redis pub/sub como backend de WS en etapa 2 |

## Rollback Plan

Revertir el commit que agrega `backend/`, restaurar `docker-compose.yml`, `requirements.txt` y `Dockerfile` a su estado anterior. El AI Core no se ve afectado porque el Backend solo lee DB.

## Dependencies

- PostgreSQL+PostGIS operativo con datos de agentes
- Redis 7+ (nuevo servicio en docker-compose)
- Tablas existentes: agent_executions, alerts, ingestion_jobs, raw_files, regions, geo_layers

## Success Criteria

- [ ] GET /api/v1/analysis/latest/?region_id=cordoba_pilot devuelve el último análisis con structured_output y natural_language_summary
- [ ] GET /api/v1/geo/soil-moisture/?region_id=cordoba_pilot devuelve GeoJSON válido con sm_surface, sm_rootzone, status
- [ ] GET /api/v1/alerts/?region_id=cordoba_pilot devuelve alertas activas ordenadas por severidad
- [ ] POST /api/v1/jobs/trigger/ crea job on-demand y devuelve job_id + ws_channel
- [ ] WS /ws/jobs/{job_id} emite eventos de progreso
- [ ] GET /api/v1/regions/ devuelve regiones activas con bbox y metadata
- [ ] /health responde 200 OK con DB y Redis disponibles
- [ ] Request sin X-API-Key recibe 401
- [ ] Tests async pasan con pytest -v
