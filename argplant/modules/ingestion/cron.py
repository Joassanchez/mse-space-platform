"""arq cron job functions for scheduled data ingestion.

Each function is idempotent — safe to call multiple times. Failures are
logged but do not crash the worker. Existing caches are preserved on error.
"""

import logging
from datetime import date, timedelta
from typing import Any

from argplant.shared.config import settings
from argplant.shared.database import async_session

logger = logging.getLogger("argplant.ingestion.cron")


# ---------------------------------------------------------------------------
# Weather cache warmup
# ---------------------------------------------------------------------------


async def warmup_weather_cache(ctx: dict[str, Any]) -> None:
    """Fetch current weather and POWER parameters for configured coordinates.

    Reads ``INGESTION_COORDS_LAT`` / ``INGESTION_COORDS_LON`` from settings,
    calls WeatherService and PowerService to populate Redis cache.
    Falls back to OpenWeather free-tier endpoint.

    Idempotent: cache entries are overwritten on each run.
    """
    from argplant.modules.agroclimate.service import (
        PowerService,
        WeatherService,
    )
    from argplant.shared.cache import _get_redis

    redis = await _get_redis()
    lat = settings.INGESTION_COORDS_LAT
    lon = settings.INGESTION_COORDS_LON

    weather = WeatherService(redis)
    power = PowerService(redis)

    try:
        _, stale = await weather.get(lat, lon)
        status = "stale" if stale else "fresh"
        logger.info("Weather cache warmup: lat=%s lon=%s (%s)", lat, lon, status)
    except Exception:
        logger.exception("Weather warmup failed for lat=%s lon=%s", lat, lon)

    today = date.today()
    try:
        _, stale = await power.get(
            lat,
            lon,
            today.replace(day=1).isoformat(),
            today.isoformat(),
            ["temp", "precip", "solar"],
        )
        status = "stale" if stale else "fresh"
        logger.info("POWER cache warmup: lat=%s lon=%s (%s)", lat, lon, status)
    except Exception:
        logger.exception("POWER warmup failed for lat=%s lon=%s", lat, lon)

    await redis.aclose()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Price refresh
# ---------------------------------------------------------------------------


# Products to refresh daily: soy(18) and corn(1) at Rosario(23)
_DAILY_PRICE_PRODUCTS: list[tuple[int, str]] = [(18, "soy"), (1, "corn")]
_DAILY_PRICE_PORTS: list[int] = [23]


async def refresh_prices(ctx: dict[str, Any]) -> None:
    """Fetch recent soy/corn prices from MAGyP and upsert to the database.

    Pulls the last 30 days for each configured product/port pair.
    Uses ``PriceSeriesRepo.upsert`` so existing rows are updated, new rows
    are inserted — safe to call multiple times per day.

    Idempotent: duplicate fetches update the same rows.
    """
    from argplant.modules.economy.client import MagypClient
    from argplant.modules.economy.repository import PriceSeriesRepo
    from argplant.modules.economy.service import PriceService

    today = date.today()
    desde = today - timedelta(days=30)

    client = MagypClient()
    repo = PriceSeriesRepo()

    for producto_id, producto_name in _DAILY_PRICE_PRODUCTS:
        for puerto_id in _DAILY_PRICE_PORTS:
            try:
                raw = await client.fetch(producto_id, puerto_id, desde, today)
                entries = PriceService.to_orm_entries(raw, producto_id, puerto_id)

                async with async_session() as session:
                    count = await repo.upsert(session, entries)
                    await session.commit()

                logger.info(
                    "Price refresh: %s (%d) at port %d — %d rows upserted",
                    producto_name,
                    producto_id,
                    puerto_id,
                    count,
                )
            except Exception:
                logger.exception(
                    "Price refresh failed for %s (%d) at port %d",
                    producto_name,
                    producto_id,
                    puerto_id,
                )


# ---------------------------------------------------------------------------
# Satellite catalog scan
# ---------------------------------------------------------------------------


async def scan_satellite_catalog(ctx: dict[str, Any]) -> None:
    """Search Sentinel-1/2 catalogs for the configured bounding box.

    Queries the last 7 days of Sentinel-1 and Sentinel-2 scenes and
    upserts metadata into the ``satellite_scenes`` table.

    Idempotent: duplicate scenes are updated, not duplicated.
    """
    from argplant.modules.satellite.service import SentinelService

    bbox = settings.INGESTION_BBOX
    today = date.today()
    start = today - timedelta(days=7)

    service = SentinelService()

    for platform in ("sentinel-1", "sentinel-2"):
        try:
            async with async_session() as session:
                results = await service.search_catalog(
                    session,
                    platform=platform,
                    bbox=bbox,
                    start_date=start.isoformat(),
                    end_date=today.isoformat(),
                )
                await session.commit()
            logger.info(
                "Satellite catalog scan: %s — %d scenes found",
                platform,
                len(results),
            )
        except Exception:
            logger.exception(
                "Satellite catalog scan failed for %s (bbox=%s)",
                platform,
                bbox,
            )
