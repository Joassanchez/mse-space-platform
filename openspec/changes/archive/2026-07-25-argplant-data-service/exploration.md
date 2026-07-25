## Exploration: ARGPLANT Data Service API

### Current State
Greenfield project on orphan branch `feature/argplant-data-service` with zero files. No existing architecture, dependencies, or legacy constraints. The goal is to build the Input and Data layers for ARGPLANT AI as a standalone, consumable API that aggregates agricultural data from multiple sources.

---

### API Landscape

#### 1. Modulo Agroclimatico (Agroclimatic Module)

| Source | Availability | Access Model | Format | Spatial/Temporal Resolution | Coverage | Python Client |
|---|---|---|---|---|---|---|
| **OpenWeather** | REST API | Free tier: 60 calls/min, 1M calls/month. API key required. Historical data requires paid tiers. | JSON, XML | Global, hyperlocal (city/station level) | Argentina (full) | `pyowm`, `httpx` |
| **NASA POWER** | REST API | Free. No API key for basic use; Earthdata login for higher throughput. | JSON, CSV, NetCDF | 0.5° x 0.5° (approx 50 km), Daily / Hourly / Monthly / Climatology | Global including Argentina | `requests`, `xarray` |
| **SNM (SMN Argentina)** | Website / Datos Abiertos | No reliable REST API identified. `smn.gob.ar/datos` returns 403. Likely requires scraping, manual download, or non-standard endpoints. | HTML / CSV / text | Station-based (sparse network) | Argentina only | None official. `BeautifulSoup` / `httpx` if scraping. |

**Key Findings**:
- **NASA POWER** is the strongest source for agroclimatic parameters (solar radiation, temperature, humidity, wind, precipitation). It is purpose-built for agriculture and solar energy modeling.
- **OpenWeather** is ideal for current conditions, short-term forecasts (up to 16 days), and national weather alerts.
- **SNM** is the highest-risk source. It lacks a documented modern API and its infrastructure has proven unreliable during this exploration. It should be treated as a **secondary fallback** or **future enhancement**.

#### 2. Modulo Satelital (Satellite Module)

| Source | Availability | Access Model | Format | Spatial/Temporal Resolution | Coverage | Python Client |
|---|---|---|---|---|---|---|
| **SMAP** | NASA Earthdata (NSIDC DAAC) | Free. Earthdata login required. | HDF5 | 36 km (radiometer-only since July 2015; radar failed) | Global | `earthaccess` (official, min Python 3.12) |
| **Sentinel-1** | Copernicus Data Space Ecosystem (CDSE) | Free. Registration required. Quota-based download. | SAFE / GRD / SLC / GeoTIFF | 5m x 20m (IW mode) | Global including Argentina | `eodag`, `sentinelhub`, direct STAC API |
| **Sentinel-2** | Copernicus Data Space Ecosystem (CDSE) | Free. Registration required. Quota-based download. | SAFE / L1C / L2A / GeoTIFF | 10m (RGB/NIR), 20m (SWIR), 60m (atmospheric) | Global including Argentina | `eodag`, `sentinelhub`, `stackstac` |
| **SAOCOM** | CONAE (Argentine space agency) | Deferred. Data exists but access is gated by CONAE portal. | HDF5 / GeoTIFF | Variable (SAR) | Argentina-focused | None mature. |

**Key Findings**:
- **SMAP** provides direct soil moisture measurements but at coarse resolution (36 km). The `earthaccess` library is the modern, NASA-recommended Python client for searching and downloading NASA Earthdata.
- **Sentinel-1** (SAR) can be used as a proxy for high-resolution soil moisture via backscatter analysis, compensating for SMAP's coarse resolution.
- **Sentinel-2** (multispectral) is the primary source for vegetation indices (NDVI, EVI, LAI). The Copernicus Data Space Ecosystem (CDSE) replaced the old SciHub. `sentinelsat` is aging and may not fully support CDSE; `eodag` or direct STAC API usage is preferred.
- **SAOCOM** is explicitly deferred per requirements.

#### 3. Modulo Agronomico (Agronomic Module)

- **External API**: None. This module is entirely reference/static data — lookup tables derived from agricultural science that rarely change.
- **Content — "Catálogos estáticos"**: These are predefined agronomic parameters used to interpret satellite and weather data:
  - **BBCH Growth Stages** (phenological scale): e.g., BBCH 60 = flowering, BBCH 79 = end of pod formation for soy.
  - **Crop Coefficients (Kc)** per growth stage: e.g., Kc initial 0.4, Kc mid 1.15, Kc end 0.5 (FAO-56).
  - **Temperature thresholds**: optimal 20-30°C, heat stress >35°C for soy.
  - **Water requirements**: 450-800 mm/cycle depending on maturity group.
  - **Anomaly sensitivity rules**: e.g., water stress during R3-R5 (grain filling) causes the highest yield loss.
