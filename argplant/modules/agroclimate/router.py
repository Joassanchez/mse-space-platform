"""FastAPI router for the agroclimate module.

Exposes weather and NASA POWER agroclimatic parameters endpoints.
Rate limiting is handled by shared middleware — no per-route config needed.
"""

import logging
from datetime import date

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, Query, Response

from argplant.modules.agroclimate.service import (
    PowerService,
    ServiceUnavailableError,
    WeatherService,
)
from argplant.shared.cache import _get_redis
from argplant.shared.middleware import add_stale_header

logger = logging.getLogger("argplant.agroclimate")

router = APIRouter(tags=["agroclimate"])


# ---------------------------------------------------------------------------
# Dependency helpers — creates a fresh Redis connection per request.
# In production you would pool / reuse, but this matches the existing pattern.
# ---------------------------------------------------------------------------


async def _get_weather_service() -> WeatherService:
    redis = await _get_redis()
    return WeatherService(redis)


async def _get_power_service() -> PowerService:
    redis = await _get_redis()
    return PowerService(redis)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/weather")
async def get_weather(
    response: Response,
    lat: float = Query(..., description="Latitude", ge=-90, le=90),
    lon: float = Query(..., description="Longitude", ge=-180, le=180),
) -> dict:
    """Return current weather conditions for the given coordinates.

    Responses include an X-Cache header (HIT/MISS) and, when stale data was
    served, an X-Stale: true header.
    """
    service = await _get_weather_service()
    try:
        result, is_stale = await service.get(lat, lon)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if is_stale:
        add_stale_header(response)
        response.headers["X-Cache"] = "STALE"
    else:
        response.headers["X-Cache"] = "HIT"

    return result.model_dump(mode="json")


@router.get("/power")
async def get_power(
    response: Response,
    lat: float = Query(..., description="Latitude", ge=-90, le=90),
    lon: float = Query(..., description="Longitude", ge=-180, le=180),
    start_date: date = Query(..., description="Start date (inclusive)"),
    end_date: date = Query(..., description="End date (inclusive)"),
    parameters: str = Query(
        ...,
        description="Comma-separated parameters: solar,temp,precip,humidity,wind",
    ),
) -> dict:
    """Return NASA POWER agroclimatic parameters for a date range.

    Parameters are requested as a comma-separated string and mapped to
    POWER's internal codes (e.g. 'solar' → 'ALLSKY_SFC_SW_DWN').
    """
    param_list = [p.strip() for p in parameters.split(",") if p.strip()]
    if not param_list:
        raise HTTPException(status_code=422, detail="At least one parameter is required")

    start = start_date.strftime("%Y%m%d")
    end = end_date.strftime("%Y%m%d")

    service = await _get_power_service()
    try:
        result, is_stale = await service.get(lat, lon, start, end, param_list)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if is_stale:
        add_stale_header(response)
        response.headers["X-Cache"] = "STALE"
    else:
        response.headers["X-Cache"] = "HIT"

    return result.model_dump(mode="json")
