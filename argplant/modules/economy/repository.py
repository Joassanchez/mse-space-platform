"""Repository for price series persistence."""

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from argplant.modules.economy.models import PriceSeries

logger = logging.getLogger("argplant.economy")


class PriceSeriesRepo:
    """Async CRUD operations for the price_series table."""

    @staticmethod
    async def upsert(
        session: AsyncSession,
        entries: list[PriceSeries],
    ) -> int:
        """Insert or update price series entries.

        Uses the UNIQUE(producto_id, puerto_id, fecha) constraint to
        determine whether to insert or update each row.

        Returns the number of affected rows.
        """
        count = 0
        for entry in entries:
            existing = await PriceSeriesRepo._find_existing(
                session, entry.producto_id, entry.puerto_id, entry.fecha
            )
            if existing is not None:
                existing.minimo = entry.minimo
                existing.maximo = entry.maximo
                existing.promedio = entry.promedio
                existing.modal = entry.modal
            else:
                session.add(entry)
            count += 1

        await session.flush()
        return count

    @staticmethod
    async def find(
        session: AsyncSession,
        producto_id: int,
        puerto_id: int,
        desde: date,
        hasta: date,
    ) -> list[PriceSeries]:
        """Return price_series rows within a date range, ordered by fecha."""
        stmt = (
            select(PriceSeries)
            .where(
                PriceSeries.producto_id == producto_id,
                PriceSeries.puerto_id == puerto_id,
                PriceSeries.fecha >= desde,
                PriceSeries.fecha <= hasta,
            )
            .order_by(PriceSeries.fecha)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def _find_existing(
        session: AsyncSession,
        producto_id: int,
        puerto_id: int,
        fecha: date,
    ) -> PriceSeries | None:
        """Return an existing row matching the unique constraint, or None."""
        stmt = select(PriceSeries).where(
            PriceSeries.producto_id == producto_id,
            PriceSeries.puerto_id == puerto_id,
            PriceSeries.fecha == fecha,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
