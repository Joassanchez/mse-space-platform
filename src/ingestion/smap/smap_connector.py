"""SMAP connector for NASA Earthdata / NSIDC.

Handles authentication, search, and download of SPL4SMGP.008 products.
"""

import os
from datetime import datetime, timedelta
from typing import Any

import earthaccess

from src.ingestion.base_connector import BaseIngestionConnector
from src.models.job_models import IngestionJob, RawFile, RawFileStatus


class AuthenticationError(Exception):
    """Raised when Earthdata authentication fails."""

    pass


class SearchError(Exception):
    """Raised when a search request fails."""

    pass


class DateRangeError(Exception):
    """Raised when the requested date range exceeds the configured maximum."""

    pass


class BboxError(Exception):
    """Raised when the bounding box is invalid."""

    pass


class SmapConnector(BaseIngestionConnector):
    """Connector for SMAP SPL4SMGP.008 products via NASA Earthdata.

    Uses the earthaccess library for authentication and data retrieval.
    """

    PRODUCT_SHORT_NAME = "SPL4SMGP"
    PRODUCT_VERSION = "008"
    PRODUCT_ID = f"{PRODUCT_SHORT_NAME}.{PRODUCT_VERSION}"

    def __init__(self, max_days_range: int | None = None):
        """Initialize the SMAP connector.

        Args:
            max_days_range: Maximum allowed date range in days.
                           Falls back to MAX_DAYS_RANGE env var, then 7.
        """
        if max_days_range is not None:
            self.max_days_range = max_days_range
        else:
            self.max_days_range = int(os.getenv("MAX_DAYS_RANGE", "7"))

    def authenticate(self) -> bool:
        """Authenticate with NASA Earthdata using environment credentials.

        Returns:
            True if authentication succeeds.

        Raises:
            AuthenticationError: If credentials are missing or invalid.
        """
        username = os.getenv("EARTHDATA_USERNAME")
        password = os.getenv("EARTHDATA_PASSWORD")

        if not username or not password:
            raise AuthenticationError(
                "EARTHDATA_USERNAME and EARTHDATA_PASSWORD environment variables are required"
            )

        try:
            # earthaccess v0.17+ reads credentials from env vars automatically
            auth = earthaccess.login(strategy="environment")
            if not auth:
                raise AuthenticationError("Earthdata authentication failed — check credentials")
            return True
        except Exception as e:
            raise AuthenticationError(f"Earthdata authentication error: {e}") from e

    def search(
        self,
        bbox: list[float],
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        """Search for SPL4SMGP.008 products within bounds.

        Args:
            bbox: [min_lon, min_lat, max_lon, max_lat]
            start_date: ISO date string (YYYY-MM-DD)
            end_date: ISO date string (YYYY-MM-DD)

        Returns:
            List of product metadata dicts.

        Raises:
            BboxError: If bbox coordinates are invalid.
            DateRangeError: If date range exceeds max_days_range.
            SearchError: If the search request fails.
        """
        self._validate_bbox(bbox)
        self._validate_date_range(start_date, end_date)

        min_lon, min_lat, max_lon, max_lat = bbox

        try:
            results = earthaccess.search_data(
                short_name=self.PRODUCT_SHORT_NAME,
                version=self.PRODUCT_VERSION,
                bounding_box=(min_lon, min_lat, max_lon, max_lat),
                temporal=(start_date, end_date),
            )
            return results
        except Exception as e:
            raise SearchError(f"Search failed for {self.PRODUCT_ID}: {e}") from e

    def download(
        self,
        results: list[dict[str, Any]],
        job: IngestionJob,
    ) -> list[RawFile]:
        """Download search results with idempotency checks.

        Args:
            results: Product metadata from search().
            job: The ingestion job context.

        Returns:
            List of RawFile records.
        """
        from src.storage.raw_storage import RawStorage
        from src.storage.metadata_repository import MetadataRepository

        storage = RawStorage(source="smap")
        repo = MetadataRepository()

        raw_files: list[RawFile] = []

        # Ensure job exists in metadata repo before registering files
        repo.save_job(job)

        for product in results:
            metadata = self.extract_metadata(product)
            file_name = metadata["file_name"]
            size_bytes = metadata.get("size_bytes", 0)

            # Idempotency check: composite key (file_name + size_bytes)
            existing = repo.check_file_registered(file_name, size_bytes, job.job_id)
            if existing:
                # File already registered — verify checksum matches
                raw_file = RawFile(
                    granule_id=metadata["granule_id"],
                    source_product_id=self.PRODUCT_ID,
                    remote_url=metadata["remote_url"],
                    acquisition_date=metadata["acquisition_date"],
                    file_name=file_name,
                    size_bytes=size_bytes,
                    checksum_sha256=existing.checksum_sha256,
                    file_path=existing.file_path,
                    status=RawFileStatus.ALREADY_DOWNLOADED,
                    ready_for_etl=True,
                )
                raw_files.append(raw_file)
                continue

            # Check for orphan file on disk (exists but not in metadata)
            orphan_path = storage.get_orphan_path(file_name, metadata["acquisition_date"])
            if orphan_path and orphan_path.exists():
                checksum = storage.compute_sha256(orphan_path)
                raw_file = RawFile(
                    granule_id=metadata["granule_id"],
                    source_product_id=self.PRODUCT_ID,
                    remote_url=metadata["remote_url"],
                    acquisition_date=metadata["acquisition_date"],
                    file_name=file_name,
                    size_bytes=size_bytes,
                    checksum_sha256=checksum,
                    file_path=str(orphan_path),
                    status=RawFileStatus.ALREADY_DOWNLOADED,
                    ready_for_etl=True,
                )
                raw_files.append(raw_file)
                # Register orphan without re-downloading
                self.register(raw_file, job)
                continue

            # Download new file
            try:
                file_path = storage.download_file(product, metadata)
                checksum = storage.compute_sha256(file_path)

                raw_file = RawFile(
                    granule_id=metadata["granule_id"],
                    source_product_id=self.PRODUCT_ID,
                    remote_url=metadata["remote_url"],
                    acquisition_date=metadata["acquisition_date"],
                    file_name=file_name,
                    size_bytes=file_path.stat().st_size,
                    checksum_sha256=checksum,
                    file_path=str(file_path),
                    status=RawFileStatus.DOWNLOADED,
                    ready_for_etl=True,
                )
                raw_files.append(raw_file)
                self.register(raw_file, job)

            except Exception as e:
                raw_file = RawFile(
                    granule_id=metadata["granule_id"],
                    source_product_id=self.PRODUCT_ID,
                    remote_url=metadata["remote_url"],
                    acquisition_date=metadata["acquisition_date"],
                    file_name=file_name,
                    size_bytes=0,
                    checksum_sha256="",
                    file_path="",
                    status=RawFileStatus.ERROR,
                    ready_for_etl=False,
                    error_message=str(e),
                )
                raw_files.append(raw_file)

        return raw_files

    def validate(self, file_path: str) -> bool:
        """Validate a downloaded HDF5 file exists and is non-empty.

        Args:
            file_path: Path to the local HDF5 file.

        Returns:
            True if valid, False otherwise.
        """
        from pathlib import Path

        p = Path(file_path)
        if not p.exists():
            return False
        if p.stat().st_size == 0:
            return False
        if not p.suffix.lower() in (".h5", ".hdf5"):
            return False
        return True

    def extract_metadata(self, product: dict[str, Any]) -> dict[str, Any]:
        """Extract normalized metadata from an earthaccess search result.

        Args:
            product: Raw product dict from earthaccess.search_data().

        Returns:
            Normalized metadata dict with standard fields.
        """
        # earthaccess returns Granule-like objects or dicts
        if hasattr(product, "umm"):
            # It's a Granule object — extract from UMM
            umm = product.umm
            granule_id = umm.get("GranuleUR", "")
            related_urls = umm.get("RelatedUrls", [])
            data_links = [
                u for u in related_urls if u.get("Type") == "GET DATA"
            ]
            remote_url = data_links[0]["URL"] if data_links else ""

            # Extract acquisition date from temporal range
            temporal = umm.get("TemporalExtent", {})
            range_date = temporal.get("RangeDateTime", {})
            beginning = range_date.get("BeginningDateTime", "")
            acquisition_date = beginning[:10] if beginning else ""

            file_name = remote_url.split("/")[-1] if remote_url else ""
            size_bytes = self._extract_size_bytes(umm)

        elif isinstance(product, dict):
            umm = product.get("umm", product)
            granule_id = umm.get("GranuleUR", "")
            related_urls = umm.get("RelatedUrls", [])
            data_links = [
                u for u in related_urls if u.get("Type") == "GET DATA"
            ]
            remote_url = data_links[0]["URL"] if data_links else ""

            temporal = umm.get("TemporalExtent", {})
            range_date = temporal.get("RangeDateTime", {})
            beginning = range_date.get("BeginningDateTime", "")
            acquisition_date = beginning[:10] if beginning else ""

            file_name = remote_url.split("/")[-1] if remote_url else ""
            size_bytes = self._extract_size_bytes(umm)
        else:
            granule_id = ""
            remote_url = ""
            acquisition_date = ""
            file_name = ""
            size_bytes = 0

        return {
            "granule_id": granule_id,
            "remote_url": remote_url,
            "acquisition_date": acquisition_date,
            "file_name": file_name,
            "size_bytes": size_bytes,
        }

    @staticmethod
    def _extract_size_bytes(umm: dict) -> int:
        """Extract the HDF5 file size in bytes from UMM metadata.

        The ArchiveAndDistributionInformation list contains entries for
        .qa, .h5, and .xml files. We need to find the .h5 entry specifically.
        """
        adi = umm.get("DataGranule", {}).get("ArchiveAndDistributionInformation", [])
        if not adi:
            return 0
        # Find the HDF5 entry by Name
        for entry in adi:
            name = entry.get("Name", "")
            if name.endswith((".h5", ".hdf5")):
                size = entry.get("SizeInBytes") or entry.get("Size", 0)
                return int(size)
        # Fallback: use first entry's SizeInBytes or Size
        entry = adi[0]
        return int(entry.get("SizeInBytes") or entry.get("Size", 0))

    def register(self, raw_file: RawFile, job: IngestionJob) -> None:
        """Register a file in the metadata repository.

        Args:
            raw_file: The RawFile to register.
            job: The parent ingestion job.
        """
        from src.storage.metadata_repository import MetadataRepository

        repo = MetadataRepository()
        repo.save_file(raw_file, job.job_id)

    def _validate_bbox(self, bbox: list[float]) -> None:
        """Validate bounding box coordinates.

        Args:
            bbox: [min_lon, min_lat, max_lon, max_lat]

        Raises:
            BboxError: If coordinates are out of range.
        """
        if len(bbox) != 4:
            raise BboxError(f"bbox must have 4 values, got {len(bbox)}")

        min_lon, min_lat, max_lon, max_lat = bbox

        if not (-180 <= min_lon <= 180):
            raise BboxError(f"min_lon must be between -180 and 180, got {min_lon}")
        if not (-180 <= max_lon <= 180):
            raise BboxError(f"max_lon must be between -180 and 180, got {max_lon}")
        if not (-90 <= min_lat <= 90):
            raise BboxError(f"min_lat must be between -90 and 90, got {min_lat}")
        if not (-90 <= max_lat <= 90):
            raise BboxError(f"max_lat must be between -90 and 90, got {max_lat}")
        if min_lon >= max_lon:
            raise BboxError(f"min_lon ({min_lon}) must be less than max_lon ({max_lon})")
        if min_lat >= max_lat:
            raise BboxError(f"min_lat ({min_lat}) must be less than max_lat ({max_lat})")

    def _validate_date_range(self, start_date: str, end_date: str) -> None:
        """Validate that the date range does not exceed max_days_range.

        Args:
            start_date: ISO date string.
            end_date: ISO date string.

        Raises:
            DateRangeError: If range exceeds max_days_range.
        """
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)

        if end < start:
            raise DateRangeError(f"end_date ({end_date}) must be after start_date ({start_date})")

        delta = (end - start).days
        if delta > self.max_days_range:
            raise DateRangeError(
                f"Date range of {delta} days exceeds maximum of {self.max_days_range} days. "
                f"Set MAX_DAYS_RANGE environment variable to override."
            )
