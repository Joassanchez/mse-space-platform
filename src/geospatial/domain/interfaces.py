"""Generic ports (interfaces) for the geospatial ETL pipeline.

All interfaces are source-agnostic. Concrete implementations (e.g. SMAPHDF5Reader)
live in the infrastructure layer and implement these ports.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from src.geospatial.domain.models import (
    ExtractedVariable,
    GeospatialMetadata,
    GeospatialProcessingJob,
    ProcessedLayer,
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
