## Exploration: Data Connectors & Context Enrichment (Módulo 6)

### Current State

The system has three existing modules:
- **M2 (Ingestion)**: `src/ingestion/` with `BaseIngestionConnector` ABC and `SmapConnector` for NASA Earthdata / NSIDC HDF5 file downloads. Uses `earthaccess` library, downloads to `data/raw/`, registers in `metadata_repository`. Pattern: authenticate → search → download → validate → extract_metadata → register.
- **M3 (Geospatial ETL)**: `src/geospatial/` with domain models (`Region`, `Indicator`, `ProcessedLayer`, `RiskAssessment`), repository interfaces (`RegionRepository`, `IndicatorRepository`, etc.), and PostgreSQL implementations. Tables created in migrations 002 and 003 with PostGIS.
- **M4 (AI Ecosystem)**: `src/ai/` with `ContextEngineImpl` that reads from M3 repos to build structured JSON context payloads for agents. Method `build_context(region_ids, indicator_codes, max_age_hours)` returns regions, layers, indicators, risk assessments.

The `ContextEngine` interface (in `src/ai/domain/interfaces.py`) declares only `build_context()` and `summarize_context()`. Tests use `MagicMock` repos (see `tests/ai/unit/test_context_engine.py`).

Seeds live in `seeds/002_geospatial_storage.sql` with `ON CONFLICT DO NOTHING`. Migrations follow `migrations/NNN_name.sql` with `BEGIN/COMMIT` and `IF NOT EXISTS`.

Sources are configured in `src/config/sources.yaml` (currently only `smap`).

### Affected Areas
- `src/ai/domain/interfaces.py` — `ContextEngine` interface needs new method for enriched context
- `src/ai/infrastructure/context/context_engine.py` — `ContextEngineImpl` needs new repos and method
- `src/geospatial/domain/models.py` — potential home for `WeatherSnapshot` (option)
- `src/geospatial/domain/interfaces.py` — potential home for `WeatherSnapshotRepository` (option)
- `src/config/sources.yaml` — needs `openweather` and `indec` source entries
- `src/ingestion/base_connector.py` — relevant as the existing connector pattern (but weather is different)
- `migrations/` — needs `007_weather_snapshots.sql`
- `seeds/` — needs `003_socioeconomic_demo.sql`
- `tests/ai/unit/test_context_engine.py` — needs tests for enriched context
- `pytest.ini` — may need marker addition if `weather` tests get their own directory

### Questions & Approaches

#### Q1: Where should `weather_snapshots` table go?

**Approach 1a: Inside `src/geospatial/` (M3 extension)**
- Add `WeatherSnapshot` dataclass to `src/geospatial/domain/models.py`
- Add `WeatherSnapshotRepository` ABC to `src/geospatial/domain/interfaces.py`
- Impl in `src/geospatial/infrastructure/persistence/weather_repo.py`

| Pros | Cons | Complexity |
|------|------|------------|
| Existing ContextEngine already imports from here | M3 was for raster/satellite processing — weather is tabular/API data | Low |
| Co-located with `Region` model (weather has region FK) | Blurs module boundary — M3 becomes a dumping ground | |
| Reuses `get_connection()` from `connection.py` | | |
| Migration 007 follows same convention | | |

**Approach 1b: New `src/weather/` domain module** ✅ *(Recommended)*
- `src/weather/domain/models.py` → `WeatherSnapshot` dataclass
- `src/weather/domain/interfaces.py` → `WeatherSnapshotRepository` ABC
- `src/weather/infrastructure/weather_repo.py` → PostgreSQL impl
- `src/weather/connectors/openweather_connector.py`

| Pros | Cons | Complexity |
|------|------|------------|
| Clean separation of concerns — weather is its own bounded context | ContextEngine must import from another domain package | Medium |
| Weather data has a different lifecycle (API polling vs file processing) | | |
| Avoids bloating M3 | | |
| Follows the same layered architecture pattern | | |

