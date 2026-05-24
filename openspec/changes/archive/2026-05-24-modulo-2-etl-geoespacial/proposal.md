 # Proposal: Módulo 2 — ETL Geoespacial SMAP

 ## Intent

 Transformar archivos SMAP HDF5 crudos (descargados en Módulo 1) en capas GeoTIFF georreferenciadas y validadas, listas para análisis territorial. El Módulo 1 dejó 64 tests passing y un HDF5 real de 138 MB, pero sin capacidad de extracción geoespacial.

 ## Scope

 ### In Scope
 - `SMAPHDF5Reader`: Lectura de grupos/datasets/atributos HDF5
 - `GeospatialValidationService`: Validación de estructura, variables, dimensiones y rangos
 - `RasterProcessingService`: Manejo de nodata (-9999.0), CRS candidato (EPSG:6933 EASE-Grid 2.0), transform espacial, ROI clipping (si la ROI está en EPSG:4326 y el raster en EASE-Grid, reproyectar geometría al CRS del raster antes de recortar)
 - `GeoTIFFWriter`: Escritura de raster con metadata completa (9 km resolución)
 - Tablas PostgreSQL: `geospatial_processing_jobs`, `processed_geospatial_layers` con idempotencia
 - `SMAPGeospatialService`: Orquestación del pipeline completo
 - CLI: `python -m src.geospatial.cli.process_smap`
 - Tests unitarios + integración con HDF5 real

 ### Out of Scope
 - Modelos de IA, alertas, dashboard (Módulos posteriores)
 - Fuentes adicionales (SAOCOM, NISAR, SMN, INDEC)
 - Cálculo de sequía o riesgo agroambiental
 - PostGIS (metadata en SQL plano es suficiente para MVP)

 ## Capabilities

 ### New Capabilities
 - `hdf5-reading`: Lectura y parsing de archivos SMAP HDF5 (grupos, datasets, atributos)
 - `geospatial-validation`: Validación de estructura HDF5, dimensiones, rangos y metadata mínima
 - `raster-processing`: Conversión de arrays científicos a raster geoespacial (CRS, transform, nodata, ROI)
 - `geotiff-writing`: Escritura de archivos GeoTIFF con metadata espacial completa
 - `geospatial-persistence`: Registro de jobs y capas procesadas en PostgreSQL con idempotencia

 ### Modified Capabilities
 - None

 ## Approach

 Arquitectura Clean/Hexagonal siguiendo patrones del Módulo 1. Pipeline secuencial:
 1. Identificar archivos `completed` en PostgreSQL
 2. Verificar idempotencia por `(raw_file_id, variable_name, processing_version)` — si ya existe, registrar job como `skipped` o retornar capa existente; no duplicar archivos ni registros, pero dejar trazabilidad del intento
 3. Leer HDF5 con `h5py` (evitando cargar datasets innecesarios; para MVP se permite cargar una variable completa si el tamaño es razonable)
 4. Validar estructura y extraer `sm_surface` (hallazgo inicial de exploración, validable por el reader/validator)
 5. Derivar CRS, transform, bounds, resolución y orientación del grid desde metadata HDF5 y documentación del producto SMAP; escribir GeoTIFF en `data/processed/smap/soil_moisture/YYYY/MM/`
 6. Registrar metadata + estadísticas en PostgreSQL

 Variable primaria candidata: `Geophysical_Data/sm_surface` (hallazgo inicial de exploración). Grid tentativo: 1624×3856, ~9 km. CRS candidato: EPSG:6933 (EASE-Grid 2.0 — Lambert Cylindrical Equal Area). El reader/validator debe contrastar estos parámetros contra el archivo real y la documentación del producto antes de usarlos como definitivos.

 ## Affected Areas

 | Area | Impact | Description |
 |------|--------|-------------|
 | `src/geospatial/` | New | Nuevo módulo geoespacial (domain/, application/, infrastructure/, cli/) |
 | `src/core/db/postgresql.py` | Modified | Extender conexión para nuevas tablas |
 | `migrations/002_create_tables.sql` | New | Tablas `geospatial_processing_jobs`, `processed_geospatial_layers` |
 | `requirements.txt` | Modified | Agregar `rasterio` (rioxarray queda opcional, solo si se justifica para clipping/reproyección) |
 | `data/processed/smap/` | New | Output directory para GeoTIFFs |
 | `tests/geospatial/` | New | Tests unitarios + integración |

 ## Risks

 | Risk | Likelihood | Mitigation |
 |------|------------|------------|
 | Georreferenciación incorrecta (EASE-Grid 2.0 ≠ lat/lon) | Medium | EPSG:6933 es hallazgo inicial, no decisión cerrada. El reader/validator debe derivar CRS, transform y bounds desde metadata HDF5 y documentación del producto antes de escribir GeoTIFF |
 | rasterio/GDAL en Windows | Medium | Usar `rasterio` directamente para escritura GeoTIFF; instalar via wheel precompilado (Christoph Gohlke) o conda; evaluar rioxarray solo si se necesita reproyección integrada con xarray |
 | Memoria con HDF5 de 138 MB | Low | `sm_surface` ocupa ~25 MB (1624×3856×float32). Para MVP se permite cargar una variable completa. Requisito: no cargar datasets innecesarios, no chunked reading forzado |
 | Duplicación sin idempotencia | Low | Unique constraint `(raw_file_id, variable_name, processing_version)` + verificación antes de procesar; job `skipped` trazable |

 ## Rollback Plan

 1. Revertir commit con `git revert HEAD`
 2. Eliminar tablas: `DROP TABLE IF EXISTS processed_geospatial_layers, geospatial_processing_jobs CASCADE`
 3. Eliminar `data/processed/smap/` (si existe)
 4. Revertir `requirements.txt` y ejecutar `pip install -r requirements.txt`
 5. El Módulo 1 permanece intacto (archivos raw + metadata original sin cambios)

 ## Dependencies

 - Módulo 1 completado y archivado ✅
 - HDF5 real disponible: `data/raw/smap/2023/12/SMAP_L4_SM_gph_20231231T223000_Vv8010_001.h5`
 - PostgreSQL 15 con Docker Compose
 - Python 3.11

 ## Success Criteria

 - [ ] `SMAPHDF5Reader` extrae `sm_surface` del HDF5 real (tests unitarios passing)
 - [ ] `GeospatialValidationService` rechaza archivos inválidos con error controlado
 - [ ] GeoTIFF generado se abre con `rasterio.open()` y contiene CRS, transform, nodata
 - [ ] Tablas PostgreSQL creadas con unique constraint funcionando
 - [ ] Reprocesamiento del mismo archivo genera `skipped` (idempotencia verificada)
 - [ ] CLI ejecuta pipeline completo: `python -m src.geospatial.cli.process_smap --limit 1`
 - [ ] 40+ tests unitarios + 5 tests integración passing
 - [ ] Proposal → specs → design → tasks → apply → verify → archive completados
