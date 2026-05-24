# Design: stabilize-m1-m3-geospatial-foundation

## Overview

Correcciones puntuales de estabilización en 5 áreas, sin agregar nuevas capacidades.
Cada issue tiene un cambio acotado, verificable de forma independiente.

---

## D1 — Conexión PostgreSQL compartida (A1)

### Current State
`_get_connection()` es una función privada definida en `postgres_repositories.py` (Módulo 2).
7 repos de Módulo 3 la importan como símbolo privado:
```python
from src.geospatial.infrastructure.persistence.postgres_repositories import _get_connection
```

### Design
1. Crear `src/geospatial/infrastructure/persistence/connection.py` con `get_connection()` (pública).
2. En `postgres_repositories.py`:
   - Eliminar la definición de `_get_connection()`.
   - Agregar: `from src.geospatial.infrastructure.persistence.connection import get_connection as _get_connection`.
   - Los 3 repos en ese archivo (`RawFileDiscoveryRepositoryImpl`, `GeospatialProcessingJobRepositoryImpl`, `ProcessedLayerRepositoryImpl`) siguen usando `_get_connection()` internamente sin cambios.
3. En cada M3 repo, cambiar el import a:
   ```python
   from src.geospatial.infrastructure.persistence.connection import get_connection
   ```
4. `connection.py` no tiene dependencias del proyecto — solo `psycopg2` (misma precondición).

### Compatibility
- `_get_connection` se mantiene como alias en `postgres_repositories.py`.
- Cualquier código que importe `from postgres_repositories import _get_connection` SEGUIRÁ funcionando.
- La firma, comportamiento y variables de entorno son idénticas.

---

## D2 — Persistencia de processed_geospatial_layers (C2)

### data_source_id

**Source of truth**: `raw_file["source_id"]`.

El `RawFileDiscoveryRepositoryImpl.find_completed()` y `find_by_id()` hacen `SELECT rf.*`, que incluye `rf.source_id`. Este es el FK directo a `data_sources.id`.

En el orquestador (`_process_single_file`), el `raw_file` dict ya está disponible. Solo hay que propagarlo al `ProcessedLayer`:

```python
data_source_id = raw_file.get("source_id")  # int | None

layer = ProcessedLayer(
    ...
    data_source_id=data_source_id,
    ...
)
```

Si `source_id` no está presente (borde: raw_file sin source), se deja NULL y se loguea un warning.

### footprint_geometry

**Estrategia**: Construir Polygon en EPSG:4326 desde los bounds del raster cuando sea seguro.

La información necesaria está en `raster_result.metadata`:
- `bounds`: `(minx, miny, maxx, maxy)` en CRS nativo
- `crs`: string como `"EPSG:6933"`

#### Algoritmo

```
footprint_geometry = try_build_footprint(bounds, crs)

donde try_build_footprint:
1. Si no hay shapely o pyproj → return None
2. Si no hay bounds o crs → return None
3. Crear Polygon desde los 4 vértices del bbox
4. Transformar cada vértice de CRS_nativo → EPSG:4326 via pyproj.Transformer
5. Si la transformación falla → log warning, return None
6. Si el resultado es válido → return Polygon en EPSG:4326
```

**Ubicación**: Método privado `_build_footprint_geometry()` en `GeospatialOrchestrator`.

Se llama justo antes de construir el `ProcessedLayer`:

```python
footprint = self._build_footprint_geometry(
    raster_result.metadata.bounds,
    raster_result.metadata.crs
)

layer = ProcessedLayer(
    ...
    footprint_geometry=footprint,
    data_source_id=data_source_id,
    ...
)
```

**Por qué en el orquestador y no en el repo**: El orquestador tiene toda la información (bounds, crs) y dependencies (shapely/pyproj). El repo solo persiste. Cohesión: la transformación de coordenadas es lógica de aplicación, no de infraestructura.

#### Casos borde

