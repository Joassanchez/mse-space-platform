"""Service layer for grain price series.

Implements the cache-first, stale-fallback pattern for MAGyP price data.
"""

import logging
from datetime import date

import httpx
import redis.asyncio as aioredis

from argplant.modules.economy.client import MagypClient
from argplant.modules.economy.models import PriceSeries, PriceSeriesResponse
from argplant.modules.economy.repository import PriceSeriesRepo
from argplant.modules.economy.seed_data import (
    get_port_map,
    get_product_map,
    is_valid_port,
    is_valid_product,
    valid_product_ids,
)
from argplant.shared.cache import get_json, get_stale, set_json

logger = logging.getLogger("argplant.economy")

PRICE_TTL = 3600  # 1 hour


class PriceService:
    """Retrieves grain price series with caching and stale-fallback."""

    def __init__(
        self,
        redis: aioredis.Redis,
        client: MagypClient | None = None,
        repo: PriceSeriesRepo | None = None,
    ) -> None:
        self._redis = redis
        self._client = client or MagypClient()
        self._repo = repo or PriceSeriesRepo()

    async def get(
        self, producto: int, puerto: int, desde: date, hasta: date
    ) -> tuple[PriceSeriesResponse, bool]:
        """Return price series and a stale flag.

        Validates product and port IDs. Returns (response, is_stale).
        Raises ValueError for unknown product/port IDs.
        Raises ServiceUnavailableError when MAGyP is down and no cache exists.
        """
        self._validate_ids(producto, puerto)

        cache_key = _price_cache_key(producto, puerto, desde, hasta)

        # 1. Fresh cache hit
        cached = await get_json(self._redis, cache_key)
        if cached is not None:
            return PriceSeriesResponse(**cached), False

        # 2. Cold cache — fetch from MAGyP
        try:
            raw = await self._client.fetch(producto, puerto, desde, hasta)
            normalised = self._normalise(raw, producto, puerto)
            await set_json(self._redis, cache_key, normalised, ttl=PRICE_TTL)
            return PriceSeriesResponse(**normalised), False
        except httpx.HTTPError:
            logger.warning(
                "MAGyP API call failed for producto=%d puerto=%d range=%s-%s",
                producto,
                puerto,
                desde.isoformat(),
                hasta.isoformat(),
            )

        # 3. API failed — try stale cache
        stale = await get_stale(self._redis, cache_key)
        if stale is not None:
            logger.info(
                "Returning stale price data for producto=%d puerto=%d",
                producto,
                puerto,
            )
            return PriceSeriesResponse(**stale), True

        # 4. Cold cache + API failure → 503
        raise ServiceUnavailableError(
            "MAGyP price service unavailable — no cached data available"
        )

    def _validate_ids(self, producto: int, puerto: int) -> None:
        """Raise ValueError if a product or port ID is not recognised."""
        if not is_valid_product(producto):
            ids = valid_product_ids()
            raise ValueError(
                f"Unknown product ID: {producto}. Valid IDs: {ids}"
            )
        if not is_valid_port(puerto):
            raise ValueError(
                f"Unknown port ID: {puerto}. "
                f"Valid IDs: {sorted(get_port_map().keys())}"
            )

    # -----------------------------------------------------------------------
    # Persistence helpers (used by Phase 5 cron jobs)
    # -----------------------------------------------------------------------

    @staticmethod
    def to_orm_entries(
        raw: dict, producto_id: int, puerto_id: int
    ) -> list[PriceSeries]:
        """Convert MAGyP raw response into ORM entries."""
        entries: list[PriceSeries] = []
        # Build a lookup of date → {minimo, maximo, promedio, modal}
        date_values: dict[str, dict] = {}

        for category, key in [
            ("minimos", "valor"),
            ("maximos", "valor"),
            ("promedios", "valor"),
        ]:
            for item in raw.get(category, []):
                f = item.get("fecha", "")
                v = item.get(key)
                if f not in date_values:
                    date_values[f] = {}
                date_values[f][category.rstrip("s")] = float(v) if v is not None else None

        # Modal is special — single value array
        modal_value = None
        modal_list = raw.get("modal", [])
        if modal_list:
            modal_value = float(modal_list[0].get("valor", 0)) if modal_list[0].get("valor") is not None else None

        for fecha_str, vals in date_values.items():
            try:
                parsed = date.fromisoformat(fecha_str)
            except (ValueError, TypeError):
                continue

            entries.append(
                PriceSeries(
                    producto_id=producto_id,
                    puerto_id=puerto_id,
                    fecha=parsed,
                    minimo=vals.get("minimo"),
                    maximo=vals.get("maximo"),
                    promedio=vals.get("promedio"),
                    modal=modal_value,
                )
            )

        return entries

    # -----------------------------------------------------------------------
    # Normalisation
    # -----------------------------------------------------------------------

    def _normalise(self, raw: dict, producto: int, puerto: int) -> dict:
        """Convert MAGyP raw response into the public API shape."""
        producto_name = get_product_map().get(producto, f"producto_{producto}")
        puerto_name = get_port_map().get(puerto, f"puerto_{puerto}")

        return {
            "producto_id": producto,
            "producto": producto_name,
            "puerto_id": puerto,
            "puerto": puerto_name,
            "minimos": raw.get("minimos", []),
            "maximos": raw.get("maximos", []),
            "promedios": raw.get("promedios", []),
            "modal": raw.get("modal", []),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _price_cache_key(producto: int, puerto: int, desde: date, hasta: date) -> str:
    return f"prices:{producto}:{puerto}:{desde.isoformat()}:{hasta.isoformat()}"


class ServiceUnavailableError(Exception):
    """Raised when MAGyP is unreachable and no stale cache exists."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
