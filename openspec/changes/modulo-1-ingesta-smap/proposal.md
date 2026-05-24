# Proposal: Módulo 1 - Ingesta de Datos SMAP

## Intent

Construir una capa de ingesta automatizada para obtener datos de humedad del suelo de SMAP (NASA Earthdata/NSIDC), guardándolos de forma trazable y dejándolos disponibles para el Módulo 2 de procesamiento ETL geoespacial. Este módulo es la base de datos crudos del sistema — sin ingesta confiable, no hay pipeline posterior posible.

## Scope

### In Scope
- Configuración declarativa de fuentes (YAML) con soporte para SMAP como primera implementación
- Autenticación contra NASA Earthdata vía `earthaccess` (EARTHDATA_USERNAME/PASSWORD)
- Búsqueda de productos SPL4SMGP.008 por bounding box y rango temporal
- **Modo search-only**: buscar y listar resultados sin descargar
- Descarga de archivos HDF5 a `data/raw/smap/YYYY/MM/`
- **Idempotencia**: si un archivo ya fue descargado y el checksum coincide, se salta
- Cálculo de checksum SHA-256 por archivo
- **Primera iteración**: registro de metadatos en `metadata.json` (archivo JSON por job, sin base de datos)
- Validación mínima (archivo existe, no vacío, extensión correcta, checksum calculable)
- Estados de job: pending, running, completed, completed_with_warnings, failed
- Marca `ready_for_etl` cuando los archivos están listos para procesamiento
- Manejo de errores de autenticación, búsqueda, descarga y validación
- Diseño extensible con `BaseIngestionConnector` para futuras fuentes (SAOCOM, NISAR, SMN, INDEC)

### Out of Scope
- Cálculo de humedad promedio o cualquier indicador
- Recorte geoespacial, reproyección o conversión a GeoTIFF (Módulo 2)
- Clasificación de sequía, riesgo o generación de alertas (Módulo 3/4)
- Visualización en dashboard (Módulo 5)
- Análisis con IA (Módulo 4)
- Automatización de fuentes distintas a SMAP en esta iteración

## Capabilities

> Contract between proposal and specs phases.

### New Capabilities
- `data-ingestion`: Capacidad general de ingesta de datos con conectores extensibles
- `smap-connector`: Conector específico para SMAP/NASA Earthdata con earthaccess
- `metadata-registry`: Registro y trazabilidad de metadatos de archivos crudos en JSON (Slice 1), migrable a PostgreSQL (Slice 2). PostGIS queda reservado para Módulo 2+
- `job-management`: Gestión de estados de jobs de ingesta (pending/running/completed/failed)

### Modified Capabilities
- None — este es el módulo inicial, no hay capacidades existentes que modificar

## Approach

**Arquitectura**: Hexagonal/Clean Architecture con conectores intercambiables. El núcleo define interfaces (`search()`, `download()`, `validate()`, `extract_metadata()`, `register()`); SMAP es la primera implementación concreta.

**Estructura del proyecto**:
```
src/
├── config/sources.yaml          # Configuración declarativa de fuentes
├── ingestion/
│   ├── base_connector.py        # Interfaz abstracta
│   └── smap/
│       ├── smap_connector.py    # Implementación SMAP
│       ├── smap_downloader.py   # Lógica de descarga
│       ├── smap_metadata.py     # Extracción de metadatos
│       └── smap_job.py          # Gestión de jobs
├── storage/
│   ├── raw_storage.py           # Gestión de data/raw
│   └── metadata_repository.py   # Repositorio de metadatos (JSON en Slice 1 → PostgreSQL en Slice 2)
└── jobs/
    └── run_smap_ingestion.py    # Entry point
```

