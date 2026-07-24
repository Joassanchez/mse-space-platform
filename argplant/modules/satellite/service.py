"""Service layer for SMAP and Sentinel satellite data.

Delegates search to external clients, normalises responses, and persists
metadata to the database. Sentinel downloads are enqueued as arq background jobs.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from argplant.modules.satellite.client import CdseClient, EarthdataClient
from argplant.modules.satellite.models import (
    SatelliteScene,
    SentinelSceneMeta,
    SmSceneMeta,
)
from argplant.modules.satellite.repository import SatelliteSceneRepo
from argplant.shared.config import settings
from argplant.shared.storage import StorageBackend

logger = logging.getLogger("argplant.satellite")


# ---------------------------------------------------------------------------
# SMAP normalisation
# ---------------------------------------------------------------------------


def _parse_bbox_from_cmr(entry: dict[str, Any]) -> list[float]:
    """Extract a bounding box from a CMR granule entry.

    CMR returns spatial as either ``boxes`` or ``polygons``.
    """
    boxes = entry.get("boxes", [])
    if boxes:
        # boxes are strings like "-180 -90 180 90"
        parts = boxes[0].split()
        if len(parts) == 4:
            return [float(p) for p in parts]

    # Fallback: use the configured ingestion bbox
    return [float(x) for x in settings.INGESTION_BBOX.split(",")]


def _normalise_smap_granule(entry: dict[str, Any]) -> SmSceneMeta:
    """Convert a raw CMR granule entry to an SmSceneMeta schema."""
    granule_ur = entry.get("granule_ur", entry.get("producer_granule_id", "unknown"))
    time_start = entry.get("time_start", "")

    # Parse ISO date
    try:
        acq_date = datetime.fromisoformat(time_start.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        acq_date = datetime.now(timezone.utc)

    return SmSceneMeta(
        scene_id=granule_ur,
        acquisition_date=acq_date,
        granule_ur=granule_ur,
        platform="smap",
        bbox=_parse_bbox_from_cmr(entry),
    )


# ---------------------------------------------------------------------------
# Sentinel normalisation
# ---------------------------------------------------------------------------


def _parse_bbox_from_stac(feature: dict[str, Any]) -> list[float]:
    """Extract bounding box from a STAC item."""
    bbox = feature.get("bbox")
    if bbox and len(bbox) == 4:
        return [float(v) for v in bbox]
    return [float(x) for x in settings.INGESTION_BBOX.split(",")]


def _normalise_sentinel_feature(feature: dict[str, Any]) -> SentinelSceneMeta:
    """Convert a raw STAC Item to a SentinelSceneMeta schema."""
    props = feature.get("properties", {})
    assets = feature.get("assets", {})
    feat_id = feature.get("id", "unknown")

    # Parse acquisition datetime
    dt_str = props.get("datetime", "")
    try:
        acq_date = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        acq_date = datetime.now(timezone.utc)

    cloud_cover = props.get("eo:cloud_cover")
    platform = props.get("platform", "unknown")

    # Thumbnail URL from assets
    thumbnail_url: str | None = None
    thumb_asset = assets.get("thumbnail")
    if thumb_asset:
        thumbnail_url = thumb_asset.get("href")

    return SentinelSceneMeta(
        scene_id=feat_id,
        acquisition_date=acq_date,
        cloud_cover=float(cloud_cover) if cloud_cover is not None else None,
        thumbnail_url=thumbnail_url,
        platform=platform,
        bbox=_parse_bbox_from_stac(feature),
    )


# ---------------------------------------------------------------------------
# SmapService
# ---------------------------------------------------------------------------


class SmapService:
    """Search SMAP soil moisture granules and persist metadata."""

    def __init__(
        self,
        earthdata: EarthdataClient | None = None,
        repo: SatelliteSceneRepo | None = None,
    ) -> None:
        self._earthdata = earthdata or EarthdataClient()
        self._repo = repo or SatelliteSceneRepo()

    async def search(
        self,
        session: AsyncSession,
        bbox: str,
        start_date: str,
        end_date: str,
    ) -> list[SmSceneMeta]:
        """Search SMAP L3 soil moisture granules.

        Searches CMR, normalises results, and upserts metadata to the DB.
        """
        try:
            raw_entries = await self._earthdata.search_smap(bbox, start_date, end_date)
        except httpx.HTTPError as exc:
            logger.error("Earthdata SMAP search failed: %s", exc)
            raise

        results: list[SmSceneMeta] = []
        for entry in raw_entries:
            meta = _normalise_smap_granule(entry)
            results.append(meta)

            # Persist metadata to DB
            scene = SatelliteScene(
                scene_id=meta.scene_id,
                platform="smap",
                bbox=meta.bbox,
                acquisition_date=meta.acquisition_date,
                cloud_cover=None,
                metadata=entry,
            )
            await self._repo.upsert(session, scene)

        return results


# ---------------------------------------------------------------------------
# SentinelService
# ---------------------------------------------------------------------------


class SentinelService:
    """Search Sentinel catalogs and enqueue async downloads."""

    def __init__(
        self,
        cdse: CdseClient | None = None,
        repo: SatelliteSceneRepo | None = None,
        storage: StorageBackend | None = None,
    ) -> None:
        self._cdse = cdse or CdseClient()
        self._repo = repo or SatelliteSceneRepo()
        self._storage = storage

    async def search_catalog(
        self,
        session: AsyncSession,
        platform: str,
        bbox: str,
        start_date: str,
        end_date: str,
        max_cloud: float | None = None,
    ) -> list[SentinelSceneMeta]:
        """Search Sentinel-1/2 scenes via CDSE STAC API.

        Normalises results and persists metadata to the DB.
        """
        try:
            raw_features = await self._cdse.search_sentinel(
                bbox, start_date, end_date, platform, max_cloud
            )
        except httpx.HTTPError as exc:
            logger.error("CDSE Sentinel search failed: %s", exc)
            raise

        results: list[SentinelSceneMeta] = []
        for feature in raw_features:
            meta = _normalise_sentinel_feature(feature)
            results.append(meta)

            # Persist metadata to DB
            scene = SatelliteScene(
                scene_id=meta.scene_id,
                platform=platform,
                bbox=meta.bbox,
                acquisition_date=meta.acquisition_date,
                cloud_cover=meta.cloud_cover,
                metadata=feature,
            )
            await self._repo.upsert(session, scene)

        return results

    async def validate_scene(
        self,
        session: AsyncSession,
        scene_id: str,
    ) -> SatelliteScene | None:
        """Check that a scene exists in the database. Returns the scene or None."""
        return await self._repo.find_by_scene_id(session, scene_id)
