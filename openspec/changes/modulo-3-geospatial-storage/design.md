# Design: Módulo 3 - Geospatial Storage

## Technical Approach

Implement a PostGIS-enabled centralized geospatial model. Execution in 2 slices:
1. **Slice 1**: Docker image → `postgis/postgis:15-3.4`, migration `003_add_postgis_and_models.sql` (PostGIS + nuevas tablas + `footprint_geometry`), domain models + constants + interfaces.
2. **Slice 2**: 7 repositorios divididos, seeds idempotentes, tests completos, audit logging no invasivo en orquestador.

Todas las entidades nuevas se implementan en Slice 1 (modelos) y Slice 2 (repos). Ninguna queda fuera del alcance.

## Architecture Decisions

### Decision: Full Repository Division (7 repos)
**Choice**: Crear un repositorio por entidad: `RegionRepository`, `IndicatorRepository`, `RiskAssessmentRepository`, `AlertRepository`, `EconomicImpactRepository`, `DataSourceRepository`, `AuditRepository`.
**Alternatives considered**: Un solo archivo `postgres_repositories.py` para todo.
**Rationale**: SRP, mantenibilidad, alineado con el tamaño del cambio. Los repos existentes (`RawFileDiscoveryRepository`, `GeospatialProcessingJobRepository`, `ProcessedLayerRepository`) se mantienen en `postgres_repositories.py` sin migrar.

### Decision: Model Location
**Choice**: Agregar nuevas dataclasses al `domain/models.py` existente.
**Alternatives considered**: Nuevo `storage_models.py`.
**Rationale**: El archivo actual (~140 líneas) puede extenderse sin saturarse. Mantiene el límite del dominio unificado.

### Decision: Geometry Representation in Domain
**Choice**: Usar `shapely.geometry.MultiPolygon` y `shapely.wkt` para representación de geometrías en las dataclasses del dominio. Shapely ya es dependencia del proyecto (usada en `raster_processing_service.py`).
**Alternatives considered**: GeoJSON dicts, WKT strings crudos, objetos PostGIS.
**Rationale**: Shapely ya existe como dependencia. Permite validación espacial, reproyección y serialización WKT/GeoJSON sin acoplar el dominio a psycopg2.

### Decision: data_source_id Strategy
**Choice**: Nuevos registros: `data_source_id` se resuelve desde el `raw_file.source_id` (relación existente) y se guarda obligatoriamente. Registros existentes: columna nullable por migración, sin backfill obligatorio.
**Alternatives considered**: Backfill obligatorio, columna NOT NULL desde el inicio.
**Rationale**: Compatibilidad con M2. `raw_files` ya tiene FK hacia `data_sources` (campo `source_id`), por lo que el linaje es resoluble sin nuevas consultas.

### Decision: footprint_geometry — Schema vs Population
**Choice**: La columna `footprint_geometry GEOMETRY(Polygon, 4326)` + GIST index forman parte del schema. La población es OPTIONAL: se intenta solo cuando el CRS nativo del raster es conocido y la transformación a EPSG:4326 es técnicamente segura (validar datum, no proyección global).
**Alternatives considered**: Población obligatoria al insertar, columna NOT NULL.
**Rationale**: No todos los rasters tienen CRS transformable. El `bbox NUMERIC[]` sigue siendo el campo de referencia para bounds nativos.

### Decision: Connection Handling
**Choice**: Retener el patrón lazy `@property def conn(self)` por repositorio (consistente con postgres_repositories.py existente).
**Alternatives considered**: Unit of Work, connection pool centralizado.
**Rationale**: Consistencia con el código actual. Refactorizar el patrón de conexión está fuera del alcance del M3.

### Decision: Audit Logging Strategy
**Choice**: Enums centralizados en `domain/constants.py` para `EntityType`, `Action` y `ActorType`. En orquestador, wrapper `try/except` que registra el error pero nunca rompe el pipeline.
**Alternatives considered**: Strings dispersos, auditoría como fallo crítico.
**Rationale**: Audit es observabilidad, no lógica de negocio. Los enums evitan strings mágicos.

