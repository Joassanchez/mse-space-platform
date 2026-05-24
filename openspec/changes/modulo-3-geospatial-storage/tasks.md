# Tasks: Módulo 3 - Geospatial Storage

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~700-850 |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Slice 1: Foundation ~300-350 lines) → PR 2 (Slice 2: Implementation ~400-500 lines) |
| Delivery strategy | auto-forecast |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | PostGIS infra + migration 003 + domain models + constants + interfaces + unit tests | PR 1 | base: main; Docker → postgis/postgis:15-3.4-alpine, non-destructive migration |
| 2 | 7 repositories + seeds + audit integration + integration tests + regression verify | PR 2 | base: main; depends on PR 1 merged; full implementation |

## Phase 1: Infrastructure & PostGIS Enablement

- [x] 1.1 Update `docker-compose.yml`: change `postgres:15-alpine` → `postgis/postgis:15-3.4-alpine` (misma base Alpine, PostGIS 3.4 sobre PG15, volumen compatible, hacer backup antes)
- [x] 1.2 Create `migrations/003_add_postgis_and_models.sql`: `CREATE EXTENSION IF NOT EXISTS postgis` (transactional, non-destructive, `IF NOT EXISTS` en todas las operaciones)
- [x] 1.3 Add `regions` table: `CREATE TABLE IF NOT EXISTS regions`, columns `id`, `name`, `geometry GEOMETRY(MultiPolygon,4326)`, `region_type`, `country`, `province`, `bbox`, `area_km2`, `metadata JSONB`, `is_active`, timestamps; GIST index on geometry
- [x] 1.4 Add `indicators`, `risk_assessments`, `alerts`, `economic_impacts`, `audit_logs` tables with `CREATE TABLE IF NOT EXISTS`, FKs, CHECK constraints, and B-tree indexes
- [x] 1.5 Alter `processed_geospatial_layers`: `ADD COLUMN IF NOT EXISTS footprint_geometry GEOMETRY(Polygon,4326)` nullable + GIST index, `ADD COLUMN IF NOT EXISTS data_source_id` nullable FK → `data_sources(id)`. `bbox NUMERIC[]` preserved, NOT modified
- [x] 1.6 Verify migration idempotency: run twice without errors or duplicates (migration uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS throughout — structurally idempotent)

## Phase 2: Domain Models & Constants

- [x] 2.1 Create `src/geospatial/domain/constants.py`: enums `EntityType`, `Action`, `ActorType`, `RiskType`, `RiskLevel`, `Severity`, `AlertStatus`, `RegionType`
- [x] 2.2 Extend `src/geospatial/domain/models.py`: add `Region`, `Indicator`, `RiskAssessment`, `Alert`, `EconomicImpact`, `AuditLog` dataclasses
- [x] 2.3 Extend `ProcessedLayer` dataclass: add `footprint_geometry: Optional[Polygon]` (Polygon desde `shapely.geometry.Polygon`, acorde al tipo DB `GEOMETRY(Polygon,4326)`), `data_source_id: Optional[int]`, `data_source_code: Optional[str]`
- [x] 2.4 In models: import `shapely.geometry.Polygon` para footprint_geometry, `MultiPolygon` para regions geometry, `shapely.wkt` para serialización. Definir geometrías como `Optional` para permitir NULL en DB
- [x] 2.5 Extend `DataSource` model/dataclass con campos del PRD M3 (opcional vía `config JSONB` existente o columnas nuevas): `config JSONB` ya almacena metadata flexible; decisión documentada — no se requieren columnas explícitas en esta fase

## Phase 3: Domain Interfaces

- [x] 3.1 Extend `src/geospatial/domain/interfaces.py`: add ABCs `RegionRepository`, `IndicatorRepository`, `RiskAssessmentRepository`, `AlertRepository`, `EconomicImpactRepository`, `DataSourceRepository`, `AuditRepository`
- [x] 3.2 Define abstract methods: `save()`, `get_by_id()`, `find_by_*()` with type hints using new domain models

## Phase 4: Unit Tests (Slice 1 Verification)

- [x] 4.1 Create `tests/geospatial/unit/test_storage_models.py`: test dataclass construction, default values, field types
- [x] 4.2 Test `constants.py` enums: validate all enum members, string values, uniqueness
- [x] 4.3 Test Shapely geometry construction: `shapely.geometry.box(minx, miny, maxx, maxy)` para bbox geometry, `shapely.wkt.dumps()`/`loads()` round-trip, `MultiPolygon` from WKT, `Polygon` for footprint_geometry
- [x] 4.4 Run existing M2 unit tests: verify no regression from domain model additions (117 passed, 0 failures)

## Phase 5: Repository Implementations

