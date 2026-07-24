"""SQLAlchemy ORM model and Pydantic schemas for the satellite module."""

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import JSON, DateTime, Double, Text
from sqlalchemy.orm import Mapped, mapped_column

from argplant.shared.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------


class SatelliteScene(Base):
    __tablename__ = "satellite_scenes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scene_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    bbox: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    acquisition_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    cloud_cover: Mapped[float | None] = mapped_column(Double, nullable=True)
    metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------


class SmSceneMeta(BaseModel):
    """SMAP soil moisture granule metadata returned by the API."""

    scene_id: str
    acquisition_date: datetime
    granule_ur: str
    platform: str = "smap"
    bbox: list[float]

    model_config = {"from_attributes": True}


class SentinelSceneMeta(BaseModel):
    """Sentinel-1/2 scene metadata returned by the catalog search."""

    id: str = Field(alias="scene_id")
    acquisition_date: datetime
    cloud_cover: float | None = None
    thumbnail_url: str | None = None
    platform: str
    bbox: list[float]

    model_config = {"from_attributes": True, "populate_by_name": True}


class DownloadResponse(BaseModel):
    """Response returned after enqueuing a download job."""

    job_id: str
    status: str = "queued"


class JobStatus(BaseModel):
    """Status of an async ingestion job."""

    job_id: str
    status: str
    result: dict[str, Any] | None = None