**Verdict**: Approach 1b — `WeatherSnapshot` and its repository belong in a dedicated `src/weather/` module. The ContextEngine already imports from multiple domains (geospatial), so importing from weather is the same pattern.

---

#### Q2: Should OpenWeatherConnector use `src/ingestion/` or `src/weather/`?

**Approach 2a: In `src/ingestion/weather/`**
- Nest under existing ingestion package
- Implement `BaseIngestionConnector`

| Pros | Cons | Complexity |
|------|------|------------|
| Reuses existing ABC pattern | `BaseIngestionConnector` is designed for file-download sources, not REST APIs | Medium |
| Stays under the "ingestion" concept | `download()` doesn't download files, `validate()` doesn't validate HDF5 | |
| | Forces OpenWeather into wrong abstractions (e.g., `authenticate()` returns bool but OpenWeather just passes an API key) | |
| | Mixed concerns: ingestion is for raw file storage, weather is for tabular snapshots | |

**Approach 2b: Standalone in `src/weather/connectors/openweather_connector.py`** ✅ *(Recommended)*
- Own class, not extending `BaseIngestionConnector`
- Follows semantically similar method names: `fetch()`, `parse()`, `store()` instead of `search()`, `download()`, `register()`
- Imports `WeatherSnapshotRepository` directly

| Pros | Cons | Complexity |
|------|------|------------|
| Clean semantics for REST API | Doesn't reuse base connector pattern | Low |
| No abstraction mismatch | | |
| Can evolve independently | | |
| Easy to test (just mock `requests`) | | |

**Verdict**: Approach 2b. OpenWeather is a REST API that returns JSON, not a file-download service. Forcing it into `BaseIngestionConnector` creates a leaky abstraction. Standalone class with `fetch_weather()` / `store_snapshot()` semantics is clearer.

---

#### Q3: How should the ContextEngine be extended?

**Approach 3a: New method `build_enriched_context()`** ✅ *(Recommended)*
- Adds to `ContextEngine` interface: `build_enriched_context(region_ids, ...) -> dict`
- Internally calls `build_context()` then appends weather + socioeconomic sections
- New repos (`WeatherSnapshotRepository`, plus a read-only interface for socioeconomic) injected via constructor

| Pros | Cons | Complexity |
|------|------|------------|
| Zero impact on existing `build_context()` callers | Duplicates some of what build_context does | Low |
| Clean evolution path | | |
| Agents opt-in to enrichment | | |

**Approach 3b: Extend `build_context()` with optional params**
- Add `include_weather: bool = False`, `include_socioeconomic: bool = False`

| Pros | Cons | Complexity |
|------|------|------------|
| Single method to maintain | Changes signature — breaks existing tests | Medium |
| | Makes the method complex with conditional logic | |
| | Tests need more fixture setup | |

**Approach 3c: Separate context builder classes**
- `WeatherContextBuilder`, `SocioeconomicContextBuilder` composed by an orchestrator

| Pros | Cons | Complexity |
|------|------|------------|
| Maximum extensibility | Over-engineered for this scope | High |
| Single Responsibility | More files, more wiring | |

**Verdict**: Approach 3a. Add `build_enriched_context()` to the interface and implementation. It's a pragmatic middle ground — doesn't break existing code, doesn't over-engineer.

---

#### Q4: Seed data strategy for demo socioeconomic indicators?

**Approach 4a: SQL seed file `seeds/003_socioeconomic_demo.sql`** ✅ *(Recommended)*
- Insert into the existing `indicators` table (already has: region_id, indicator_code, indicator_name, value, unit, metadata)
- Mark with `metadata = '{"demo": true}'` in JSONB
- Use the pilot Chaco region (id from existing seed)
- `ON CONFLICT DO NOTHING` for idempotency