| Situación | Resultado |
|---|---|
| CRS nativo = EPSG:4326 | Mismo Polygon, sin transformación |
| CRS nativo transformable (EPSG:6933) | Polygon transformado a 4326 |
| CRS nulo o vacío | NULL + warning |
| shapely/pyproj no instalados | NULL (compatible con entorno mínimo) |
| Transformación falla | NULL + warning |

### INSERT actualizado

```sql
INSERT INTO processed_geospatial_layers (
    ..., -- existing columns
    data_source_id,
    footprint_geometry
) VALUES (
    ..., -- existing values
    %s,
    ST_GeomFromText(%s, 4326)
)
```

Para `footprint_geometry`, usamos `ST_GeomFromText(wkt_string, 4326)`.

Si `footprint_geometry` es None, se pasa NULL directamente.

### SELECT actualizado

`get_by_raw_file_and_variable()` ya usa `SELECT *` — las columnas nuevas se obtienen automáticamente.
Solo hay que agregar los campos al constructor de `ProcessedLayer`:

```python
return ProcessedLayer(
    ...
    data_source_id=row.get("data_source_id"),
    footprint_geometry=row.get("footprint_geometry"),  # shapely.wkt.loads si es WKT
)
```

---

## D3 — fallback nodata_value en GeoTIFFWriter (C1)

### Current State
Línea 161 de `geotiff_writer.py`:
```python
effective_nodata = nodata_value if nodata_value is not None else metadata.nodata_value if hasattr(metadata, 'nodata_value') else None
```

`GeospatialMetadata` no tiene `nodata_value`, así que `hasattr` siempre da False → `effective_nodata = None`. El orquestador SIEMPRE pasa `nodata_value=extracted.nodata_value`, así que este camino nunca se ejecuta.

### Design
Simplificar a:
```python
effective_nodata = nodata_value
```

El método `write()` recibe `nodata_value: float | None = None`. Si es None, no se agrega nodata al perfil del GeoTIFF (líneas 193-194 existentes: `if effective_nodata is not None: profile["nodata"] = effective_nodata`).

### Verification
Test unitario que:
1. Crea un `GeoTIFFWriter` y llama `write()` con datos de prueba y `nodata_value=-9999.0`.
2. Lee el GeoTIFF resultante con rasterio y verifica que `src.nodata == -9999.0`.
3. Llama `write()` sin `nodata_value` y verifica que `src.nodata` es None/0.

---

## D4 — Autoasignación muerta en smap_reader.py (C3)

### Current State
```python
if y_coords.ndim == 2:
    y_1d = y_coords[:, 0]
else:
    y_coords = y_coords  # dead
    y_1d = y_coords      # correct by accident
```

### Design
```python
if y_coords.ndim == 2:
    y_1d = y_coords[:, 0]
else:
    y_1d = y_coords
```

Cambio de UNA línea. Funcionalmente idéntico.

---

## D5 — Flag --metadata-backend (A2)

### Design
1. En `run_smap_ingestion.py`:
   - Agregar `--metadata-backend` con choices `["json", "postgresql"]`, default `"json"`.
2. En `job_manager.py`:
   - `JobManager.__init__()` acepta `metadata_backend: str = "json"`.
   - Si `metadata_backend == "postgresql"`, instancia `PostgreSQLMetadataRepository` en vez de `MetadataRepository`.
   - Si la importación falla (psycopg2 no instalado), error claro.
3. En `run_smap_ingestion.py`:
   - Pasa `metadata_backend=args.metadata_backend` al `JobManager`.

### Dependencies
- `PostgreSQLMetadataRepository` ya existe en `src/storage/metadata_repository_pg.py`.
- `psycopg2` ya es dependencia opcional del proyecto.

---

## D6 — Separación de sources.yaml (A3, evaluar)

### Evaluación
Actualmente `sources.yaml`:
```yaml
sources:
  smap: ...
geospatial:
  variables: ...
  roi: ...
```

`config_loader.py` carga el archivo completo y expone:
- `config.get_smap_config()` → lee `sources.smap`
- `config.geospatial` → se usa como dict en el orquestador

