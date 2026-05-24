"""Abstract base connector for data ingestion sources.

All ingestion connectors (SMAP, SAOCOM, NISAR, etc.) must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Any

from src.models.job_models import IngestionJob, RawFile


class BaseIngestionConnector(ABC):
    """Abstract base class for ingestion connectors.

    Subclasses must implement search, download, validate, extract_metadata,
    and register methods to support a specific data source.
    """

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the data source.

        Returns:
            True if authentication succeeds, False otherwise.

        Raises:
            AuthenticationError: If credentials are invalid or missing.
        """
        pass

    @abstractmethod
    def search(
        self,
        bbox: list[float],
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        """Search for available products within the given spatial and temporal bounds.

        Args:
            bbox: Bounding box [min_lon, min_lat, max_lon, max_lat].
            start_date: Start date in ISO format (YYYY-MM-DD).
            end_date: End date in ISO format (YYYY-MM-DD).

        Returns:
            List of product metadata dictionaries from the remote source.

        Raises:
            SearchError: If the search request fails.
            ValueError: If bbox or date range is invalid.
        """
        pass

    @abstractmethod
    def download(
        self,
        results: list[dict[str, Any]],
        job: IngestionJob,
    ) -> list[RawFile]:
        """Download search results and register them with storage.

        Args:
            results: List of product metadata from search().
            job: The ingestion job to associate files with.

        Returns:
            List of RawFile records (downloaded, skipped, or failed).
        """
        pass

    @abstractmethod
    def validate(self, file_path: str) -> bool:
        """Validate a downloaded file for integrity.

        Args:
            file_path: Path to the local file.

        Returns:
            True if the file is valid, False otherwise.
        """
        pass

    @abstractmethod
    def extract_metadata(self, product: dict[str, Any]) -> dict[str, Any]:
        """Extract relevant metadata from a raw product record.

        Args:
            product: Raw product dictionary from the search result.

        Returns:
            Normalized metadata dictionary with standard fields.
        """
        pass

    @abstractmethod
    def register(
        self,
        raw_file: RawFile,
        job: IngestionJob,
    ) -> None:
        """Register a downloaded file in the metadata repository.

        Args:
            raw_file: The RawFile record to register.
            job: The parent ingestion job.
        """
        pass
