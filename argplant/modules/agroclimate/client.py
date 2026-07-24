"""HTTP clients for OpenWeather and NASA POWER APIs.

Both clients use httpx.AsyncClient with tenacity retry on transient failures.
"""

from collections.abc import Mapping
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from argplant.shared.config import settings

# ---------------------------------------------------------------------------
# Retry policy: 3 attempts, exponential backoff 1s → 2s → 4s, only on 5xx
# ---------------------------------------------------------------------------

_RETRY_POLICY = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=1, max=4),
    "retry": retry_if_exception_type(httpx.HTTPStatusError),
}

# ---------------------------------------------------------------------------
# OpenWeather
# ---------------------------------------------------------------------------

_OWM_BASE = "https://api.openweathermap.org"

_OWM_WEATHER_PARAMS: Mapping[str, str] = {
    "exclude": "minutely,alerts",
    "units": "metric",
}


class OpenWeatherClient:
    """Async HTTP client for OpenWeather One Call / Current Weather APIs."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=_OWM_BASE, timeout=settings.OPENWEATHER_TIMEOUT
            )
        return self._client

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    @retry(**_RETRY_POLICY)
    async def current(self, lat: float, lon: float) -> dict[str, Any]:
        """Fetch current weather for a single lat/lon pair.

        Uses OpenWeather's free-tier /data/2.5/weather endpoint.
        """
        client = await self._ensure_client()
        params: dict[str, str | float] = {
            "lat": lat,
            "lon": lon,
            "appid": settings.OPENWEATHER_API_KEY,
            **_OWM_WEATHER_PARAMS,
        }
        response = await client.get("/data/2.5/weather", params=params)
        response.raise_for_status()
        return response.json()


# ---------------------------------------------------------------------------
# NASA POWER
# ---------------------------------------------------------------------------

_POWER_BASE = "https://power.larc.nasa.gov"

# Canonical parameter names accepted by the POWER REST API.
# Maps user-facing short names → POWER parameter codes.
_PARAMETER_MAP: dict[str, str] = {
    "solar": "ALLSKY_SFC_SW_DWN",
    "temp": "T2M",
    "precip": "PRECTOTCORR",
    "humidity": "RH2M",
    "wind": "WS2M",
}

# Human-readable units for each parameter.
_UNITS: dict[str, str] = {
    "ALLSKY_SFC_SW_DWN": "MJ/m²/day",
    "T2M": "°C",
    "PRECTOTCORR": "mm",
    "RH2M": "%",
    "WS2M": "m/s",
}


def _expand_params(requested: list[str]) -> list[str]:
    """Translate user-facing short names to POWER parameter codes.

    Raises ValueError if an unrecognized parameter name is provided.
    """
    expanded: list[str] = []
    for name in requested:
        code = _PARAMETER_MAP.get(name.strip().lower())
        if code is None:
            raise ValueError(
                f"Unknown parameter '{name}'. "
                f"Valid options: {', '.join(sorted(_PARAMETER_MAP))}"
            )
        expanded.append(code)
    return expanded


def _build_unit_map(requested: list[str]) -> dict[str, str]:
    """Build a human-readable unit map for the requested parameter set."""
    expanded = _expand_params(requested)
    return {code: _UNITS[code] for code in expanded}


class NasaPowerClient:
    """Async HTTP client for the NASA POWER REST API."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=_POWER_BASE, timeout=settings.POWER_TIMEOUT
            )
        return self._client

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    @retry(**_RETRY_POLICY)
    async def daily(
        self,
        lat: float,
        lon: float,
        start: str,  # YYYYMMDD
        end: str,  # YYYYMMDD
        params: list[str],
    ) -> dict[str, Any]:
        """Fetch daily agroclimatic parameters for a date range.

        Uses POWER's temporal/daily/point endpoint with community=AG.
        """
        client = await self._ensure_client()
        codes = _expand_params(params)
        query: dict[str, str | float] = {
            "latitude": lat,
            "longitude": lon,
            "start": start,
            "end": end,
            "parameters": ",".join(codes),
            "community": "AG",
            "format": "JSON",
        }
        response = await client.get("/api/temporal/daily/point", params=query)
        response.raise_for_status()
        return response.json()
