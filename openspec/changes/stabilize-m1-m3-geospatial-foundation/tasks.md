# Tasks: stabilize-m1-m3-geospatial-foundation

## Review Workload Forecast

- **Estimated changed lines**: ~150-200 (spread across 11-13 files, most changes are 1-3 lines)
- **New files**: 1 (`connection.py`)
- **400-line budget risk**: Low
- **Chained PRs recommended**: No — single atomic change, all tasks are dependents of each other

---

## Task 1: Extraer conexión PostgreSQL a módulo compartido (A1)

**Files to create/modify:**
- `src/geospatial/infrastructure/persistence/connection.py` — CREAR
- `src/geospatial/infrastructure/persistence/postgres_repositories.py` — MODIFICAR
- `src/geospatial/infrastructure/persistence/regions_repo.py` — MODIFICAR
- `src/geospatial/infrastructure/persistence/data_sources_repo.py` — MODIFICAR
- `src/geospatial/infrastructure/persistence/indicators_repo.py` — MODIFICAR
- `src/geospatial/infrastructure/persistence/risk_assessments_repo.py` — MODIFICAR
- `src/geospatial/infrastructure/persistence/alerts_repo.py` — MODIFICAR
- `src/geospatial/infrastructure/persistence/economic_impacts_repo.py` — MODIFICAR
- `src/geospatial/infrastructure/persistence/audit_repo.py` — MODIFICAR

**Changes:**
1. Crear `connection.py` con `get_connection()` (pública, mismo cuerpo que `_get_connection()` actual).
2. En `postgres_repositories.py`: eliminar `def _get_connection()`, agregar `from ...connection import get_connection as _get_connection`.
3. En 7 M3 repos: cambiar import de `postgres_repositories._get_connection` a `connection.get_connection`.

**Verification:**
- [ ] `connection.py` existe y `get_connection()` retorna una conexión psycopg2.
- [ ] `postgres_repositories.py` no define `_get_connection()` pero lo importa como alias.
- [ ] Los 7 M3 repos importan desde `connection.py`.
- [ ] `python -c "from src.geospatial.infrastructure.persistence.connection import get_connection; print('OK')"` funciona.
- [ ] `python -c "from src.geospatial.infrastructure.persistence.postgres_repositories import _get_connection; print('OK')"` funciona (compatibilidad).

---

## Task 2: Propagar data_source_id en ProcessedLayer (C2)

**Files to modify:**
- `src/geospatial/application/orchestrator.py`
- `src/geospatial/infrastructure/persistence/postgres_repositories.py`

**Changes in orchestrator.py:**
1. En `_process_single_file()`, extraer `data_source_id` de `raw_file.get("source_id")`.
2. Pasar `data_source_id=data_source_id` al constructor de `ProcessedLayer`.
3. Agregar método privado `_build_footprint_geometry(bounds, crs)` que retorna `Optional[Polygon]`.

**Changes in postgres_repositories.py (ProcessedLayerRepositoryImpl):**
4. Agregar `data_source_id` y `footprint_geometry` al INSERT.
5. Para `footprint_geometry`, usar `ST_GeomFromText(wkt, 4326)`.
6. Actualizar `get_by_raw_file_and_variable()` para poblar ambos campos en el `ProcessedLayer` retornado.

**Verification:**
- [ ] `ProcessedLayerRepositoryImpl.insert()` incluye ambas columnas en SQL.
- [ ] `data_source_id` se propaga desde `raw_file["source_id"]`.
- [ ] `_build_footprint_geometry()` construye Polygon 4326 válido cuando es posible.
- [ ] `_build_footprint_geometry()` retorna NULL si CRS no es transformable.
- [ ] `get_by_raw_file_and_variable()` devuelve ambos campos.

---

## Task 3: Corregir fallback nodata_value en GeoTIFFWriter (C1)

**Files to modify:**
- `src/geospatial/infrastructure/raster/geotiff_writer.py`

