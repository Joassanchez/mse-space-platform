"""Pydantic schemas for alerts API responses.

Aligned with actual DB schema from migrations/003_add_postgis_and_models.sql.
"""

from datetime import datetime

from pydantic import BaseModel


class AlertItem(BaseModel):
    """Minimal alert info for list views."""

    id: int
    alert_type: str
    severity: str
    title: str
    status: str
    region_id: int
    region_name: str | None = None
    issued_at: datetime | None = None
    created_at: datetime | None = None


class AlertListResponse(BaseModel):
    """List of alerts."""

    items: list[AlertItem]
    total: int


class AlertDetailResponse(BaseModel):
    """Full alert detail."""

    id: int
    alert_type: str
    severity: str
    title: str
    message: str | None = None
    status: str
    region_id: int
    region_name: str | None = None
    issued_at: datetime | None = None
    resolved_at: datetime | None = None
    metadata: dict | None = None
    created_at: datetime | None = None


class ActiveAlertCountResponse(BaseModel):
    """Count of active alerts by severity level."""

    info: int = 0
    warning: int = 0
    severe: int = 0
    critical: int = 0
    total: int = 0
