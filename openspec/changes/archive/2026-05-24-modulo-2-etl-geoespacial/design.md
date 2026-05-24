 # Design: Módulo 2 - ETL Geoespacial SMAP

 ## Technical Approach

 El sistema implementará un pipeline ETL geoespacial bajo Arquitectura Hexagonal. Orquestará la lectura de archivos HDF5 (SMAP), la validación de estructura, la extracción de arrays (ej. humedad superficial), el procesamiento espacial (proyección y recorte ROI), la escritura de GeoTIFFs y el registro en PostgreSQL. Cumpliendo las specs, se desacoplará la lógica general de raster de las implementaciones específicas de SMAP, garantizando extensibilidad, idempotencia estricta y seguridad en la escritura.

 ## Architecture Decisions

 ### Decision: Generic Interfaces vs Concrete SMAP Implementation

 **Choice**: Definir interfaces `GeospatialReader` y `GeospatialValidator` que serán implementadas por `SMAPHDF5Reader` y `SMAPValidationService`.
 **Alternatives considered**: Hardcodear lectura HDF5 directamente en el servicio orquestador.
 **Rationale**: Requisito de las specs (`hdf5-reading`, `geospatial-validation`) para permitir escalar a SAOCOM y NISAR sin reescribir el pipeline core.

 ### Decision: Output Format

 **Choice**: Escribir la capa raster en formato GeoTIFF usando `rasterio`.
 **Alternatives considered**: NetCDF, Zarr o escritura manual de binarios.
 **Rationale**: GeoTIFF es el estándar interoperable para GIS y está mandatado explícitamente en el PRD.

 ### Decision: CRS Handling

 **Choice**: Derivar o validar el CRS (ej. EPSG:6933) a partir de la metadata HDF5 y configuración, sin asumpciones hardcodeadas en el código base.
 **Alternatives considered**: Hardcodear `EPSG:6933` en toda la aplicación.
 **Rationale**: Evitar errores de georreferenciación. La spec `geotiff-writing` requiere explícitamente derivar el CRS y evitar hardcodes.

 ### Decision: ROI Clipping

 **Choice**: Clipping opcional y configurable. Si ROI está habilitado, reproyectar la geometría (ej. de EPSG:4326 a EPSG:6933) antes de recortar el raster. Si ROI está deshabilitado, pipeline genera raster completo sin recorte.
 **Alternatives considered**: Reproyectar todo el array raster a EPSG:4326 y luego recortar; hardcodear ROI obligatorio.
 **Rationale**: Transformar un vector es computacionalmente muy ligero; hacer *warping* de un raster completo es pesado y degrada calidad. ROI obligatorio rompería casos de uso que requieren el raster global.

 ### Decision: Idempotency Strategy

 **Choice**: Restricción única en base de datos `(raw_file_id, variable_name, processing_version)`.
 **Alternatives considered**: Solo revisar la existencia del archivo en disco.
 **Rationale**: Garantiza integridad a nivel ACID. La spec `geospatial-persistence` exige que no se sobreescriban archivos silenciosamente.

 ### Decision: Safe Write Strategy

 **Choice**: El `GeoTIFFWriter` escribirá en un archivo `.tmp` y hará un *atomic move* a la ruta final solo en caso de éxito.
 **Alternatives considered**: Escribir directo a la ruta final.
 **Rationale**: Evita dejar archivos parciales o corruptos si el proceso falla (ej. disco lleno), exigido por `geotiff-writing`.

 ## Data Flow

     PostgreSQL (raw_files) ──(RawFileDiscoveryRepository)──> Orchestrator
                                                                    │
                                                                    ▼
     HDF5 File on Disk ──(SMAPHDF5Reader)──> ExtractedVariable + GeospatialMetadata
                                                                    │
                                                                    ▼
                 ┌── ROI disabled ──> Full raster
     RasterProcessingService ──┤
                 └── ROI enabled ──> Reproject geometry → Clip raster
                                                                    │
                                                                    ▼
     GeoTIFFWriter (.tmp → atomic move) ──> data/processed/{source}/{var}/YYYY/MM/{source}_{var}_{date}_v{ver}.tif
                                                                    │
                                                                    ▼
     PostgreSQL (geospatial_processing_jobs + processed_geospatial_layers)

 ## File Changes

 | File | Action | Description |
 |------|--------|-------------|
 | `src/geospatial/domain/interfaces.py` | Create | Puertos genéricos: `GeospatialReader`, `GeospatialValidator`, `RawFileDiscoveryRepository`, `GeospatialProcessingJobRepository`, `ProcessedLayerRepository` |
 | `src/geospatial/domain/models.py` | Create | Modelos `ExtractedVariable`, `GeospatialMetadata`, `RasterProcessingResult`, `ProcessedLayer`, `GeospatialProcessingJob` |
 | `src/geospatial/domain/errors.py` | Create | Excepciones específicas: `ValidationError`, `ReadError`, `WriteError`, `IdempotencySkip` |
 | `src/geospatial/infrastructure/hdf5/smap_reader.py` | Create | Implementación SMAP del port `GeospatialReader` (`h5py`) |
 | `src/geospatial/application/smap_validation_service.py` | Create | Implementación SMAP del port `GeospatialValidator` |
 | `src/geospatial/infrastructure/raster/geotiff_writer.py` | Create | Escritura a `.tmp` y movimiento atómico (`rasterio`); agnóstico de fuente |
 | `src/geospatial/application/raster_processing_service.py` | Create | Genérico: nodata, CRS, transform, clipping; agnóstico de fuente |
 | `src/geospatial/infrastructure/persistence/postgres_repositories.py` | Create | Implementación PostgreSQL de los 3 repositorios |
 | `src/geospatial/application/orchestrator.py` | Create | Coordinación genérica del pipeline ETL; usa ports, no implementaciones concretas |
 | `src/geospatial/cli/process_smap.py` | Create | Punto de entrada CLI |
 | `migrations/002_create_tables.sql` | Create | Tablas `geospatial_processing_jobs`, `processed_geospatial_layers` |
 | `src/config/sources.yaml` | Modify | Config de variables (ej. `sm_surface`), ROI y nodata |
 | `requirements.txt` | Modify | Agregar dependencia `rasterio` |

 ## CLI Contract

 ```
 python -m src.geospatial.cli.process_smap [opciones]
 
 Opciones:
   --limit N                 Procesar hasta N archivos (default: todos)
   --raw-file-id ID          Procesar un raw_file_id específico
   --processing-version VER  Versión de procesamiento (default: v1)
   --roi-enabled             Habilitar recorte por ROI (default: true)
   --roi-path PATH           Ruta al archivo GeoJSON de ROI (default: de config)
 
 Códigos de salida:
   0  Todos los jobs completados sin errores
   1  Uno o más jobs fallaron
   2  Error de configuración o argumentos inválidos
 ```

 ## Interfaces / Contracts

 ### Domain Models

 ```python
 @dataclass
 class ExtractedVariable:
     data: np.ndarray              # 2D array (y, x)
     attributes: dict              # HDF5 attributes (units, long_name, etc.)
     units: str                    # e.g. "m3 m-3", "K"
     nodata_value: float           # -9999.0 for SMAP
     acquisition_date: str         # ISO date from product
 
 @dataclass
 class GeospatialMetadata:
     crs: str                     # WKT or EPSG code (validated/derived)
     transform: Affine             # rasterio affine transform
     bounds: tuple[float,float,float,float]  # (minx, miny, maxx, maxy)
     resolution: tuple[float,float]          # (x_res, y_res) in CRS units
     width: int                    # number of columns
     height: int                    # number of rows
 
 @dataclass
 class RasterProcessingResult:
     data: np.ndarray              # processed 2D array
     metadata: GeospatialMetadata
     statistics: dict              # min, max, mean, valid_pixel_count, nodata_pixel_count
     warnings: list[str]
 
 @dataclass
 class ProcessedLayer:
     id: int | None
     raw_file_id: int
     processing_job_id: str
     variable_name: str
     file_path: str
     crs: str
     bbox: list[float]
     resolution_x: float
     resolution_y: float
     width: int
     height: int
     nodata_value: float
     min_value: float
     max_value: float
     mean_value: float
     valid_pixel_count: int
     nodata_pixel_count: int
     acquisition_date: str
     processing_version: str
     created_at: str
 
 @dataclass
 class GeospatialProcessingJob:
     id: str
     raw_file_id: int
     source_code: str              # e.g. "SMAP"
     status: str                   # pending|running|completed|completed_with_warnings|failed|skipped
     started_at: str | None
     finished_at: str | None
     error_message: str | None
     warnings: list[str]
     created_at: str
 ```

 ### Ports (Generic Interfaces)

 ```python
 class GeospatialReader(ABC):
     """Generic port. Implemented by SMAPHDF5Reader for SMAP."""
     @abstractmethod
     def open(self, file_path: Path) -> None: ...
     @abstractmethod
     def extract_variable(self, variable_name: str) -> ExtractedVariable: ...
     @abstractmethod
     def get_metadata(self) -> GeospatialMetadata: ...
 
 class GeospatialValidator(ABC):
     """Generic port. Implemented by SMAPValidationService for SMAP."""
     @abstractmethod
     def validate_structure(self, file_path: Path, config: dict) -> bool: ...
     @abstractmethod
     def validate_variable(self, variable: ExtractedVariable, config: dict) -> bool: ...
 
 class RawFileDiscoveryRepository(ABC):
     """Searches raw_files table for completed files pending geospatial processing."""
     @abstractmethod
     def find_completed(self, source: str, limit: int | None = None) -> list[dict]: ...
     @abstractmethod
     def find_by_id(self, raw_file_id: int) -> dict | None: ...
 
 class GeospatialProcessingJobRepository(ABC):
     """CRUD for geospatial_processing_jobs table."""
     @abstractmethod
     def create(self, job: GeospatialProcessingJob) -> None: ...
     @abstractmethod
     def update_status(self, job_id: str, status: str, error: str | None = None) -> None: ...
     @abstractmethod
     def exists_by_raw_file_variable(self, raw_file_id: int, variable: str, version: str) -> bool: ...
 
 class ProcessedLayerRepository(ABC):
     """CRUD for processed_geospatial_layers table."""
     @abstractmethod
     def insert(self, layer: ProcessedLayer) -> int: ...
     @abstractmethod
     def get_by_raw_file_and_variable(self, raw_file_id: int, var: str, version: str) -> ProcessedLayer | None: ...
 ```

 ### Job State Transitions

 ```
 pending ──→ running ──→ completed
 pending ──→ running ──→ completed_with_warnings  (GeoTIFF OK, non-fatal warnings)
 pending ──→ running ──→ failed                   (critical error)
 pending ──→ skipped                               (idempotency hit before processing)
 ```

 ### File-DB Consistency Strategy

 | Risk | Mitigation |
 |------|------------|
 | GeoTIFF generated but no DB record | Atomic: write .tmp → move to final → INSERT in same transaction scope. If DB insert fails, delete orphan .tif. |
 | DB record points to missing file | Check `file_path` existence before returning or processing. Mark job as `failed` if file not found. |
 | Abandoned .tmp files | Clean up .tmp on successful move. On startup or job recovery, scan for .tmp older than 1h and remove. |
 | Physical duplicates on idempotent reprocess | Before writing, verify `exists_by_raw_file_variable`. If hit → skip, job = skipped, return existing path. |

 ### Deterministic Output Path

 ```
 data/processed/{source}/{variable}/{YYYY}/{MM}/{source}_{variable}_{acquisition_date}_{processing_version}.tif
 ```

 Example:
 data/processed/smap/soil_moisture/2023/12/smap_soil_moisture_20231231T223000_v1.tif

 ## Testing Strategy

 | Layer | What to Test | Approach |
 |-------|-------------|----------|
 | Unit | `SMAPHDF5Reader` | Usar mocks de `h5py` para validar extracción sin disco. |
 | Unit | `RasterProcessingService` | Arrays sintéticos (`numpy`) para probar clipping y nodata. |
 | Unit | `GeoTIFFWriter` | Probar lógica de archivo `.tmp` y atomic move. |
 | Integration | Pipeline Completo | HDF5 real -> CLI -> Validar apertura del GeoTIFF -> Verificar DB. |

 ## Migration — `002_create_tables.sql`

 (Migration content omitted in archive copy for brevity; see original change folder.)

 ## Alcance — Solo SMAP

 Este diseño implementa SMAP como primera fuente concreta. No se diseñan ni implementan SAOCOM, NISAR, SMN ni INDEC en este módulo. Los puertos genéricos (`GeospatialReader`, `GeospatialValidator`, repositorios) están definidos para que futuras fuentes puedan incorporarse sin modificar el core del pipeline, pero su implementación queda fuera del alcance del Módulo 2.

 ## Open Questions

 - [ ] ¿Cómo gestionar los entornos de despliegue si `rasterio`/GDAL presenta problemas de compilación en Windows para el Módulo 2? (Mitigación: usar conda o wheel precompilado).
