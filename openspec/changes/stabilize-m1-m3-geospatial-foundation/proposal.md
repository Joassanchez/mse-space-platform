# Proposal: stabilize-m1-m3-geospatial-foundation

## Intent

Estabilizar la base técnica de los Módulos 1, 2 y 3 corrigiendo bugs reales y deuda arquitectónica barata detectada en la auditoría de código, sin agregar nuevas capacidades ni refactors grandes.

## Scope

### In Scope

1. **C2 — Persistencia completa de `processed_geospatial_layers`**
   - Corregir `ProcessedLayerRepositoryImpl.insert()` para persistir `data_source_id` y `footprint_geometry`.
   - Propagar `data_source_id` desde el raw_file/config hasta el `ProcessedLayer`.
   - Construir `footprint_geometry` en EPSG:4326 solo cuando sea técnicamente seguro; dejar NULL si no.
   - Actualizar `get_by_raw_file_and_variable()` para devolver ambos campos.

2. **C1 — Fallback incorrecto de nodata_value en GeoTIFFWriter**
   - Eliminar el `hasattr(metadata, 'nodata_value')` que nunca funciona (`GeospatialMetadata` no tiene ese campo).
     El `nodata_value` siempre se pasa explícitamente desde el orquestador.
   - Agregar test que verifique que el nodata se escribe correctamente en el GeoTIFF.

3. **C3 — Autoasignación muerta en `smap_reader.py`**
   - Reemplazar `y_coords = y_coords` por `y_1d = y_coords` en `_build_transform_from_coords()`.
   - Verificar que el manejo de coordenadas 1D sigue funcionando igual.

4. **A1 — Acoplamiento de `_get_connection()` privado entre módulos**
   - Extraer la conexión PostgreSQL a un módulo/helper compartido (`src/geospatial/infrastructure/persistence/connection.py`).
   - Actualizar los 7 repos de Módulo 3 (`regions_repo.py`, `data_sources_repo.py`, `indicators_repo.py`,
     `risk_assessments_repo.py`, `alerts_repo.py`, `economic_impacts_repo.py`, `audit_repo.py`) más los 3 repos
     de `postgres_repositories.py` para importar desde el nuevo módulo compartido.
   - Mantener compatibilidad total: `_get_connection()` sigue siendo el mismo código, solo cambia su ubicación.

5. **A2 — Selección de backend de metadata (JSON vs PostgreSQL)**
   - Agregar flag `--metadata-backend` al CLI `run_smap_ingestion.py` (valores: `json` | `postgresql`).
   - Default: `json` (no rompe desarrollo local).
   - Documentar en el CLI help que `postgresql` debe usarse en producción multi-instancia.

6. **A3 — Separación de `sources.yaml` (si es simple)**
   - Evaluar durante implementación. Si separar las secciones `sources:` y `geospatial:` en archivos separados
     no rompe loaders ni documentación, hacerlo. Si requiere cambios amplios en `config_loader.py`, dejarlo fuera.

### Out of Scope