- **Data Sources**: FAO-56 guidelines, INTA publications, academic literature.
- **Storage Strategy**: PostgreSQL relational tables with seeded data, or version-controlled JSON/YAML fixtures loaded at startup. These are not live APIs — they are reference tables that the model layer queries to interpret dynamic data from the Satellite and Agroclimatic modules.

#### 4. Modulo Economico (Economic Module)

- **Primary Source — Monitor de Granos (MAGyP)** ✅ Confirmed viable.
  - **Endpoint**: `https://monitorsiogranos.magyp.gob.ar/v5_ajax/cuadrosCotizaciones_min.php`
  - **Parameters**: `fechaDesde` (DD/MM/YYYY), `fechaHasta`, `producto` (numeric ID), `puerto` (numeric ID)
  - **Response format**: JSON with `minimos`, `maximos`, `promedios`, `modal` arrays — each entry has `fecha_concertacion` and `valor` (ARS).
  - **Example**: Producto `18` (to be confirmed — likely soy), Puerto `23` (to be confirmed — likely Rosario).
  - **Todo**: Map product IDs (soy, corn, wheat, sunflower) and port IDs to their names.
- **Secondary Sources**:
  - BCR (Bolsa de Comercio de Rosario) — may offer additional data services.
  - Global commodity APIs (Trading Economics, World Bank) — for international price context, not farm-gate.
- **Status**: Viable. The MAGyP endpoint provides daily price series with sufficient granularity for economic impact estimation. Product/port ID mapping is the only remaining unknown.

---

### Architecture Options

| Approach | Description | Pros | Cons | Complexity |
|---|---|---|---|---|
| **A. Monolith FastAPI (plain)** | Single FastAPI app, synchronous requests to external APIs. | Simplest to build and deploy. | Slow when calling multiple external APIs sequentially. Harder to scale individual modules later. | Low |
| **B. Modular Monorepo (FastAPI + Async)** | Single FastAPI app with internal package boundaries (`argplant.modules.*`). Uses `async`/`await` with `httpx` for concurrent external API calls. | Best balance of speed and structure. Modules are decoupled in code but deployed together. Shared DB and config. Easy to extract to microservices later. | Slightly more initial scaffolding (internal routers, service layers). | Medium |
| **C. Microservices from Day 1** | Four separate deployable services (Agroclimatic, Satellite, Agronomic, Economic) with inter-service HTTP or message-bus communication. | True independence, separate scaling, language flexibility per module. | Massive operational overhead for a greenfield MVP. Network latency, deployment complexity, and observability requirements multiply. | High |

**Storage & Infrastructure Choices**:
- **API Framework**: **FastAPI** is the clear winner. It is modern, has excellent async support, automatic OpenAPI documentation, and is familiar to the team from previous iterations.
- **Database**: **PostgreSQL** for all relational metadata, normalized agroclimatic time-series, agronomic catalogs, and economic price tables.
- **Raw Satellite Storage**: Local filesystem for MVP (store GeoTIFF/HDF5/SAFE files by tile and date). Abstract behind a storage interface so it can be migrated to **MinIO / S3-compatible** object storage later without code changes.
- **Cache**: **Redis** with TTL for external API responses (OpenWeather, NASA POWER) to respect rate limits and reduce latency.
- **Task Queue**: **Celery** with **Redis** or **RabbitMQ** broker, or **`arq`** (lighter, async-native) for scheduled ingestion and heavy satellite processing jobs.
- **Settings / Config**: **Pydantic-Settings** (v2) for centralized, environment-driven configuration including all external API keys and credentials.

**Recommendation**: Approach **B (Modular Monorepo with FastAPI + Async)**. It provides the best long-term evolution path without the day-1 operational burden of microservices.

---

### Module Boundaries

Each module exposes two interfaces:
1. **Internal Python API**: Repository and service layers used by other modules or background tasks.
2. **Public REST API**: Exposed via FastAPI routers under a unified application.

**Proposed Endpoint Prefixes**:
- `GET /api/v1/agroclimate/weather` — Current/forecast from OpenWeather
- `GET /api/v1/agroclimate/power` — Agroclimatic parameters from NASA POWER
- `GET /api/v1/satellite/smap` — SMAP soil moisture catalog / download
- `GET /api/v1/satellite/sentinel/search` — Sentinel catalog search
- `GET /api/v1/satellite/sentinel/{id}/download` — Sentinel product download
- `GET /api/v1/agronomy/crops` — List supported crops
- `GET /api/v1/agronomy/crops/{id}/stages` — Growth stages and thresholds
- `GET /api/v1/economy/prices` — Commodity price series