### Decision: DB Migration
**Choice**: Migración única transaccional `003_add_postgis_and_models.sql`. NO destructiva: preserva `bbox NUMERIC[]`, deja `footprint_geometry` y `data_source_id` como NULLables, no elimina columnas existentes.
**Alternatives considered**: Múltiples migraciones por entidad.
**Rationale**: Rollback simple, versionado único para este cambio.

### Decision: SMAP-independence for footprint_geometry
**Choice**: La lógica de generación de `footprint_geometry` lee el CRS nativo desde el campo `crs` del registro — no está hardcodeada a SMAP ni a EPSG:6933.
**Alternatives considered**: Transformación fija EPSG:6933 → 4326.
**Rationale**: Cualquier fuente futura (SAOCOM, Sentinel, CHIRPS) con CRS conocido podrá generar su `footprint_geometry` sin cambios de código.

## Data Flow

```
Pipeline (genérico, no solo SMAP)
  → ProcessedLayer generado
  → Si crs conocido y transformable: footprint_geometry derivado (EPSG:4326)
  → data_source_id resuelto via raw_file.source_id
  → Persistencia en processed_geospatial_layers (bbox intacto, footprint_geometry nullable)

Eventos pipeline (start, complete, fail)
  → AuditRepository.log_event() vía try/except
  → Fallo de audit: log + continue, nunca rompe pipeline
  → entity_type/action/actor_type desde enums centralizados
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `docker-compose.yml` | Modify | Update to `postgis/postgis:15-3.4` (validado en Docker Hub, compatible con volumen PG15 existente). |
| `migrations/003_add_postgis_and_models.sql` | Create | `CREATE EXTENSION IF NOT EXISTS postgis`, tablas nuevas (`regions`, `indicators`, `risk_assessments`, `alerts`, `economic_impacts`, `audit_logs`), `footprint_geometry GEOMETRY(Polygon,4326)` nullable + GIST, `data_source_id` nullable FK, constraints, índices. |
| `seeds/002_geospatial_storage.sql` | Create | Seeds idempotentes: SMAP source update, región piloto, tipos base. |
| `src/geospatial/domain/models.py` | Modify | Agregar: `Region`, `Indicator`, `RiskAssessment`, `Alert`, `EconomicImpact`, `AuditLog`, extender `ProcessedLayer` (opcional `footprint_geometry`), extender `DataSource` si aplica. |
| `src/geospatial/domain/constants.py` | Create | Enums: `EntityType`, `Action`, `ActorType`, `RiskType`, `RiskLevel`, `Severity`, `AlertStatus`, `RegionType`. |
| `src/geospatial/domain/interfaces.py` | Modify | Agregar ABCs: `RegionRepository`, `IndicatorRepository`, `RiskAssessmentRepository`, `AlertRepository`, `EconomicImpactRepository`, `DataSourceRepository`, `AuditRepository`. |
| `src/geospatial/infrastructure/persistence/regions_repo.py` | Create | `RegionRepositoryImpl`. |
| `src/geospatial/infrastructure/persistence/indicators_repo.py` | Create | `IndicatorRepositoryImpl`. |
| `src/geospatial/infrastructure/persistence/risk_assessments_repo.py` | Create | `RiskAssessmentRepositoryImpl`. |
| `src/geospatial/infrastructure/persistence/alerts_repo.py` | Create | `AlertRepositoryImpl`. |
| `src/geospatial/infrastructure/persistence/economic_impacts_repo.py` | Create | `EconomicImpactRepositoryImpl`. |
| `src/geospatial/infrastructure/persistence/data_sources_repo.py` | Create | `DataSourceRepositoryImpl` (extiende funcionalidad de data_sources existente). |
| `src/geospatial/infrastructure/persistence/audit_repo.py` | Create | `AuditRepositoryImpl`. |
| `src/geospatial/application/orchestrator.py` | Modify | Inyectar `AuditRepository`, emitir eventos start/complete/fail con enums centralizados, catch failures sin romper pipeline. |

## Interfaces / Contracts

```python
# Geometrías: shapely.geometry.MultiPolygon en dominio, WKT para PostgreSQL