Para separar:
1. Crear `src/config/geospatial-sources.yaml` con el contenido de `geospatial:`.
2. En `config_loader.py`, agregar carga del segundo archivo.
3. El orquestador (`cli/process_smap.py`) carga config y accede a `config.geospatial`.

**Impacto**: Bajo. `config_loader.py` ya usa `yaml.safe_load()` — cargar dos archivos es trivial.

**Decisión**: Si el cambio es solo agregar `load_geospatial_config()` y modificar el CLI para pasarlo, HACERLO. Si toca refactor del `SourcesConfig` dataclass, DEJARLO.

---

## Sequence: Pipeline completo con correcciones

```
CLI (process_smap.py)
  │
  ├── Load geospatial config (from sources.yaml OR geospatial-sources.yaml)
  │
  ├── GeospatialOrchestrator.run_batch()
  │     │
  │     ├── For each raw_file:
  │     │     ├── Read HDF5 (SMAPHDF5Reader)
  │     │     ├── Validate (SMAPValidationService)
  │     │     ├── Process raster (RasterProcessingService)
  │     │     ├── Write GeoTIFF (GeoTIFFWriter) ─── nodada_value explícito
  │     │     ├── Build footprint (desde bounds + CRS) ← NUEVO
  │     │     ├── data_source_id = raw_file["source_id"] ← NUEVO
  │     │     └── Persist layer (ProcessedLayerRepositoryImpl) ← INSERT completo
  │     │
  │     └── Return batch results
  │
  └── Done
```

## Archivos modificados/creados

| Archivo | Acción | Issue |
|---|---|---|
| `src/geospatial/infrastructure/persistence/connection.py` | **CREAR** | A1 |
| `src/geospatial/infrastructure/persistence/postgres_repositories.py` | MODIFICAR (import) | A1, C2 |
| `src/geospatial/infrastructure/persistence/regions_repo.py` | MODIFICAR (import) | A1 |
| `src/geospatial/infrastructure/persistence/data_sources_repo.py` | MODIFICAR (import) | A1 |
| `src/geospatial/infrastructure/persistence/indicators_repo.py` | MODIFICAR (import) | A1 |
| `src/geospatial/infrastructure/persistence/risk_assessments_repo.py` | MODIFICAR (import) | A1 |
| `src/geospatial/infrastructure/persistence/alerts_repo.py` | MODIFICAR (import) | A1 |
| `src/geospatial/infrastructure/persistence/economic_impacts_repo.py` | MODIFICAR (import) | A1 |
| `src/geospatial/infrastructure/persistence/audit_repo.py` | MODIFICAR (import) | A1 |
| `src/geospatial/application/orchestrator.py` | MODIFICAR (data_source_id + footprint) | C2 |
| `src/geospatial/infrastructure/raster/geotiff_writer.py` | MODIFICAR (1 línea) | C1 |
| `src/geospatial/infrastructure/hdf5/smap_reader.py` | MODIFICAR (1 línea) | C3 |
| `src/jobs/run_smap_ingestion.py` | MODIFICAR (flag) | A2 |
| `src/jobs/job_manager.py` | MODIFICAR (backend param) | A2 |
| `src/config/config_loader.py` | POSIBLEMENTE (carga dual) | A3 |
| `src/config/geospatial-sources.yaml` | POSIBLEMENTE CREAR | A3 |

Total: 1 new file + 10-12 modified files. Cambios mínimos por archivo.

## Riesgos técnicos

| Decisión | Riesgo | Mitigación |
|---|---|---|
| `_get_connection` como alias | Alguien importa de la ubicación antigua con nombre privado | Mantener alias es compatible |
| `raw_file["source_id"]` como data_source_id | `raw_file` dict no tiene la columna para ciertos raw_files | Usar `.get("source_id")` con fallback NULL + warning |
| `_build_footprint_geometry` en orchestrator | Aumenta responsabilidad del orquestador | Es un helper privado, no cambia interfaz pública |
| shapely/pyproj son opcionales | footprint_geometry siempre NULL si no están instalados | Comportamiento esperado, misma condición que ROI clipping |
