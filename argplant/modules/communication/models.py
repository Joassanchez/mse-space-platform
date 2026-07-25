"""Alert models matching the frontend's expected JSON schema.

SQLAlchemy ORM + Pydantic schemas aligned with the frontend contract:
  - region_id, alert_type, severity, title, message, status, metadata
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from argplant.shared.database import Base


# ---------------------------------------------------------------------------
# SQLAlchemy ORM
# ---------------------------------------------------------------------------


class Alert(Base):
    """Alert row in the database — matches frontend SSE contract."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(Integer, nullable=False)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    SEVERITY_VALUES = frozenset({"info", "warning", "severe", "critical"})
    STATUS_VALUES = frozenset({"active", "acknowledged", "resolved"})


# ---------------------------------------------------------------------------
# Pydantic schemas (matching frontend contract)
# ---------------------------------------------------------------------------


class AlertCreate(BaseModel):
    """Schema for creating a new alert (POST /api/v1/alerts)."""

    region_id: int
    alert_type: str
    severity: str = "info"
    title: str
    message: str
    status: str = "active"
    metadata_: dict[str, Any] | None = Field(default=None, alias="metadata")


class AlertResponse(BaseModel):
    """Schema returned to the frontend (GET / SSE)."""

    id: int
    region_id: int
    alert_type: str
    severity: str
    title: str
    message: str
    status: str
    metadata: dict[str, Any] | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