class RegionRepository(ABC):
    @abstractmethod
    def save(self, region: Region) -> int: ...
    @abstractmethod
    def get_by_id(self, region_id: int) -> Region | None: ...
    @abstractmethod
    def find_by_geometry(self, polygon_wkt: str) -> list[Region]: ...

class IndicatorRepository(ABC):
    @abstractmethod
    def save(self, indicator: Indicator) -> int: ...
    @abstractmethod
    def find_by_region(self, region_id: int) -> list[Indicator]: ...

class RiskAssessmentRepository(ABC):
    @abstractmethod
    def save(self, assessment: RiskAssessment) -> int: ...

class AlertRepository(ABC):
    @abstractmethod
    def save(self, alert: Alert) -> int: ...

class EconomicImpactRepository(ABC):
    @abstractmethod
    def save(self, impact: EconomicImpact) -> int: ...

class DataSourceRepository(ABC):
    @abstractmethod
    def get_by_code(self, code: str) -> DataSource | None: ...

class AuditRepository(ABC):
    @abstractmethod
    def log_event(self, log: AuditLog) -> None: ...
```

Todos los métodos concretos usan psycopg2 + shapely.wkt para geometrías, siguiendo el patrón lazy connection existente.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Domain models & constants | Validar dataclasses, enums, constraints. Shapely geometry construction. |
| Integration | PostGIS habilitado | `SELECT PostGIS_Version()` retorna versión. |
| Integration | Regions CRUD + GIST | Insertar MultiPolygon EPSG:4326, consultar por solapamiento espacial. |
| Integration | FKs evitan huérfanos | Intentar insertar indicator sin region → violación FK. |
| Integration | data_source_id lineage | Nuevo registro con raw_file.source_id resoluble → data_source_id poblado. |
| Integration | footprint_geometry | Insert con y sin geometría, verificar GIST index usage. |
| Integration | Audit non-fatal | Mock DB failure en AuditRepository, pipeline completa sin error. |
| Integration | Seeds idempotentes | Ejecutar seeds 2 veces sin duplicados. |
| Regression | M2 compatibilidad | Tests existentes de idempotencia y pipeline siguen pasando. |
| Regression | bbox preservado | Insert en processed_geospatial_layers sin footprint_geometry → bbox funciona. |

## Migration / Rollout

1. **Docker**: Cambiar imagen a `postgis/postgis:15-3.4`. La imagen postgis extiende la oficial de PG15, el volumen de datos es compatible (misma versión major de PostgreSQL). Hacer backup del volumen antes.
2. **Migración 003**: `CREATE EXTENSION IF NOT EXISTS postgis`, nuevas tablas, alter de `processed_geospatial_layers` (ADD COLUMN `footprint_geometry` nullable + GIST, ADD COLUMN `data_source_id` nullable + FK). Todo en transacción única.
3. **Rollback**: `DROP TABLE ... CASCADE`, `DROP EXTENSION IF EXISTS postgis`, revertir docker-compose.yml a `postgres:15-alpine`.
4. **data_source_id**: Migración add column nullable. Nuevos registros lo pueblan, existentes quedan NULL.
5. **footprint_geometry**: Nullable siempre. Sin backfill. Población condicional cuando CRS conocido y transformable.

## Open Questions / Decisiones Cerradas

- [x] **Imagen Docker**: `postgis/postgis:15-3.4` — validado, mismo PG15, volumen compatible.
- [x] **data_source_id nullability**: NULL para existentes, obligatorio para nuevos cuando linaje resoluble.
- [x] **Alcance repositorios**: 7 repos nuevos (regions, indicators, risk_assessments, alerts, economic_impacts, data_sources, audit). Ninguno se queda fuera.
- [x] **Geometría en dominio**: `shapely.geometry.MultiPolygon` en dataclasses, WKT para serialización DB. Shapely ya es dependencia.
- [ ] **PostGIS no disponible en CI**: ¿usar skip condicional como con earthdata? Decidir en implementación.
- [ ] **data_source_id resolución**: ¿vía JOIN directo en query o lookup separado? Pendiente de diseño fino en apply.
