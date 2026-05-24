# Design: Módulo 1 - Ingesta de Datos SMAP

## Technical Approach

El módulo de ingesta se construirá siguiendo principios de Clean/Hexagonal Architecture. La lógica central de orquestación de trabajos (Jobs), validación de idempotencia y almacenamiento de metadatos estará completamente desacoplada de la fuente de datos específica. El conector para SMAP (`SmapConnector`) implementará una interfaz común (`BaseIngestionConnector`). Se construirá en dos slices: el primero utilizará un archivo JSON local (`metadata.json`) para persistir la información de los jobs y archivos (sin depender de bases de datos), y el segundo slice reemplazará la capa de almacenamiento con PostgreSQL plano (sin PostGIS). El almacenamiento de los crudos será directamente en el sistema de archivos (`data/raw/...`), particionado por la fecha de adquisición del producto.

## Architecture Decisions

### Decision: Almacenamiento de metadatos en JSON para Slice 1
**Choice**: Usar un archivo `metadata.json` por job de ingesta para almacenar información de archivos y estados, sin base de datos (ni SQLite).
**Alternatives considered**: Usar SQLite como base de datos embebida desde el día uno, o usar PostgreSQL directamente.
**Rationale**: El uso de JSON reduce la complejidad inicial al mínimo y permite construir y validar todo el core de orquestación y conectores (Slice 1) rápidamente. Posteriormente (Slice 2), esta pieza se cambiará por PostgreSQL, manteniendo el principio de segregación de interfaces.

### Decision: Idempotencia basada en disco y metadata local
**Choice**: Para determinar si un archivo ya fue descargado, verificar primero si existe en disco (por nombre/tamaño). Si existe, calcular su SHA-256 local y compararlo contra el registrado en `metadata.json` (o DB). Si coincide, saltar descarga. Si no hay registro previo (archivo huérfano), registrarlo sin re-descargar.
**Alternatives considered**: Solicitar siempre el checksum remoto a NASA Earthdata antes de descargar para comparar.
**Rationale**: `earthaccess` no garantiza exponer un checksum remoto liviano en todas las colecciones previo a la descarga. Basar la idempotencia en el estado local asegura robustez y evita llamadas innecesarias a la API.

### Decision: Estructura de partición de datos crudos
**Choice**: Almacenar en `data/raw/<source>/<YYYY>/<MM>/` basándose en la **fecha de adquisición/timestamp** del producto, no en la fecha de ejecución de la ingesta.
**Alternatives considered**: Particionar por fecha de ingesta.
**Rationale**: Los procesos de ETL posteriores y análisis temporales buscarán los datos por el período observado (adquisición). Particionar por fecha de adquisición optimiza la búsqueda y facilita el reprocesamiento.

## Data Flow

    [CLI/run_smap_ingestion] ──(bbox, dates)──→ [JobManager]
                                                      │
         ┌────────────────────────────────────────────┤
         │                                            ▼
    [SmapConnector] ◀──(search)── [earthaccess/NASA Earthdata]
         │
         ├──(search-only = True) ──→ List results & Exit (completed)
         │
         └──(search-only = False)
                 │
                 ▼
         [RawStorage] ──(check idempotency)── [MetadataRepository]
                 │                                    │
                 ▼                                    ▼
       (Download HDF5 to disk)              (Save JSON / PostgreSQL)

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/config/sources.yaml` | Create | Define config para SMAP (default limit 7 días) |
| `src/ingestion/base_connector.py` | Create | Interfaz abstracta `BaseIngestionConnector` |
| `src/ingestion/smap/smap_connector.py` | Create | Integración principal con `earthaccess` |
| `src/ingestion/smap/smap_downloader.py` | Create | Lógica de descarga e idempotencia |
| `src/storage/raw_storage.py` | Create | Manejo de filesystem y verificación SHA-256 |
| `src/storage/metadata_repository.py` | Create | Abstracción de registro (JSON local en Slice 1) |
| `src/jobs/run_smap_ingestion.py` | Create | CLI de entrada y orquestador |
| `data/.gitignore` | Create | Excluye directorios `raw/` y `processed/` |
| `openspec/changes/modulo-1-ingesta-smap/design.md` | Create | Este documento de diseño |

## Interfaces / Contracts

### Data Models

```python
from enum import Enum
from pydantic import BaseModel, Field

class JobState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"

class RawFile(BaseModel):
    file_name: str
    product_acquisition_date: str
    file_path: str
    size_bytes: int
    checksum_sha256: str
    status: str # downloaded, already_downloaded, error

class IngestionJob(BaseModel):
    job_id: str
    source: str
    start_time: str
    end_time: str | None = None
    state: JobState = JobState.PENDING
    ready_for_etl: bool = False
    files: list[RawFile] = []
    errors: list[str] = []
```

### Connector Interface

```python
from abc import ABC, abstractmethod

class BaseIngestionConnector(ABC):
    @abstractmethod
    def search(self, bbox: list[float], start_date: str, end_date: str) -> list[dict]:
        pass
        
    @abstractmethod
    def download(self, results: list[dict], storage, metadata_repo) -> list[RawFile]:
        pass
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Orquestación, límites de fechas, y transición de estados | Mockear `SmapConnector` (sin red). Verificar `MAX_DAYS_RANGE`. |
| Unit | Idempotencia y checksums | Usar filesystem temporal local. Verificar bypass de descarga. |
| Integration | earthaccess API auth y búsqueda | Test real con credenciales vía `.env`, usar `--search-only` para validar parsing de metadata sin descargar. (Decorador `@pytest.mark.integration`). |

## Migration / Rollout

**Slice 1:** No requiere migración de datos. Crea estructura local (JSON y raw storage).
**Slice 2:** Requerirá un script (ej: `migrate_metadata_to_pg.py`) para parsear los `metadata.json` históricos e insertar los registros en las tablas de PostgreSQL recién creadas.

## Open Questions

- [ ] ¿El esquema del Slice 2 en PostgreSQL requerirá claves foráneas hacia alguna tabla de dominios ya existente en la base de datos, o es completamente self-contained por ahora? (Asumido self-contained en el MVP).
- [ ] ¿La rotación de credenciales EARTHDATA_PASSWORD requerirá invalidar sesiones previas? (Asumido que earthaccess maneja los tokens internamente).