- **A4 — `self._variable_configs[0]`**: Depende de soporte multi-variable, fuera del alcance de estabilización.
- **A5 — `SMAPValidationService` en application/**: Violación Clean Architecture teórica sin impacto funcional.
- Módulo 4 (dashboard, backend, IA agents).
- Refactors grandes fuera de los issues listados.
- Nuevas capacidades o features.

## Capabilities

> Contract between proposal and specs phases.

### Modified Capabilities

| Capability | Change |
|---|---|
| `geospatial-persistence` | INSERT completo con `data_source_id` y `footprint_geometry`; helper de conexión compartido |
| `geotiff-writing` | Nodata value escrito correctamente en GeoTIFF |
| `hdf5-reading` | Coordenadas 1D manejadas sin código muerto |
| `smap-ingestion` | Flag `--metadata-backend` para elegir JSON o PostgreSQL |
| `config` | Posible separación de `sources.yaml` en archivos por dominio |

## Approach

### Slice 1 — Persistencia (C2 + conexión compartida A1)
1. Crear `connection.py` con `get_connection()` (público, misma implementación).
2. Actualizar `postgres_repositories.py` para importar desde el helper.
3. Actualizar los 7 repos de Módulo 3.
4. Agregar `data_source_id` y `footprint_geometry` al INSERT.
5. Propagar `data_source_id` desde el orquestador.
6. Construir `footprint_geometry` como EPSG:4326 Polygon desde el bbox.

### Slice 2 — Correcciones puntuales (C1 + C3)
7. Limpiar `hasattr` en `geotiff_writer.py`.
8. Corregir autoasignación en `smap_reader.py`.

### Slice 3 — Configuración (A2 + A3)
9. Agregar `--metadata-backend` a `run_smap_ingestion.py`.
10. Evaluar y posiblemente separar `sources.yaml`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/geospatial/infrastructure/persistence/connection.py` | **New** | Helper de conexión PostgreSQL compartido entre módulos |
| `src/geospatial/infrastructure/persistence/postgres_repositories.py` | Modified | Importar `get_connection` desde helper, no definir `_get_connection` localmente |
| `src/geospatial/infrastructure/persistence/regions_repo.py` | Modified | Importar `get_connection` desde helper |
| `src/geospatial/infrastructure/persistence/data_sources_repo.py` | Modified | Importar `get_connection` desde helper |
| `src/geospatial/infrastructure/persistence/indicators_repo.py` | Modified | Importar `get_connection` desde helper |
| `src/geospatial/infrastructure/persistence/risk_assessments_repo.py` | Modified | Importar `get_connection` desde helper |
| `src/geospatial/infrastructure/persistence/alerts_repo.py` | Modified | Importar `get_connection` desde helper |
| `src/geospatial/infrastructure/persistence/economic_impacts_repo.py` | Modified | Importar `get_connection` desde helper |
| `src/geospatial/infrastructure/persistence/audit_repo.py` | Modified | Importar `get_connection` desde helper |
| `src/geospatial/infrastructure/persistence/postgres_repositories.py` | Modified | INSERT con `data_source_id` y `footprint_geometry`; SELECT actualizado |
| `src/geospatial/application/orchestrator.py` | Modified | Pasar `data_source_id` al crear `ProcessedLayer` |
| `src/geospatial/infrastructure/raster/geotiff_writer.py` | Modified | Eliminar `hasattr` fallback muerto |
| `src/geospatial/infrastructure/hdf5/smap_reader.py` | Modified | Corregir autoasignación `y_coords = y_coords` |
| `src/jobs/run_smap_ingestion.py` | Modified | Agregar flag `--metadata-backend` |
| `src/jobs/job_manager.py` | Modified | Aceptar backend de metadata como parámetro |
| `src/config/sources.yaml` | **May be split** | Separar `sources:` y `geospatial:` si es simple |
| `src/config/config_loader.py` | **May be modified** | Si se separa `sources.yaml` |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Cambio de import en repos rompe imports existentes | Low | Mantener `_get_connection` como alias en `postgres_repositories.py` para compatibilidad |
| `footprint_geometry` incorrecto si CRS no es transformable a 4326 | Medium | Solo construir si CRS es conocido y transformable; si no, NULL explícito |
| `--metadata-backend` agrega complejidad innecesaria a la CLI | Low | Default `json` no rompe nada; flag simple, sin dependencias nuevas |
| Separar `sources.yaml` rompe `config_loader.py` | Medium | Solo separar si el cambio es superficial; si toca lógica de parsing, dejar para después |

## Rollback Plan

1. Revertir commits del cambio vía `git revert`.
2. Si se separó `sources.yaml`, restaurar el archivo original.
3. Si se creó `connection.py`, mantenerlo o eliminarlo según decisión post-revert.

## Dependencies

- Módulos 1, 2, 3 implementados y archivados.
- PostgreSQL + PostGIS operativos.
- Tests existentes pasando antes del cambio.

## Success Criteria

- [ ] `ProcessedLayerRepositoryImpl.insert()` persiste `data_source_id` y `footprint_geometry`.
- [ ] `data_source_id` se propaga correctamente desde raw_file/orchestrator.
- [ ] `footprint_geometry` se construye en EPSG:4326 cuando es seguro; NULL si no.
- [ ] `get_by_raw_file_and_variable()` devuelve ambos campos.
- [ ] `hasattr(metadata, 'nodata_value')` eliminado; nodata se pasa explícitamente.
- [ ] GeoTIFF generado incluye nodata en metadata.
- [ ] `y_coords = y_coords` corregido a `y_1d = y_coords`.
- [ ] Conexión PostgreSQL centralizada en `connection.py`, todos los repos la usan.
- [ ] `_get_connection()` mantenido como alias en `postgres_repositories.py` para compatibilidad.
- [ ] CLI `run_smap_ingestion.py` acepta `--metadata-backend json|postgresql`.
- [ ] `sources.yaml` separado (si es simple) o documentado como deuda si no.
- [ ] Tests unitarios y de integración pasan.
- [ ] Type checking y lint no introducen errores nuevos.
