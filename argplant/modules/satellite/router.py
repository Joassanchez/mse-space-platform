"""FastAPI router for the satellite module.

Exposes SMAP metadata search, Sentinel catalog search, and async download endpoints.
"""

import logging
from datetime import date

import arq
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from argplant.modules.satellite.models import (
    DownloadResponse,
    SentinelSceneMeta,
    SmSceneMeta,
)
from argplant.modules.satellite.service import SentinelService, SmapService
from argplant.shared.config import settings
from argplant.shared.database import get_session

logger = logging.getLogger("argplant.satellite")

router = APIRouter(tags=["satellite"])

# arq pool — lazily initialised. Phase 5 WorkerSettings will replace the
# Redis URL with the production configuration.
_arq_pool: arq.ArqRedis | None = None


async def _get_arq() -> arq.ArqRedis:
    """Return a shared arq Redis connection pool for enqueuing jobs."""
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await arq.create_pool(
            RedisSettings().from_dsn(settings.REDIS_URL)
        )
    return _arq_pool


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


async def _get_smap_service() -> SmapService:
    return SmapService()


async def _get_sentinel_service() -> SentinelService:
    return SentinelService()


# ---------------------------------------------------------------------------
# SMAP
# ---------------------------------------------------------------------------


@router.get("/smap", response_model=list[SmSceneMeta])
async def search_smap(
    bbox: str = Query(
        ...,
        description="Bounding box as min_lon,min_lat,max_lon,max_lat (e.g. -61,-34,-60,-33)",
    ),
    start_date: date = Query(..., description="Start date (inclusive)"),
    end_date: date = Query(..., description="End date (inclusive)"),
    session: AsyncSession = Depends(get_session),
) -> list[SmSceneMeta]:
    """Search SMAP L3 soil moisture granules for a bounding box and date range."""
    service = await _get_smap_service()
    try:
        results = await service.search(
            session,
            bbox=bbox,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )
        await session.commit()
        return results
    except Exception as exc:
        logger.exception("SMAP search failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Sentinel
# ---------------------------------------------------------------------------


@router.get("/sentinel/search", response_model=list[SentinelSceneMeta])
async def search_sentinel(
    platform: str = Query(
        ...,
        description="Satellite platform: sentinel-1 or sentinel-2",
    ),
    bbox: str = Query(
        ...,
        description="Bounding box as min_lon,min_lat,max_lon,max_lat",
    ),
    start: date = Query(..., description="Start date (inclusive)"),
    end: date = Query(..., description="End date (inclusive)"),
    max_cloud: float | None = Query(
        None,
        alias="max_cloud_cover",
        description="Maximum cloud cover percentage (Sentinel-2 only, 0–100)",
    ),
    session: AsyncSession = Depends(get_session),
) -> list[SentinelSceneMeta]:
    """Search Sentinel-1/2 scenes via the CDSE STAC catalog."""
    if platform not in ("sentinel-1", "sentinel-2"):
        raise HTTPException(
            status_code=400,
            detail="platform must be 'sentinel-1' or 'sentinel-2'",
        )

    service = await _get_sentinel_service()
    try:
        results = await service.search_catalog(
            session,
            platform=platform,
            bbox=bbox,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            max_cloud=max_cloud,
        )
        await session.commit()
        return results
    except Exception as exc:
        logger.exception("Sentinel catalog search failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/sentinel/{scene_id}/download",
    response_model=DownloadResponse,
    status_code=202,
)
async def enqueue_download(
    scene_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Enqueue an async download job for a Sentinel scene.

    Returns a 202 with the job ID for status tracking.
    Returns 404 if the scene has not been previously catalogued.
    """
    service = await _get_sentinel_service()
    scene = await service.validate_scene(session, scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail=f"Scene '{scene_id}' not found")

    # Enqueue the download as an arq background job
    try:
        arq_redis = await _get_arq()
        job = await arq_redis.enqueue_job("download_sentinel", scene_id)
        result = {"job_id": job.job_id, "status": "queued"}
        return result
    except Exception as exc:
        logger.exception("Failed to enqueue download job for %s", scene_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
