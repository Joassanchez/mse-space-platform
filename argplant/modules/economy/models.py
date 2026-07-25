"""Pydantic schemas and SQLAlchemy ORM model for the economy module."""

import uuid
from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Date, DateTime, Double, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from argplant.shared.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------


class PriceSeries(Base):
    """Daily grain price series from MAGyP Monitor de Granos."""

    __tablename__ = "price_series"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    producto_id: Mapped[int] = mapped_column(Integer, nullable=False)
    puerto_id: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    minimo: Mapped[float | None] = mapped_column(Double, nullable=True)
    maximo: Mapped[float | None] = mapped_column(Double, nullable=True)
    promedio: Mapped[float | None] = mapped_column(Double, nullable=True)
    modal: Mapped[float | None] = mapped_column(Double, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class PriceEntry(BaseModel):
    """A single daily price data point."""

    fecha: date
    valor: float | None


class PriceSeriesResponse(BaseModel):
    """Public API response for the prices endpoint."""

    producto_id: int
    producto: str
    puerto_id: int
    puerto: str
    minimos: list[dict[str, Any]]
    maximos: list[dict[str, Any]]
    promedios: list[dict[str, Any]]
    modal: list[dict[str, Any]]


class PriceQuery(BaseModel):
    """Validated query parameters for the prices endpoint."""

    producto: int
    puerto: int
    desde: date
    hasta: date