**Decisiones técnicas clave**:
- `earthaccess` para consumo programático de NASA Earthdata (recomendado oficialmente)
- **Slice 1**: metadatos en `metadata.json` (por job), sin base de datos.
- **Slice 2**: migración a PostgreSQL plano (sin PostGIS). PostGIS queda reservado para cuando Módulo 2+ necesite consultas geoespaciales.
- HDF5 como formato crudo — sin transformación, se guarda tal cual
- **El bbox es solo para filtrar la búsqueda en NASA Earthdata. No implica recorte ni reproyección.** Los archivos se descargan completos.
- **Modo search-only**: flag `--search-only` para buscar y listar resultados sin descargar
- **Idempotencia**: antes de descargar, verificar si el archivo ya existe en `data/raw/smap/YYYY/MM/` por nombre y tamaño. Si existe, calcular checksum local y comparar contra el registrado en `metadata.json`. Si coincide, se salta y se registra como `already_downloaded`. No se asume checksum remoto disponible antes de la descarga.
- **Primera prueba limitada a 1-7 días de rango temporal** para evitar descargas masivas involuntarias.
- Checksum SHA-256 para integridad y detección de corrupción
- Variables de entorno para credenciales (`.env` con `EARTHDATA_USERNAME`/`PASSWORD`)
- Docker Compose para PostgreSQL (Slice 2 — en Slice 1 no hay dependencia de base de datos)
- **Política de `.gitignore`**: `data/raw/` y `data/processed/` se excluyen del control de versiones. Los datos crudos son caché reproducible; los datos procesados son artefactos derivados. Solo se versionan configuraciones, código fuente y documentación.

