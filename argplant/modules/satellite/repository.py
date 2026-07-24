"""Repository for satellite scene persistence."""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from argplant.modules.satellite.models import SatelliteScene

logger = logging.getLogger("argplant.satellite")


class SatelliteSceneRepo:
    """Async CRUD operations for the satellite_scenes table."""

    @staticmethod
    async def upsert(session: AsyncSession, scene: SatelliteScene) -> SatelliteScene:
        """Insert a scene or update it on scene_id conflict. Returns the ORM instance."""
        existing = await SatelliteSceneRepo.find_by_scene_id(session, scene.scene_id)

        if existing is not None:
            existing.platform = scene.platform
            existing.bbox = scene.bbox
            existing.acquisition_date = scene.acquisition_date
            existing.cloud_cover = scene.cloud_cover
            existing.metadata = scene.metadata
            existing.file_path = scene.file_path
            await session.flush()
            return existing

        session.add(scene)
        await session.flush()
        return scene

    @staticmethod
    async def find_by_scene_id(
        session: AsyncSession, scene_id: str
    ) -> SatelliteScene | None:
        """Return a single scene by its unique scene_id."""
        stmt = select(SatelliteScene).where(SatelliteScene.scene_id == scene_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def find_by_bbox(
        session: AsyncSession,
        bbox: list[float],
        platform: str,
        since: datetime,
        until: datetime,
    ) -> list[SatelliteScene]:
        """Return scenes for a platform within a date range.

        Note: spatial filtering on bbox is approximate without PostGIS.
        The caller should further filter by exact bbox intersection if needed.
        """
        stmt = (
            select(SatelliteScene)
            .where(
                SatelliteScene.platform == platform,
                SatelliteScene.acquisition_date >= since,
                SatelliteScene.acquisition_date <= until,
            )
            .order_by(SatelliteScene.acquisition_date.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_file_path(
        session: AsyncSession,
        scene_id: str,
        file_path: str,
    ) -> SatelliteScene | None:
        """Update the file_path on an existing scene. Returns the updated instance."""
        scene = await SatelliteSceneRepo.find_by_scene_id(session, scene_id)
        if scene is None:
            return None
        scene.file_path = file_path
        await session.flush()
        return scene
