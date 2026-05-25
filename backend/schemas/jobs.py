"""Pydantic schemas for jobs API — aligned with actual ingestion_jobs table."""

from datetime import datetime

from pydantic import BaseModel


class JobItem(BaseModel):
    """Minimal job info for list views."""

    id: str
    status: str
    region_id: str | None = None
    source_id: int | None = None
    date_from: str | None = None
    date_to: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None


class JobListResponse(BaseModel):
    """List of ingestion jobs."""

    items: list[JobItem]
    total: int


class JobDetailResponse(JobItem):
    """Full job detail."""

    error_message: str | None = None
    ready_for_etl: bool = False
    search_only: bool = False


class JobTriggerRequest(BaseModel):
    """Request to trigger a new ingestion job."""

    region_id: str
    date_from: str
    date_to: str
    bbox: list[float] | None = None


class JobTriggerResponse(BaseModel):
    """Response after triggering a job."""

    id: str
    status: str = "pending"
    region_id: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    created_at: datetime | None = None
