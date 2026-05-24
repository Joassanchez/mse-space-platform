"""Raw storage operations for downloaded data files.

Handles filesystem paths, directory creation, SHA-256 checksums, and downloads.
"""

import hashlib
from datetime import datetime
from pathlib import Path

import earthaccess


class RawStorage:
    """Manages raw data file storage on the local filesystem.

    Files are stored in data/raw/<source>/<YYYY>/<MM>/ using the
    product's acquisition date (not the execution date).
    """

    def __init__(self, source: str, base_dir: str | Path | None = None):
        """Initialize storage for a specific data source.

        Args:
            source: Source identifier (e.g. 'smap').
            base_dir: Base directory for raw data. Defaults to data/raw/.
        """
        self.source = source
        if base_dir is None:
            # Project root is 3 levels up from src/storage/raw_storage.py
            project_root = Path(__file__).parent.parent.parent
            self.base_dir = project_root / "data" / "raw"
        else:
            self.base_dir = Path(base_dir)

    def get_destination_path(self, file_name: str, acquisition_date: str) -> Path:
        """Calculate the destination path for a downloaded file.

        Uses the product's acquisition date for directory partitioning.

        Args:
            file_name: The file name to store.
            acquisition_date: ISO date string (YYYY-MM-DD) from the product.

        Returns:
            Full destination path: data/raw/<source>/<YYYY>/<MM>/<file_name>
        """
        date = datetime.fromisoformat(acquisition_date)
        year_month = date.strftime("%Y/%m")
        dest_dir = self.base_dir / self.source / year_month
        dest_dir.mkdir(parents=True, exist_ok=True)
        return dest_dir / file_name

    def get_orphan_path(self, file_name: str, acquisition_date: str) -> Path | None:
        """Look for an orphan file that might exist on disk.

        Searches the expected directory for the file. Returns the path if
        found, None otherwise.

        Args:
            file_name: The file name to look for.
            acquisition_date: ISO date string for the expected directory.

        Returns:
            Path if file exists, None otherwise.
        """
        try:
            path = self.get_destination_path(file_name, acquisition_date)
            if path.exists():
                return path
        except (ValueError, OSError):
            pass
        return None

    def download_file(
        self,
        product: dict,
        metadata: dict,
    ) -> Path:
        """Download a single file from earthaccess search result.

        Args:
            product: Raw earthaccess product/granule object.
            metadata: Extracted metadata dict with file_name and acquisition_date.

        Returns:
            Path to the downloaded file.

        Raises:
            DownloadError: If the download fails.
        """
        dest_path = self.get_destination_path(metadata["file_name"], metadata["acquisition_date"])

        try:
            # earthaccess.download returns list of downloaded file paths
            downloaded = earthaccess.download([product], str(dest_path.parent))
            if not downloaded:
                raise RuntimeError(f"earthaccess returned empty download list for {metadata['file_name']}")

            # earthaccess may save to a subdirectory — find the actual file
            actual_path = Path(downloaded[0])
            if actual_path != dest_path:
                # Move to expected location if earthaccess used a different path
                actual_path.rename(dest_path)

            return dest_path
        except Exception as e:
            raise RuntimeError(f"Download failed for {metadata['file_name']}: {e}") from e

    def compute_sha256(self, file_path: str | Path) -> str:
        """Compute SHA-256 checksum for a file.

        Args:
            file_path: Path to the file.

        Returns:
            Hex-encoded SHA-256 digest string.
        """
        path = Path(file_path)
        sha256 = hashlib.sha256()

        with open(path, "rb") as f:
            # Read in chunks to handle large files without loading entirely into memory
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)

        return sha256.hexdigest()

    def file_exists_with_size(self, file_name: str, acquisition_date: str, expected_size: int) -> bool:
        """Check if a file exists on disk with the expected size.

        Args:
            file_name: The file name.
            acquisition_date: ISO date for directory lookup.
            expected_size: Expected file size in bytes.

        Returns:
            True if file exists and size matches.
        """
        path = self.get_destination_path(file_name, acquisition_date)
        if not path.exists():
            return False
        return path.stat().st_size == expected_size