**Changes:**
1. Reemplazar línea 161 (hasattr) por `effective_nodata = nodata_value`.

**Verification:**
- [ ] `hasattr(metadata, 'nodata_value')` no aparece en el archivo.
- [ ] El flujo actual (orquestador pasa `nodata_value=extracted.nodata_value`) sigue funcionando.
- [ ] Si `nodata_value` es explícito, se escribe en el GeoTIFF.
- [ ] Si `nodata_value` es None, el GeoTIFF no tiene metadata nodata.

---

## Task 4: Corregir autoasignación en smap_reader.py (C3)

**Files to modify:**
- `src/geospatial/infrastructure/hdf5/smap_reader.py`

**Changes:**
1. Cambiar `y_coords = y_coords` por `y_1d = y_coords` en `_build_transform_from_coords()`.

**Verification:**
- [ ] `y_coords = y_coords` no aparece en el archivo.
- [ ] Coordenadas 1D se asignan correctamente a `y_1d`.
- [ ] Coordenadas 2D siguen extrayendo primera columna.

---

## Task 5: Agregar flag --metadata-backend al CLI (A2)

**Files to modify:**
- `src/jobs/run_smap_ingestion.py`
- `src/jobs/job_manager.py`

**Changes in run_smap_ingestion.py:**
1. Agregar argumento `--metadata-backend` con `choices=["json", "postgresql"]`, `default="json"`.
2. Pasar `metadata_backend` al `JobManager`.

**Changes in job_manager.py:**
3. `__init__()` acepta `metadata_backend: str = "json"`.
4. Si `"postgresql"`, instancia `PostgreSQLMetadataRepository`.
5. Si falla import (psycopg2), mostrar error claro.

**Verification:**
- [ ] `python -m src.jobs.run_smap_ingestion --help` muestra `--metadata-backend`.
- [ ] Default `json` no cambia comportamiento actual.
- [ ] `--metadata-backend postgresql` intenta usar PostgreSQLMetadataRepository.
- [ ] Error si psycopg2 no está instalado y se pide postgresql.

---

## Task 6: Separar sources.yaml (A3, evaluar e implementar si es simple)

**Files to potentially create/modify:**
- `src/config/geospatial-sources.yaml` — CREAR (si aplica)
- `src/config/config_loader.py` — MODIFICAR (si aplica)
- `src/config/sources.yaml` — MODIFICAR (quitar geospatial:)

**Evaluation gate:**
1. Revisar `config_loader.py` — si la carga es simple (yaml.safe_load), proceder.
2. Si hay lógica compleja de validación/pydantic sobre `geospatial:`, NO separar.

**If simple:**
3. Crear `geospatial-sources.yaml` con el contenido de `geospatial:`.
4. Agregar `load_geospatial_config()` en `config_loader.py`.
5. Actualizar CLI `process_smap.py` para cargar geospatial config desde el nuevo archivo.

**If complex:**
3. Documentar en `debt.md` o en el archive-report como deuda técnica.

**Verification (if implemented):**
- [ ] `geospatial-sources.yaml` existe con la sección `geospatial:` correcta.
- [ ] `sources.yaml` ya no tiene `geospatial:`.
- [ ] `config_loader.py` carga ambos archivos.
- [ ] `process_smap.py` y orquestador funcionan sin cambios en el pipeline.
- [ ] Tests existentes de config pasan.

---

## Task 7: Verificación final

**Actions:**
1. Type checking: `mypy src/` si está configurado.
2. Lint: `ruff check src/` si está configurado.
3. Tests unitarios: ejecutar suite completa.
4. Tests de integración (si PostgreSQL disponible).
5. Verificar que imports no están rotos.

**Success criteria:**
- [ ] Todos los tests pasan (unitarios + integración disponibles).
- [ ] No hay errores de import.
- [ ] `data_source_id` y `footprint_geometry` se persisten correctamente.
- [ ] nodada se escribe en GeoTIFF.
- [ ] `_get_connection()` sigue siendo accesible desde `postgres_repositories.py`.
