"""Geospatial ETL module for transforming raw satellite data into processed GeoTIFF layers.

Subpackages:
    domain: Core models, interfaces, and errors
    application: Services and orchestrator
    infrastructure: Concrete implementations (HDF5 reader, GeoTIFF writer, PostgreSQL repos)
    cli: Command-line entry points
"""

from src.geospatial.domain.errors import IdempotencySkip, ReadError, ValidationError, WriteError
from src.geospatial.domain.interfaces import (
    GeospatialProcessingJobRepository,
    GeospatialReader,
    GeospatialValidator,
    ProcessedLayerRepository,
    RawFileDiscoveryRepository,
)
from src.geospatial.domain.models import (
    ExtractedVariable,
    GeospatialMetadata,
    GeospatialProcessingJob,
    ProcessedLayer,
    RasterProcessingResult,
)

__all__ = [
    # Errors
    "ValidationError",
    "ReadError",
    "WriteError",
    "IdempotencySkip",
    # Interfaces
    "GeospatialReader",
    "GeospatialValidator",
    "RawFileDiscoveryRepository",
    "GeospatialProcessingJobRepository",
    "ProcessedLayerRepository",
    # Models
    "ExtractedVariable",
    "GeospatialMetadata",
    "RasterProcessingResult",
    "ProcessedLayer",
    "GeospatialProcessingJob",
]
