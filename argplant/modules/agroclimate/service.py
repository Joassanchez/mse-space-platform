"""Service layer for weather and agroclimatic parameters.

Implements the cache-first, stale-fallback pattern described in the design.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
import redis.asyncio as aioredis

from argplant.modules.agroclimate.client import (
    NasaPowerClient,
    OpenWeatherClient,
    _build_unit_map,
    _expand_params,
)
from argplant.modules.agroclimate.models import PowerParameter, PowerResponse, WeatherResponse
from argplant.modules.agroclimate.repository import WeatherSnapshotRepo
from argplant.shared.cache import delete, get_json, get_stale, set_json

logger = logging.getLogger("argplant.agroclimate")

# Cache TTLs (seconds)
WEATHER_TTL = 3600  # 1 hour
POWER_TTL = 86400  # 24 hours

# ---------------------------------------------------------------------------
# Cache key helpers
# ---------------------------------------------------------------------------


def _weather_cache_key(lat: float, lon: float) -> str:
    return f"weather:{lat}:{lon}"


def _power_cache_key(lat: float, lon: float, start: str, end: str, params: list[str]) -> str:
    params_key = ",".join(sorted(params))
    return f"power:{lat}:{lon}:{start}:{end}:{params_key}"


# ---------------------------------------------------------------------------
# Weather normalisation
# ---------------------------------------------------------------------------


def _normalise_openweather(raw: dict[str, Any], lat: float, lon: float) -> dict[str, Any]:
    """Extract the fields we expose from an OpenWeather response."""
    main = raw.get("main", {})
    weather_list = raw.get("weather", [])
    wind = raw.get("wind", {})

    return {
        "lat": lat,
        "lon": lon,
        "temp": main.get("temp"),
        "humidity": main.get("humidity"),
        "wind_speed": wind.get("speed"),
        "conditions": weather_list[0].get("description") if weather_list else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _normalise_power(
    raw: dict[str, Any], lat: float, lon: float, start: str, end: str, params: list[str]
) -> dict[str, Any]:
    """Extract daily parameter arrays from a NASA POWER response."""
    properties = raw.get("properties", {})
    parameter_data = properties.get("parameter", {})

    expanded = _expand_params(params)
    unit_map = _build_unit_map(params)

    param_series: list[dict[str, Any]] = []
    for code in expanded:
        values: list[float | None] = []
        raw_values = parameter_data.get(code, {})
        if isinstance(raw_values, dict):
            # POWER returns keys like "YYYYMMDD"
            for _key, val in sorted(raw_values.items()):
                # -999 indicates missing data
                values.append(None if val == -999 else float(val))
        param_series.append({"name": code, "values": values})

    return {
        "lat": lat,
        "lon": lon,
        "start_date": start,
        "end_date": end,
        "parameters": param_series,
        "unit_map": unit_map,
    }


# ---------------------------------------------------------------------------
# WeatherService
# ---------------------------------------------------------------------------


class WeatherService:
    """Retrieves current weather with caching and stale-fallback."""

    def __init__(
        self,
        redis: aioredis.Redis,
        owm_client: OpenWeatherClient | None = None,
        repo: WeatherSnapshotRepo | None = None,
    ) -> None:
        self._redis = redis
        self._owm = owm_client or OpenWeatherClient()
        self._repo = repo or WeatherSnapshotRepo()

    async def get(self, lat: float, lon: float) -> tuple[WeatherResponse, bool]:
        """Return current weather and a stale flag.

        Returns (response, is_stale). is_stale is True when the data came
        from the stale-cache fallback path.
        """
        cache_key = _weather_cache_key(lat, lon)

        # 1. Fresh cache hit
        cached = await get_json(self._redis, cache_key)
        if cached is not None:
            return WeatherResponse(**cached), False

        # 2. Cold cache — fetch from external API
        try:
            raw = await self._owm.current(lat, lon)
            normalised = _normalise_openweather(raw, lat, lon)
            await set_json(self._redis, cache_key, normalised, ttl=WEATHER_TTL)
            return WeatherResponse(**normalised), False
        except httpx.HTTPError:
            logger.warning("OpenWeather API call failed for lat=%s lon=%s", lat, lon)

        # 3. API failed — try stale cache
        stale = await get_stale(self._redis, cache_key)
        if stale is not None:
            logger.info("Returning stale weather data for lat=%s lon=%s", lat, lon)
            return WeatherResponse(**stale), True

        # 4. Cold cache + API failure → 503
        raise _service_unavailable("weather")


# ---------------------------------------------------------------------------
# PowerService
# ---------------------------------------------------------------------------


class PowerService:
    """Retrieves NASA POWER agroclimatic parameters with caching and stale-fallback."""

    def __init__(
        self,
        redis: aioredis.Redis,
        power_client: NasaPowerClient | None = None,
        repo: WeatherSnapshotRepo | None = None,
    ) -> None:
        self._redis = redis
        self._power = power_client or NasaPowerClient()
        self._repo = repo or WeatherSnapshotRepo()

    async def get(
        self, lat: float, lon: float, start: str, end: str, params: list[str]
    ) -> tuple[PowerResponse, bool]:
        """Return POWER parameters and a stale flag."""
        cache_key = _power_cache_key(lat, lon, start, end, params)

        # 1. Fresh cache hit
        cached = await get_json(self._redis, cache_key)
        if cached is not None:
            return PowerResponse(**cached), False

        # 2. Cold cache — fetch from NASA POWER
        try:
            raw = await self._power.daily(lat, lon, start, end, params)
            normalised = _normalise_power(raw, lat, lon, start, end, params)
            await set_json(self._redis, cache_key, normalised, ttl=POWER_TTL)
            return PowerResponse(**normalised), False
        except httpx.HTTPError:
            logger.warning(
                "NASA POWER API call failed for lat=%s lon=%s date=%s-%s",
                lat, lon, start, end,
            )

        # 3. API failed — try stale cache
        stale = await get_stale(self._redis, cache_key)
        if stale is not None:
            logger.info(
                "Returning stale POWER data for lat=%s lon=%s date=%s-%s",
                lat, lon, start, end,
            )
            return PowerResponse(**stale), True

        # 4. Cold cache + API failure → 503
        raise _service_unavailable("POWER")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class ServiceUnavailableError(Exception):
    """Raised when a service cannot fetch fresh data and no stale cache exists."""

    def __init__(self, service: str) -> None:
        super().__init__(f"{service} service unavailable — no cached data available")
        self.service = service


def _service_unavailable(service: str) -> ServiceUnavailableError:
    return ServiceUnavailableError(service)