**Flujo operativo**:
1. Recibir región piloto (bbox) y rango temporal (máx 7 días en primera iteración)
2. Leer configuración de SMAP desde YAML
3. Autenticar contra NASA Earthdata
4. Buscar productos SPL4SMGP.008 disponibles
5. Si `--search-only`, listar resultados y terminar
6. Para cada resultado, verificar idempotencia (checksum vs archivo existente)
7. Descargar archivos HDF5 faltantes
8. Guardar en `data/raw/smap/YYYY/MM/`
9. Calcular checksum
10. Registrar metadatos en `metadata.json` (primera iteración)
11. Validar archivos
12. Actualizar `ingestion_job`
13. Marcar `ready_for_etl = true`

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/config/sources.yaml` | New | Configuración declarativa de SMAP y futuras fuentes |
| `src/ingestion/base_connector.py` | New | Interfaz abstracta para conectores de ingesta |
| `src/ingestion/smap/` | New | Implementación completa del conector SMAP |
| `src/storage/raw_storage.py` | New | Gestión de almacenamiento de datos crudos |
| `src/storage/metadata_repository.py` | New | Repositorio de metadatos en JSON (primera iteración) |
| `src/jobs/run_smap_ingestion.py` | New | Entry point para ejecución manual/programada |
| `data/raw/smap/` | New | Directorio de datos crudos descargados (no versionado) |
| `data/.gitignore` | New | Ignorar `data/raw/` y `data/processed/` — datos crudos y derivados no se versionan |
| `docker-compose.yml` | New | PostgreSQL (opcional, para slice posterior con DB) |
| `.env.example` | New | Plantilla de variables de entorno |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Cambios en API de NASA Earthdata | Low | `earthaccess` es librería oficial; actualizaciones frecuentes |
| Archivos HDF5 corruptos o incompletos | Medium | Validación de checksum + reintentos automáticos |
| Credenciales expuestas en logs | Low | Sanitizar logs, nunca imprimir credenciales, usar variables de entorno |
| Rate limiting de NASA Earthdata | Medium | Implementar backoff exponencial y respetar límites de la API |
| PostgreSQL no disponible en entorno local | Low | Sin impacto en Slice 1 (usa metadata.json); Slice 2 requiere Docker |
| Bounding box inválido o mal formado | Low | Validar coordenadas (lon -180..180, lat -90..90) antes de consultar |
| Rango sin resultados disponibles | Low | Informar cero resultados como caso válido, no como error |
| Descarga excesiva sin control | Medium | Límite de 7 días en rango + flag `--search-only` para previsualizar volumen |

## Rollback Plan (por slice)

### Slice 1 — Core + JSON metadata

- **Código**: Revertir commit — no hay datos en producción, es greenfield
- **Datos crudos**: Eliminar archivos de `data/raw/smap/` y re-ejecutar el job
- **Metadatos JSON**: Eliminar el `metadata.json` del job y re-ejecutar
- **Credenciales**: Rotar password de NASA Earthdata desde el portal si hay exposición sospechada

### Slice 2 — PostgreSQL

- **Código**: Revertir commit del slice
- **Datos crudos**: Los archivos en `data/raw/` son inmutables; si hay problema, se marcan como `ready_for_etl = false` y se re-ejecuta el job con nuevo rango
- **Metadatos en DB**: Drop de tablas `raw_files` e `ingestion_jobs` y re-ejecutar ingestion; las tablas `data_sources` y `datasets` son configuración estática
- **Migración**: Si se migró desde JSON, restaurar `metadata.json` original y eliminar registros en DB

## Dependencies

- **Python 3.11+** — versión estable recomendada para librerías geoespaciales
- **NASA Earthdata Login** — cuenta gratuita requerida (crear en https://urs.earthdata.nasa.gov)
- **PostgreSQL 15+** (opcional — solo para slices posteriores con base de datos)
- **Librerías Python (primera iteración)**: `earthaccess`, `h5py`, `pydantic`, `rich` (para logs)
- **Librerías Python (slice posterior)**: `psycopg2-binary`, `pandas`
- **Docker Desktop** — opcional, solo si se usa PostgreSQL local

## Timeline/Effort Estimate

| Tarea | Estimación | Descripción |
|-------|------------|-------------|
| **Slice 1 — Core + JSON metadata (sin DB)** | | |
| Setup del proyecto | 1h | Estructura inicial, venv, .env.example, .gitignore |
| Configuración YAML de fuentes | 1h | `sources.yaml` con schema validado por pydantic |
| BaseIngestionConnector (interfaz) | 2h | Clase abstracta con métodos: search, download, validate, extract_metadata, register |
| SmapConnector + search-only | 5h | Integración con earthaccess, autenticación, búsqueda, flag `--search-only` |
| Idempotencia + raw storage | 2h | Detección de duplicados por nombre/tamaño, validación contra metadata.json, estructura `data/raw/smap/YYYY/MM/` |
| Metadata JSON por job | 2h | `metadata.json` con datos de fuente, archivos, checksums, estados |
| Validación + checksum | 1.5h | Validación de archivos, cálculo SHA-256 |
| Job management + estados | 2h | Modelo de ingestion_job, transiciones de estado, error handling |
| Entry point + CLI | 1.5h | `run_smap_ingestion.py` con bbox, fechas (max 7d), `--search-only` |
| Tests slice 1 | 3h | Tests unitarios mockeando earthaccess, tests de idempotencia |
| | **~21h** | **Slice 1** |
| **Slice 2 — PostgreSQL (plano, sin PostGIS)** | | |
| Docker Compose con PostgreSQL | 1h | `docker-compose.yml` con PostgreSQL plano |
| Migraciones + MetadataRepository | 3h | Esquema de tablas, migración de metadata.json a DB |
| Tests slice 2 | 1h | Tests de integración con PostgreSQL en Docker |
| | **~5h** | **Slice 2** |
| **Total** | **~26h** | **~3-4 días laborales** |

## Success Criteria (por slice)

### Slice 1 — Core + JSON metadata

- [ ] Configuración de SMAP en YAML cargada y validada
- [ ] Autenticación exitosa contra NASA Earthdata con credenciales de entorno
- [ ] Búsqueda de SPL4SMGP.008 retorna resultados para bbox y fechas válidas
- [ ] Modo `--search-only` lista resultados sin descargar
- [ ] Descarga de ≥1 archivo HDF5 a `data/raw/smap/YYYY/MM/`
- [ ] Si el archivo ya existe y el checksum coincide, se salta (idempotencia)
- [ ] `data/raw/` está en `.gitignore` — no se versionan datos crudos
- [ ] Cada archivo tiene checksum SHA-256 registrado en `metadata.json`
- [ ] Cada ejecución genera un `ingestion_job` con estado correcto
- [ ] Límite de 7 días en rango temporal para primera prueba
- [ ] Salida del job indica `ready_for_etl = true` cuando todos los archivos son válidos
- [ ] Errores de autenticación/descarga se registran con mensaje claro
- [ ] Diseño permite agregar nuevo conector (ej: `SaocomConnector`) sin modificar lógica central

### Slice 2 — PostgreSQL (plano, sin PostGIS)

- [ ] Tablas `data_sources`, `datasets`, `ingestion_jobs`, `raw_files` creadas en PostgreSQL (sin PostGIS)
- [ ] Migración de `metadata.json` a PostgreSQL manteniendo integridad de datos existentes
- [ ] Queries de metadatos funcionan contra PostgreSQL
- [ ] Docker Compose listo para levantar PostgreSQL localmente
