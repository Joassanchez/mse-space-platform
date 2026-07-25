"""FastAPI router for the economy module.

Exposes the daily grain price series endpoint backed by MAGyP data.
"""

import logging
from datetime import date

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, Query, Response

from argplant.modules.economy.service import PriceService, ServiceUnavailableError
from argplant.shared.cache import _get_redis
from argplant.shared.config import settings
from argplant.shared.middleware import add_stale_header

logger = logging.getLogger("argplant.economy")

router = APIRouter(tags=["economy"])


async def _get_price_service() -> PriceService:
    redis = await _get_redis()
    return PriceService(redis)


@router.get("/prices")
async def get_prices(
    response: Response,
    producto: int = Query(..., description="MAGyP numeric product ID (e.g. 18 = soy)"),
    puerto: int = Query(..., description="MAGyP numeric port ID (e.g. 23 = Rosario)"),
    desde: date = Query(..., description="Start date inclusive (YYYY-MM-DD)"),
    hasta: date = Query(..., description="End date inclusive (YYYY-MM-DD)"),
) -> dict:
    """Return daily grain price series from MAGyP Monitor de Granos.

    Data is cached in Redis (TTL 1h). On MAGyP failure, stale cache is
    returned with X-Stale: true. On cold cache + failure, returns 503.
    """
    if not settings.ENABLE_MAGYP:
        raise HTTPException(status_code=503, detail="MAGyP source is disabled (ENABLE_MAGYP=False)")

    service = await _get_price_service()
    try:
        result, is_stale = await service.get(producto, puerto, desde, hasta)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if is_stale:
        add_stale_header(response)
        response.headers["X-Cache"] = "STALE"
    else:
        response.headers["X-Cache"] = "HIT"

    return result.model_dump(mode="json")
