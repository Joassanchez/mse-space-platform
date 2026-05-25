"""Pydantic schemas for regions endpoints."""

from datetime import datetime

from pydantic import BaseModel


class RegionListItem(BaseModel):
    """Summary view of a region for list endpoints."""

    id: int
    name: str
    region_type: str | None = None
    country: str | None = None
    province: str | None = None
    bbox: list[float] = []
    is_active: bool = True
    created_at: datetime | None = None


class RegionDetail(BaseModel):
    """Full detail of a single region."""

    id: int
    name: str
    region_type: str | None = None
    country: str | None = None
    province: str | None = None
    bbox: list[float] = []
    area_km2: float | None = None
    metadata: dict | None = None
    is_active: bool = True
    created_at: datetime | None = None


class RegionListResponse(BaseModel):
    """Response wrapper for region list."""

    items: list[RegionListItem]