- [x] 5.1 Create `src/geospatial/infrastructure/persistence/regions_repo.py`: `RegionRepositoryImpl` with lazy `@property conn()`, methods `save()`, `get_by_id()`, `find_intersecting_geometry(wkt)` (usa `ST_Intersects` en PostGIS)
- [x] 5.2 Create `src/geospatial/infrastructure/persistence/indicators_repo.py`: `IndicatorRepositoryImpl`, `save()`, `find_by_region(region_id)`
- [x] 5.3 Create `src/geospatial/infrastructure/persistence/risk_assessments_repo.py`: `RiskAssessmentRepositoryImpl`, `save()`, `find_by_region_and_date()`
- [x] 5.4 Create `src/geospatial/infrastructure/persistence/alerts_repo.py`: `AlertRepositoryImpl`, `save()`, `find_active_by_region()`
- [x] 5.5 Create `src/geospatial/infrastructure/persistence/economic_impacts_repo.py`: `EconomicImpactRepositoryImpl`, `save()`, `find_by_indicator()`
- [x] 5.6 Create `src/geospatial/infrastructure/persistence/data_sources_repo.py`: `DataSourceRepositoryImpl`, `get_by_code()`, `get_by_id()`
- [x] 5.7 Create `src/geospatial/infrastructure/persistence/audit_repo.py`: `AuditRepositoryImpl`, `log_event(audit_log)` — el repositorio falla normalmente (propaga excepción). La no-fatalidad se maneja ÚNICAMENTE en el orquestador (Phase 7), no en el repo
- [x] 5.8 All repos: use WKT serialization via `shapely.wkt.dumps(geom)` for geometry params, `cursor.execute()` with param binding

## Phase 6: Seeds & Data Lineage

- [x] 6.1 Create `seeds/002_geospatial_storage.sql`: idempotent seeds with `INSERT ... ON CONFLICT DO NOTHING/UPDATE`
- [x] 6.2 Update SMAP `data_source` record: set `config` JSONB metadata (spatial_resolution_m, temporal_resolution, native_crs), preserve existing `source_id` FK
- [x] 6.3 Insert pilot region (Chaco/Argentina): `name`, `geometry` WKT EPSG:4326 MultiPolygon, `region_type='administrative'`, `country='Argentina'`, `province='Chaco'`
- [x] 6.4 Skip: indicator types, risk types, alert severities son enums/CHECK constraints definidos en migración 003. No se seedean como datos — se definen como constantes en `domain/constants.py`
- [x] 6.5 Verify seed idempotency: execute twice without duplicates or errors

## Phase 7: Audit Integration in Orchestrator

- [x] 7.1 Inject `AuditRepository` into `src/geospatial/application/orchestrator.py` constructor
- [x] 7.2 Add audit event on pipeline start: `entity_type=PIPELINE_BATCH`, `action=START`, `actor_type=SYSTEM`
- [x] 7.3 Add audit event on pipeline complete: `action=COMPLETE`, include message with raw_file_id
- [x] 7.4 Add audit event on pipeline fail: `action=FAIL`, include error message
- [x] 7.5 Wrap all audit calls in `try/except`: log exception, never raise, pipeline continues

## Phase 8: Integration Tests

- [x] 8.1 Create `tests/geospatial/integration/test_postgis_storage.py`: test fixture with PostGIS container skip if unavailable
- [x] 8.2 Test PostGIS enabled: `SELECT PostGIS_Version()` returns version string
- [x] 8.3 Test `RegionRepository`: insert MultiPolygon EPSG:4326, query `find_intersecting_geometry()` with overlapping polygon, verify spatial query returns correct results
- [x] 8.4 Test FK constraints: insert `indicator` without `region_id` → assert `IntegrityError`
- [x] 8.5 Test `data_source_id` lineage: insert `processed_geospatial_layer` with `raw_file_id` → `raw_files.source_id` (FK existente a `data_sources.id`) resuelve el linaje vía JOIN directo, verificar `data_source_id` poblado. No hardcodeado a SMAP — cualquier source con FK funciona
- [x] 8.6 Test `footprint_geometry`: insert with and without geometry, verify nullable, `\di+` verify GIST index exists on `processed_geospatial_layers_footprint_geometry_idx`
- [x] 8.7 Test audit non-fatal: mock DB failure in `AuditRepository.log_event()` (repo propaga error), orchestrator catch en try/except, pipeline completes without error
- [x] 8.8 Test seeds idempotency: run seeds twice via `psql -f seeds/002_geospatial_storage.sql`, assert no duplicate rows via COUNT(*) = COUNT(DISTINCT ...) queries
- [x] 8.9 Test M2 regression: run existing M2 integration tests (`pytest tests/geospatial/integration/`), verify `bbox` preserved, processing pipeline unchanged

## Phase 9: Cleanup & Documentation

- [x] 9.1 Verify `bbox NUMERIC[]` still functional in `processed_geospatial_layers` (preserved from M2)
- [x] 9.2 Add docstrings to all repository classes: describe lazy connection pattern, WKT usage
- [x] 9.3 Update README or docs: document PostGIS dependency, migration 003, seed execution order
- [x] 9.4 Remove any temporary debug prints or TODO comments added during implementation
- [x] 9.5 Final verification with concrete commands:
  ```
  # Unit tests
  pytest tests/geospatial/unit/test_storage_models.py -v

  # Integration tests (requires Docker + PostGIS)
  pytest tests/geospatial/integration/test_postgis_storage.py -v

  # M2 regression - existing pipeline tests
  pytest tests/geospatial/integration/test_idempotency.py -v
  pytest tests/geospatial/integration/test_pipeline.py -v

  # Migration + seeds validation
  psql -U mse_user -d mse_platform -f migrations/003_add_postgis_and_models.sql
  psql -U mse_user -d mse_platform -f seeds/002_geospatial_storage.sql

  # PostGIS version check
  psql -U mse_user -d mse_platform -c "SELECT PostGIS_Version();"
  ```
