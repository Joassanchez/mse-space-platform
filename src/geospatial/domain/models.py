"""Domain models for the geospatial ETL pipeline.

Dataclasses represent the core domain entities flowing through the pipeline.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractedVariable:
    """A scientific variable extracted from a raw geospatial file.

    Attributes:
        data: 2D numpy array (y, x) with the variable values.
        attributes: HDF5/file attributes (units, long_name, etc.).
        units: Physical units string (e.g. "m3 m-3", "K").
        nodata_value: Sentinel value for missing data (e.g. -9999.0).
        acquisition_date: ISO date string from the product metadata.
    """

    data: Any  # np.ndarray
    attributes: dict[str, Any]
    units: str
    nodata_value: float
    acquisition_date: str


@dataclass
class GeospatialMetadata:
    """Spatial metadata required to write a georeferenced raster.

    Attributes:
        crs: WKT string or EPSG code (validated/derived, never hardcoded).
        transform: rasterio Affine transform for the raster grid.
        bounds: (minx, miny, maxx, maxy) in CRS units.
        resolution: (x_res, y_res) in CRS units per pixel.
        width: Number of columns.
        height: Number of rows.
    """

    crs: str
    transform: Any  # rasterio.transform.Affine
    bounds: tuple[float, float, float, float]
    resolution: tuple[float, float]
    width: int
    height: int


@dataclass
class RasterProcessingResult:
    """Result of raster processing (nodata handling, ROI clipping, statistics).

    Attributes:
        data: Processed 2D numpy array.
        metadata: GeospatialMetadata for the processed raster.
        statistics: Dict with min, max, mean, valid_pixel_count, nodata_pixel_count.
        warnings: Non-fatal issues encountered during processing.
    """

    data: Any  # np.ndarray
    metadata: GeospatialMetadata
    statistics: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


@dataclass
class ProcessedLayer:
    """Persistence model for a processed geospatial layer (DB record).

    Attributes:
        id: Database-assigned ID (None before insert).
        raw_file_id: FK to raw_files(id).
        processing_job_id: FK to geospatial_processing_jobs(id).
        variable_name: e.g. "sm_surface".
        file_path: Absolute path to the generated GeoTIFF.
        crs: CRS string (EPSG code or WKT).
        bbox: Bounding box [minx, miny, maxx, maxy] in CRS units.
        resolution_x: X resolution in CRS units.
        resolution_y: Y resolution in CRS units.
        width: Raster width in pixels.
        height: Raster height in pixels.
        nodata_value: Sentinel value for missing data.
        min_value: Minimum valid pixel value.
        max_value: Maximum valid pixel value.
        mean_value: Mean of valid pixels.
        valid_pixel_count: Number of non-nodata pixels.
        nodata_pixel_count: Number of nodata pixels.
        acquisition_date: ISO date of the source product.
        processing_version: Version string (e.g. "v1").
        created_at: ISO timestamp of layer creation.
    """

    raw_file_id: int
    processing_job_id: str
    source_code: str
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
    id: int | None = None
    created_at: str | None = None


@dataclass
class GeospatialProcessingJob:
    """Tracks the state of a geospatial processing job.

    Attributes:
        id: Job identifier (UUID string).
        raw_file_id: FK to raw_files(id).
        source_code: Source identifier (e.g. "SMAP").
        status: One of pending, running, completed, completed_with_warnings, failed, skipped.
        started_at: ISO timestamp when processing started.
        finished_at: ISO timestamp when processing finished.
        error_message: Error details if status is failed.
        warnings: Non-fatal issues collected during processing.
        created_at: ISO timestamp of job creation.
    """

    raw_file_id: int
    source_code: str
    status: str = "pending"
    id: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)
    created_at: str | None = None