**Inter-Module Communication**:
- Modules communicate via direct internal Python service calls within the same process (no HTTP overhead, no message bus needed for MVP).
- A shared `locations` or `fields` registry table in PostgreSQL can link agronomic plots to their coordinates so that Agroclimatic and Satellite modules can query data for the same geometry.

**Authentication Strategy**:
- **External APIs**: Centralized configuration object (`pydantic-settings`). Each module owns its HTTP client but reads credentials from the same secure config. No hard-coded keys.
- **Internal Service**: Simple API key or JWT auth on the FastAPI gateway (deferred to a future security hardening phase if the service is internal-only initially).

---

### Data Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   External   │────▶│   Ingest     │────▶│  Normalize   │────▶│    Store     │
│   Sources    │     │  (Pull/API)  │     │  (Schemas)   │     │ (PG/Files/   │
│              │     │              │     │              │     │    Cache)    │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                                                                     │
                                                                     ▼
                                                              ┌──────────────┐
                                                              │    Serve     │
                                                              │  (FastAPI)   │
                                                              └──────────────┘
```

**Ingest**:
- **Scheduled Pulls**: Daily/hourly background jobs (Celery/`arq`) fetch baseline weather, update satellite catalogs, and refresh economic prices.
- **On-Demand Requests**: Live calls to OpenWeather and NASA POWER when a user queries a specific location and the cache is cold.
- **Satellite Bulk Download**: SMAP and Sentinel products are queued as background tasks because downloads are large and slow.

**Normalize**:
- Agroclimatic data converted to consistent units (metric), timestamps (UTC), and coordinate reference systems (WGS84).
- Satellite metadata (scene ID, cloud cover, acquisition date, footprint geometry) stored as structured records; raw files referenced by path/URL.

**Store**:
- PostgreSQL: All structured tables (weather_daily, satellite_scenes, crop_parameters, price_series).
- File Storage: Raw imagery organized by `source/tile/date/`.
- Redis: Hot cache for API responses (TTL 1h for forecasts, 24h for historical/climatology).

**Serve**:
- JSON responses for metadata, time-series, and catalog queries.
- For large raster delivery, the API should return download URLs or metadata rather than base64-encoded imagery.

---

### Risks

1. **SNM API Unavailability**: Argentina's Servicio Meteorológico Nacional lacks a reliable programmatic API. Any scraping solution is brittle and may violate terms of service. **Mitigation**: Treat OpenWeather + NASA POWER as primary weather sources; SNM as a future enhancement.
2. **Rate Limiting & Quotas**: OpenWeather free tier has limits. CDSE imposes download quotas. NASA Earthdata may throttle excessive requests. **Mitigation**: Aggressive Redis caching, scheduled pulls during off-peak hours, and graceful degradation (return cached data with a `stale` flag).
3. **Satellite Data Volume**: A single Sentinel-2 L2A tile can exceed 100 MB. Covering Argentine agricultural regions regularly will consume significant disk/bandwidth. **Mitigation**: Store only requested tiles, use cloud-optimized GeoTIFFs (COG) if possible, and plan for object storage migration.
4. **Authentication Complexity**: Earthdata and CDSE both require OAuth2 or token-based authentication with refresh logic. **Mitigation**: Wrap clients in reusable auth managers that handle token refresh automatically.
5. **SMAP Resolution Gap**: SMAP radiometer resolution (36 km) is too coarse for field-level anomaly detection. **Mitigation**: Use Sentinel-1 SAR backscatter as a high-resolution soil moisture proxy or downscaling models.
6. **On-Demand Satellite Latency**: Generating indices (e.g., NDVI) or downloading raw products on-the-fly is too slow for a synchronous REST call. **Mitigation**: All heavy satellite processing must be asynchronous (background jobs + polling or webhook status endpoints).
7. **Economic Data — Product/Port ID Mapping**: The MAGyP Monitor de Granos endpoint is confirmed viable, but numeric product and port IDs (e.g., `producto=18`, `puerto=23`) need to be mapped to crop names and port locations. **Mitigation**: Reverse-engineer the ID mapping from the Monitor de Granos web interface or MAGyP documentation during implementation.
8. **Async I/O Learning Curve**: If the team is not deeply familiar with `async`/`await`, debugging concurrent HTTP client issues can be non-trivial. **Mitigation**: Isolate async code in client adapters and keep business logic synchronous where possible.

---

### Ready for Proposal

**Yes.**

The orchestrator should proceed to `sdd-propose`. The exploration has identified viable APIs for all primary sources — including the MAGyP Monitor de Granos for economic data — confirmed the feasibility of a FastAPI-based modular monorepo, and surfaced the key risks (especially SNM reliability and satellite data volume). The Argentine meteorological service (SNM) does not offer a stable public API and should be treated as a secondary fallback or future enhancement. The satellite module must account for download quotas and storage growth.
