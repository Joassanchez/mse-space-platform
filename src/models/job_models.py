"""Data models for ingestion jobs and raw files."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class JobState(str, Enum):
    """Possible states for an ingestion job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"


class RawFileStatus(str, Enum):
    """Status of an individual raw file within a job."""

    DOWNLOADED = "downloaded"
    ALREADY_DOWNLOADED = "already_downloaded"
    ERROR = "error"


class RawFile(BaseModel):
    """Represents a single raw data file from an ingestion source."""

    granule_id: str = Field(..., description="NASA granule identifier")
    source_product_id: str = Field(..., description="Source product identifier (e.g. SPL4SMGP.008)")
    remote_url: str = Field(..., description="Remote download URL")
    acquisition_date: str = Field(..., description="Product acquisition date (ISO format)")
    file_name: str = Field(..., description="Local file name")
    size_bytes: int = Field(default=0, description="File size in bytes")
    checksum_sha256: str = Field(default="", description="SHA-256 checksum of the file")
    file_path: str = Field(default="", description="Local filesystem path")
    status: RawFileStatus = Field(
        default=RawFileStatus.DOWNLOADED, description="Download/verification status"
    )
    ready_for_etl: bool = Field(
        default=False, description="Whether this file is ready for ETL processing"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message if download/verification failed"
    )


class IngestionJob(BaseModel):
    """Represents a single ingestion job with its state and associated files."""

    job_id: str = Field(default_factory=lambda: str(uuid4()))
    source: str = Field(..., description="Source identifier (e.g. 'smap')")
    bbox: list[float] = Field(
        default_factory=lambda: [-180.0, -90.0, 180.0, 90.0],
        description="Bounding box [min_lon, min_lat, max_lon, max_lat]",
    )
    start_date: str = Field(..., description="Start date for search (ISO format)")
    end_date: str = Field(..., description="End date for search (ISO format)")
    state: JobState = Field(default=JobState.PENDING)
    ready_for_etl: bool = Field(default=False)
    search_only: bool = Field(default=False, description="If true, only search, no download")
    files: list[RawFile] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def mark_running(self) -> None:
        """Transition to running state."""
        self.state = JobState.RUNNING
        self._touch()

    def mark_completed(self) -> None:
        """Transition to completed state; set ready_for_etl if files exist."""
        self.state = JobState.COMPLETED
        self.ready_for_etl = len(self.files) > 0 and not self.search_only
        self._touch()

    def mark_completed_with_warnings(self) -> None:
        """Transition to completed_with_warnings; ready_for_etl if at least 1 file ok."""
        self.state = JobState.COMPLETED_WITH_WARNINGS
        successful = [f for f in self.files if f.status != RawFileStatus.ERROR]
        self.ready_for_etl = len(successful) > 0 and not self.search_only
        self._touch()

    def mark_failed(self, error: str) -> None:
        """Transition to failed state; ready_for_etl is always false."""
        self.state = JobState.FAILED
        self.ready_for_etl = False
        self.errors.append(error)
        self._touch()

    def _touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc).isoformat()
