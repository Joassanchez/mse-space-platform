"""Generic ports (interfaces) for the geospatial ETL pipeline.

All interfaces are source-agnostic. Concrete implementations (e.g. SMAPHDF5Reader)
live in the infrastructure layer and implement these ports.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from src.geospatial.domain.models import (
    Alert,
    AuditLog,
    EconomicImpact,
    ExtractedVariable,
    GeospatialMetadata,
    GeospatialProcessingJob,
    Indicator,
    ProcessedLayer,
    Region,
    RiskAssessment,
)


class GeospatialReader(ABC):
    """Generic port for reading geospatial source files.

    Implemented by source-specific readers (e.g. SMAPHDF5Reader for SMAP HDF5).
    """

    @abstractmethod
    def open(self, file_path: Path) -> None:
        """Open a geospatial file and prepare it for reading.

        Args:
            file_path: Path to the source file.

        Raises:
            ReadError: If the file cannot be opened or is not a valid format.
        """
        pass

    @abstractmethod
    def extract_variable(self, variable_name: str) -> ExtractedVariable:
        """Extract a specific variable from the opened file.

        Args:
            variable_name: Name/path of the variable to extract (e.g. "Geophysical_Data/sm_surface").

        Returns:
            ExtractedVariable with data, attributes, units, nodata_value, and acquisition_date.

        Raises:
            ReadError: If the variable cannot be extracted.
        """
        pass

    @abstractmethod
    def get_metadata(self) -> GeospatialMetadata:
        """Derive spatial metadata from the opened file.

        Returns:
            GeospatialMetadata with CRS, transform, bounds, resolution, width, height.

        Raises:
            ReadError: If metadata cannot be derived.
        """
        pass


class GeospatialValidator(ABC):
    """Generic port for validating geospatial source files and extracted variables.

    Implemented by source-specific validators (e.g. SMAPValidationService).
    """

    @abstractmethod
    def validate_structure(self, file_path: Path, config: dict[str, Any]) -> bool:
        """Validate that a file meets the minimum expected structure.

        Args:
            file_path: Path to the source file.
            config: Source-specific configuration (expected dimensions, groups, etc.).

        Returns:
            True if structure is valid.

        Raises:
            ValidationError: If structural requirements are not met.
        """
        pass

    @abstractmethod
    def validate_variable(self, variable: ExtractedVariable, config: dict[str, Any]) -> bool:
        """Validate an extracted variable's data range and metadata.

        Args:
            variable: The extracted variable to validate.
            config: Source-specific configuration (expected ranges, required attributes).

        Returns:
            True if variable is valid.

        Raises:
            ValidationError: If variable data or metadata is invalid.
        """
        pass


class RawFileDiscoveryRepository(ABC):
    """Searches raw_files table for completed files pending geospatial processing."""

    @abstractmethod
    def find_completed(self, source: str, limit: int | None = None) -> list[dict[str, Any]]:
        """Find raw files with completed status pending geospatial processing.

        Args:
            source: Source code filter (e.g. "SMAP").
            limit: Maximum number of files to return (None for all).

        Returns:
            List of raw file dicts with id, file_path, source_product_id, etc.
        """
        pass

    @abstractmethod
    def find_by_id(self, raw_file_id: int) -> dict[str, Any] | None:
        """Find a specific raw file by its database ID.

        Args:
            raw_file_id: The raw_files.id value.

        Returns:
            Raw file dict or None if not found.
        """
        pass


class GeospatialProcessingJobRepository(ABC):
    """CRUD for geospatial_processing_jobs table."""

    @abstractmethod
    def create(self, job: GeospatialProcessingJob) -> None:
        """Insert a new processing job record.

        Args:
            job: The job to create (must have id set).
        """
        pass

    @abstractmethod
    def update_status(
        self,
        job_id: str,
        status: str,
        error: str | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        """Update the status of an existing job.

        Args:
            job_id: The job identifier.
            status: New status value.
            error: Error message (if status is failed).
            warnings: List of non-fatal warnings.
        """
        pass

    @abstractmethod
    def exists_by_raw_file_variable(
        self, raw_file_id: int, variable: str, version: str
    ) -> bool:
        """Check if a layer already exists for the given combination.

        Used for idempotency: if True, skip processing.

        Args:
            raw_file_id: The raw file database ID.
            variable: Variable name (e.g. "sm_surface").
            version: Processing version string (e.g. "v1").

        Returns:
            True if a matching layer already exists.
        """
        pass


class ProcessedLayerRepository(ABC):
    """CRUD for processed_geospatial_layers table."""

    @abstractmethod
    def insert(self, layer: ProcessedLayer) -> int:
        """Insert a new processed layer record.

        Args:
            layer: The layer to insert.

        Returns:
            The database-assigned layer ID.
        """
        pass

    @abstractmethod
    def get_by_raw_file_and_variable(
        self, raw_file_id: int, var: str, version: str
    ) -> ProcessedLayer | None:
        """Retrieve an existing layer by raw file, variable, and version.

        Args:
            raw_file_id: The raw file database ID.
            var: Variable name.
            version: Processing version string.

        Returns:
            ProcessedLayer if found, None otherwise.
        """
        pass


# ============================================================
# Geospatial Storage Interfaces (Módulo 3)
# ============================================================


class RegionRepository(ABC):
    """CRUD and spatial queries for the regions table."""

    @abstractmethod
    def save(self, region: Region) -> int:
        """Insert or update a region record.

        Args:
            region: The region to persist.

        Returns:
            The database-assigned region ID.
        """
        pass

    @abstractmethod
    def get_by_id(self, region_id: int) -> Region | None:
        """Retrieve a region by its database ID.

        Args:
            region_id: The regions.id value.

        Returns:
            Region if found, None otherwise.
        """
        pass

    @abstractmethod
    def find_intersecting_geometry(self, wkt: str) -> list[Region]:
        """Find regions whose geometry intersects the given WKT polygon.

        Uses PostGIS ST_Intersects for spatial query.

        Args:
            wkt: WKT string of the query geometry (EPSG:4326).

        Returns:
            List of intersecting Region objects.
        """
        pass


class IndicatorRepository(ABC):
    """CRUD and queries for the indicators table."""

    @abstractmethod
    def save(self, indicator: Indicator) -> int:
        """Insert an indicator record.

        Args:
            indicator: The indicator to persist.

        Returns:
            The database-assigned indicator ID.
        """
        pass

    @abstractmethod
    def find_by_region(self, region_id: int) -> list[Indicator]:
        """Find all indicators for a given region.

        Args:
            region_id: The regions.id value.

        Returns:
            List of Indicator objects for the region.
        """
        pass


class RiskAssessmentRepository(ABC):
    """CRUD and queries for the risk_assessments table."""

    @abstractmethod
    def save(self, assessment: RiskAssessment) -> int:
        """Insert a risk assessment record.

        Args:
            assessment: The assessment to persist.

        Returns:
            The database-assigned assessment ID.
        """
        pass

    @abstractmethod
    def find_by_region_and_date(
        self, region_id: int, date_from: str | None = None, date_to: str | None = None
    ) -> list[RiskAssessment]:
        """Find risk assessments for a region within a date range.

        Args:
            region_id: The regions.id value.
            date_from: Start date filter (inclusive).
            date_to: End date filter (inclusive).

        Returns:
            List of matching RiskAssessment objects.
        """
        pass


class AlertRepository(ABC):
    """CRUD and queries for the alerts table."""

    @abstractmethod
    def save(self, alert: Alert) -> int:
        """Insert an alert record.

        Args:
            alert: The alert to persist.

        Returns:
            The database-assigned alert ID.
        """
        pass

    @abstractmethod
    def find_active_by_region(self, region_id: int) -> list[Alert]:
        """Find active alerts for a given region.

        Args:
            region_id: The regions.id value.

        Returns:
            List of active Alert objects.
        """
        pass


class EconomicImpactRepository(ABC):
    """CRUD and queries for the economic_impacts table."""

    @abstractmethod
    def save(self, impact: EconomicImpact) -> int:
        """Insert an economic impact record.

        Args:
            impact: The impact to persist.

        Returns:
            The database-assigned impact ID.
        """
        pass

    @abstractmethod
    def find_by_indicator(self, indicator_id: int) -> list[EconomicImpact]:
        """Find economic impacts associated with an indicator.

        Args:
            indicator_id: The indicators.id value.

        Returns:
            List of EconomicImpact objects.
        """
        pass


class DataSourceRepository(ABC):
    """Queries for the data_sources table."""

    @abstractmethod
    def get_by_code(self, code: str) -> dict[str, Any] | None:
        """Retrieve a data source by its unique code.

        Args:
            code: The data_sources.code value.

        Returns:
            Dict of data source fields or None if not found.
        """
        pass

    @abstractmethod
    def get_by_id(self, source_id: int) -> dict[str, Any] | None:
        """Retrieve a data source by its database ID.

        Args:
            source_id: The data_sources.id value.

        Returns:
            Dict of data source fields or None if not found.
        """
        pass


class AuditRepository(ABC):
    """Append-only audit log repository."""

    @abstractmethod
    def log_event(self, audit_log: AuditLog) -> int:
        """Insert an audit log entry.

        Args:
            audit_log: The audit log entry to persist.

        Returns:
            The database-assigned audit log ID.
        """
        pass
