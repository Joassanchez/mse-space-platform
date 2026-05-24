"""Domain models for the geospatial ETL pipeline.

Dataclasses represent the core domain entities flowing through the pipeline.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

try:
    from shapely.geometry import MultiPolygon, Polygon
    import shapely.wkt

    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False


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
    footprint_geometry: Optional["Polygon"] = None
    data_source_id: Optional[int] = None
    data_source_code: Optional[str] = None


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


@dataclass
class Region:
    """Domain model for a geographic region.

    Attributes:
        id: Database-assigned ID (None before insert).
        name: Human-readable region name.
        geometry: Shapely MultiPolygon in EPSG:4326.
        region_type: Classification (administrative, province, etc.).
        country: Country name or ISO code.
        province: Province/state name.
        bbox: Bounding box [minx, miny, maxx, maxy].
        area_km2: Surface area in square kilometers.
        metadata: Additional JSONB metadata.
        is_active: Whether the region is currently active.
        created_at: ISO timestamp of creation.
        updated_at: ISO timestamp of last update.
    """

    name: str
    geometry: Optional["MultiPolygon"] = None
    region_type: str = "administrative"
    country: Optional[str] = None
    province: Optional[str] = None
    bbox: Optional[list[float]] = None
    area_km2: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Indicator:
    """Domain model for a computed indicator value.

    Attributes:
        id: Database-assigned ID (None before insert).
        region_id: FK to regions(id).
        processed_layer_id: FK to processed_geospatial_layers(id), nullable.
        indicator_code: Short code (e.g. "NDVI", "SM_INDEX").
        indicator_name: Human-readable name.
        indicator_type: Category (e.g. "vegetation", "soil_moisture").
        value: Numeric indicator value.
        unit: Unit string (e.g. "m3/m3", "index").
        classification: Derived classification string.
        confidence: Confidence score (0-1).
        calculation_method: Method used to compute the indicator.
        temporal_start: Start date of the measurement period.
        temporal_end: End date of the measurement period.
        metadata: Additional JSONB metadata.
        created_at: ISO timestamp of creation.
    """

    region_id: int
    indicator_code: str
    processed_layer_id: Optional[int] = None
    indicator_name: Optional[str] = None
    indicator_type: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    classification: Optional[str] = None
    confidence: Optional[float] = None
    calculation_method: Optional[str] = None
    temporal_start: Optional[str] = None
    temporal_end: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class RiskAssessment:
    """Domain model for a risk assessment result.

    Attributes:
        id: Database-assigned ID (None before insert).
        region_id: FK to regions(id).
        indicator_id: FK to indicators(id), nullable.
        risk_type: One of drought, flood, hydric_stress, agroenvironmental.
        risk_level: One of low, medium, high, critical.
        risk_score: Numeric risk score.
        confidence: Confidence score (0-1).
        method: Assessment method used.
        explanation: Human-readable explanation of the assessment.
        temporal_start: Start date of the assessment period.
        temporal_end: End date of the assessment period.
        metadata: Additional JSONB metadata.
        created_at: ISO timestamp of creation.
    """

    region_id: int
    risk_type: str
    risk_level: str
    indicator_id: Optional[int] = None
    risk_score: Optional[float] = None
    confidence: Optional[float] = None
    method: Optional[str] = None
    explanation: Optional[str] = None
    temporal_start: Optional[str] = None
    temporal_end: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class Alert:
    """Domain model for an alert notification.

    Attributes:
        id: Database-assigned ID (None before insert).
        region_id: FK to regions(id).
        risk_assessment_id: FK to risk_assessments(id), nullable.
        alert_type: Alert category string.
        severity: One of info, warning, severe, critical.
        title: Alert title.
        message: Detailed alert message.
        status: One of active, acknowledged, resolved, dismissed.
        issued_at: ISO timestamp when alert was issued.
        resolved_at: ISO timestamp when alert was resolved.
        metadata: Additional JSONB metadata.
        created_at: ISO timestamp of creation.
    """

    region_id: int
    alert_type: str
    severity: str
    title: str
    risk_assessment_id: Optional[int] = None
    message: Optional[str] = None
    status: str = "active"
    issued_at: Optional[str] = None
    resolved_at: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class EconomicImpact:
    """Domain model for an estimated economic impact.

    Attributes:
        id: Database-assigned ID (None before insert).
        region_id: FK to regions(id).
        risk_assessment_id: FK to risk_assessments(id), nullable.
        impact_type: Category of impact (e.g. "crop_loss", "infrastructure").
        estimated_loss_usd: Estimated financial loss in USD.
        affected_area_ha: Affected area in hectares.
        crop_type: Affected crop type.
        yield_loss_percentage: Percentage yield loss.
        method: Estimation method used.
        assumptions: Text describing assumptions made.
        confidence: Confidence score (0-1).
        metadata: Additional JSONB metadata.
        created_at: ISO timestamp of creation.
    """

    region_id: int
    impact_type: str
    risk_assessment_id: Optional[int] = None
    estimated_loss_usd: Optional[float] = None
    affected_area_ha: Optional[float] = None
    crop_type: Optional[str] = None
    yield_loss_percentage: Optional[float] = None
    method: Optional[str] = None
    assumptions: Optional[str] = None
    confidence: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class AuditLog:
    """Domain model for an audit log entry.

    Attributes:
        id: Database-assigned ID (None before insert).
        entity_type: Type of entity being audited.
        entity_id: ID of the entity being audited.
        action: Action performed (start, complete, fail, create, etc.).
        actor_type: One of system, user, agent.
        actor_id: ID of the actor.
        message: Human-readable description of the event.
        metadata: Additional JSONB metadata.
        created_at: ISO timestamp of the event.
    """

    entity_type: str
    action: str
    actor_type: str = "system"
    entity_id: Optional[str] = None
    actor_id: Optional[str] = None
    message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    created_at: Optional[str] = None
