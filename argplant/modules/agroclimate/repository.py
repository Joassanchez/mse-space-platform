"""Repository for weather snapshot persistence."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from argplant.modules.agroclimate.models import WeatherSnapshot


class WeatherSnapshotRepo:
    """Async CRUD operations for the weather_snapshots table."""

    @staticmethod
    async def upsert(
        session: AsyncSession,
        location_id: uuid.UUID | None,
        temp: float | None,
        humidity: int | None,
        wind_speed: float | None,
        conditions: str | None,
        source: str,
        raw_data: dict,
        captured_at: datetime,
    ) -> WeatherSnapshot:
        """Insert a new weather snapshot and return the ORM instance."""
        snapshot = WeatherSnapshot(
            location_id=location_id,
            temp=temp,
            humidity=humidity,
            wind_speed=wind_speed,
            conditions=conditions,
            source=source,
            data=raw_data,
            captured_at=captured_at,
        )
        session.add(snapshot)
        await session.flush()
        return snapshot

    @staticmethod
    async def get_latest(
        session: AsyncSession, location_id: uuid.UUID
    ) -> WeatherSnapshot | None:
        """Return the most recent snapshot for a location."""
        stmt = (
            select(WeatherSnapshot)
            .where(WeatherSnapshot.location_id == location_id)
            .order_by(WeatherSnapshot.captured_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_since(
        session: AsyncSession,
        location_id: uuid.UUID,
        since: datetime,
    ) -> list[WeatherSnapshot]:
        """Return snapshots for a location captured after a point in time."""
        stmt = (
            select(WeatherSnapshot)
            .where(
                WeatherSnapshot.location_id == location_id,
                WeatherSnapshot.captured_at >= since,
            )
            .order_by(WeatherSnapshot.captured_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
