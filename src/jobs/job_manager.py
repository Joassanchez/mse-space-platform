"""Job manager with state machine and retry logic.

Orchestrates the ingestion lifecycle: search → download → validate → register.
"""

import time
from typing import Any

from src.ingestion.base_connector import BaseIngestionConnector
from src.ingestion.smap.smap_connector import (
    AuthenticationError,
    DateRangeError,
    SearchError,
)
from src.models.job_models import IngestionJob, RawFile, RawFileStatus
from src.storage.metadata_repository import MetadataRepository


class JobManager:
    """Manages ingestion job lifecycle with state transitions and retries.

    State machine:
        pending → running → completed (all files OK)
        running → completed_with_warnings (≥1 OK, ≥1 failed)
        running → failed (0 files, auth error, search error)

    ready_for_etl:
        true  if completed OR completed_with_warnings (≥1 valid file)
        false if failed, pending, running, or search-only mode
    """

    MAX_RETRIES = 3
    BASE_BACKOFF = 1.0  # seconds

    def __init__(
        self,
        connector: BaseIngestionConnector,
        metadata_repo: MetadataRepository | None = None,
        metadata_backend: str = "json",
    ):
        """Initialize the job manager.

        Args:
            connector: The ingestion connector to use.
            metadata_repo: Metadata repository. Creates default if None.
            metadata_backend: Backend for metadata storage: "json" (default) or "postgresql".
        """
        self.connector = connector
        if metadata_backend == "postgresql":
            from src.storage.metadata_repository_pg import PostgreSQLMetadataRepository
            self.metadata_repo = PostgreSQLMetadataRepository()
        else:
            self.metadata_repo = metadata_repo or MetadataRepository()

    def run_ingestion(
        self,
        source: str,
        bbox: list[float],
        start_date: str,
        end_date: str,
        search_only: bool = False,
    ) -> IngestionJob:
        """Execute a full ingestion job.

        Args:
            source: Source identifier (e.g. 'smap').
            bbox: Bounding box [min_lon, min_lat, max_lon, max_lat].
            start_date: ISO date string.
            end_date: ISO date string.
            search_only: If True, only search without downloading.

        Returns:
            The completed IngestionJob with final state.
        """
        job = IngestionJob(
            source=source,
            bbox=bbox,
            start_date=start_date,
            end_date=end_date,
            search_only=search_only,
        )

        # Save initial job state
        self.metadata_repo.save_job(job)

        try:
            # Step 1: Authenticate
            try:
                self.connector.authenticate()
            except AuthenticationError as e:
                job.mark_failed(f"Authentication error: {e}")
                self.metadata_repo.save_job(job)
                return job

            # Step 2: Search
            try:
                results = self.connector.search(bbox, start_date, end_date)
            except (DateRangeError, SearchError) as e:
                job.mark_failed(f"Search error: {e}")
                self.metadata_repo.save_job(job)
                return job
            except Exception as e:
                job.mark_failed(f"Unexpected search error: {e}")
                self.metadata_repo.save_job(job)
                return job

            # Handle zero results (valid case, not an error)
            if not results:
                job.mark_running()
                job.mark_completed()
                self.metadata_repo.save_job(job)
                return job

            # Step 3: Search-only mode — list results without downloading
            if search_only:
                job.mark_running()
                for product in results:
                    metadata = self.connector.extract_metadata(product)
                    raw_file = RawFile(
                        granule_id=metadata.get("granule_id", ""),
                        source_product_id=source.upper(),
                        remote_url=metadata.get("remote_url", ""),
                        acquisition_date=metadata.get("acquisition_date", ""),
                        file_name=metadata.get("file_name", ""),
                        size_bytes=metadata.get("size_bytes", 0),
                        status=RawFileStatus.ALREADY_DOWNLOADED,
                        ready_for_etl=False,
                    )
                    job.files.append(raw_file)
                job.mark_completed()
                # NOT persisted to metadata repo — search-only is a dry run,
                # saving fake records would break idempotency in real downloads
                return job

            # Step 4: Download with retries
            job.mark_running()
            self.metadata_repo.save_job(job)

            raw_files = self._download_with_retries(results, job)
            job.files = raw_files

            # Step 5: Determine final state
            successful = [f for f in raw_files if f.status != RawFileStatus.ERROR]
            failed = [f for f in raw_files if f.status == RawFileStatus.ERROR]

            if len(failed) == 0:
                # All files OK
                job.mark_completed()
            elif len(successful) > 0:
                # Partial success
                job.mark_completed_with_warnings()
                for f in failed:
                    job.errors.append(
                        f"File {f.file_name}: {f.error_message or 'Download failed'}"
                    )
            else:
                # All files failed
                job.mark_failed(
                    f"All {len(failed)} files failed to download after retries"
                )

            self.metadata_repo.save_job(job)
            return job

        except Exception as e:
            job.mark_failed(f"Unexpected error during ingestion: {e}")
            self.metadata_repo.save_job(job)
            return job

    def _download_with_retries(
        self,
        results: list[dict[str, Any]],
        job: IngestionJob,
    ) -> list[RawFile]:
        """Download results with exponential backoff retry logic.

        Args:
            results: Search result products.
            job: The parent ingestion job.

        Returns:
            List of RawFile records (downloaded, skipped, or failed).
        """
        raw_files: list[RawFile] = []

        for product in results:
            metadata = self.connector.extract_metadata(product)
            last_error = None

            for attempt in range(1, self.MAX_RETRIES + 1):
                try:
                    files = self.connector.download([product], job)
                    raw_files.extend(files)
                    break  # Success — move to next product
                except Exception as e:
                    last_error = str(e)
                    if attempt < self.MAX_RETRIES:
                        backoff = self.BASE_BACKOFF * (2 ** (attempt - 1))
                        time.sleep(backoff)
                    # Continue to next attempt

            if last_error and not any(
                f.granule_id == metadata.get("granule_id", "") for f in raw_files
            ):
                # All retries exhausted — record failure
                raw_files.append(
                    RawFile(
                        granule_id=metadata.get("granule_id", ""),
                        source_product_id=job.source.upper(),
                        remote_url=metadata.get("remote_url", ""),
                        acquisition_date=metadata.get("acquisition_date", ""),
                        file_name=metadata.get("file_name", ""),
                        size_bytes=0,
                        checksum_sha256="",
                        file_path="",
                        status=RawFileStatus.ERROR,
                        ready_for_etl=False,
                        error_message=f"Failed after {self.MAX_RETRIES} retries: {last_error}",
                    )
                )

        return raw_files