| Pros | Cons | Complexity |
|------|------|------------|
| Matches existing `seeds/002_geospatial_storage.sql` pattern | SQL only, less flexible | Low |
| Version-controlled with git | | |
| Idempotent, safe to re-run | | |

**Approach 4b: Python script `scripts/seed_socioeconomic.py`**

| Pros | Cons | Complexity |
|------|------|------------|
| More flexible (can generate data) | Doesn't match existing pattern | Low |
| | Adds a new kind of seed artifact | |

**Verdict**: Approach 4a. Follow the established convention. Example indicators: GDP per capita, HDI, poverty rate, literacy rate, agricultural area, population density. All marked `"demo": true` in metadata.

---

#### Q5: IndecConnector minimal viable design?

**Approach 5a: Stub in `src/socioeconomic/connectors/indec_connector.py`** ✅ *(Recommended)*
- Define `SocioeconomicConnector` ABC with `fetch_indicators(region_id: int, year: int | None = None) -> list[Indicator]`
- `IndecConnector` implements it returning canned demo data
- Stored in a new `src/socioeconomic/` module alongside the ABC

| Pros | Cons | Complexity |
|------|------|------------|
| Clean separation from weather | New top-level module | Low |
| Establishes contract early | | |
| Demo data can feed into ContextEngine immediately | | |

**Approach 5b: Just add to `src/weather/`**

| Pros | Cons | Complexity |
|------|------|------------|
| Fewer modules | Socioeconomic data ≠ weather | Low |
| | Creates a misleading "weather" package | |

**Verdict**: Approach 5a. Define a `SocioeconomicConnector` ABC + `IndecConnector` stub in `src/socioeconomic/`. The stub returns demo data that feeds into the `indicators` table. Full implementation is out of scope for this change.

### Recommendation

```
Module layout:
  src/weather/
    __init__.py
    domain/
      __init__.py
      models.py              # WeatherSnapshot dataclass
      interfaces.py           # WeatherSnapshotRepository ABC
    infrastructure/
      __init__.py
      weather_repo.py         # WeatherSnapshotRepositoryImpl (PostgreSQL)
    connectors/
      __init__.py
      openweather_connector.py  # Standalone REST API connector

  src/socioeconomic/
    __init__.py
    base_connector.py         # SocioeconomicConnector ABC
    connectors/
      __init__.py
      indec_connector.py      # Stub returning demo data

Migrations:
  migrations/007_weather_snapshots.sql

Seeds:
  seeds/003_socioeconomic_demo.sql

Context Engine:
  src/ai/domain/interfaces.py → add build_enriched_context()
  src/ai/infrastructure/context/context_engine.py → implement it
  Inject WeatherSnapshotRepository + optional socioeconomic reader

Tests:
  tests/weather/unit/test_openweather_connector.py  (mock requests)
  tests/weather/unit/test_weather_repo.py            (mock psycopg2)
  tests/ai/unit/test_context_engine.py               (extend with new method tests)
  tests/socioeconomic/unit/                          (optional, lightweight)
```

### Risks
- **Scope creep on IndecConnector**: Keep it as a stub/contract only. Full INDEC API integration requires understanding their data format and availability.
- **ContextEngine becoming a monolith**: `build_enriched_context()` is a pragmatic addition, but if weather and socioeconomic data grow independently, consider breaking into separate context builders.
- **Weather API dependency**: OpenWeather free tier has rate limits. The connector must handle 429 responses gracefully with retry/backoff.
- **Migration ordering**: 007 depends on 003 (regions table) being applied first. Document this dependency.
- **400-line budget risk**: Estimated ~750 lines of new code. Chained PRs recommended: (1) migration + weather domain, (2) OpenWeatherConnector + tests, (3) ContextEngine extension + tests, (4) socioeconomic stubs + seed.

### Ready for Proposal
Yes. All 5 questions have clear recommendations. The orchestrator should proceed with `sdd-propose` for `modulo-6-data-connectors-context-enrichment`.
