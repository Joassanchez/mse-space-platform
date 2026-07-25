"""Unit tests for agroclimate service layer.

Tests WeatherService and PowerService with mocked external clients and
fakeredis. Covers cache hit, cache miss, stale fallback, and cold-start
failure paths.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from argplant.modules.agroclimate.models import PowerParameter, PowerResponse, WeatherResponse
from argplant.modules.agroclimate.service import (
    POWER_TTL,
    WEATHER_TTL,
    PowerService,
    ServiceUnavailableError,
    WeatherService,
)

# ---------------------------------------------------------------------------
# Shared mock data
# ---------------------------------------------------------------------------

MOCK_OWM_RAW = {
    "coord": {"lon": -60.57, "lat": -33.89},
    "weather": [{"id": 800, "main": "Clear", "description": "clear sky"}],
    "main": {"temp": 25.3, "humidity": 55},
    "wind": {"speed": 3.6},
}

MOCK_POWER_RAW = {
    "geometry": {"type": "Point", "coordinates": [-60.57, -33.89]},
    "properties": {
        "parameter": {
            "T2M": {"20260101": 25.0, "20260102": 26.1},
            "PRECTOTCORR": {"20260101": 0.0, "20260102": 2.3},
        }
    },
}

MOCK_POWER_MISSING = {
    "geometry": {"type": "Point", "coordinates": [-60.57, -33.89]},
    "properties": {
        "parameter": {
            "T2M": {"20260101": 25.0, "20260102": -999},
        }
    },
}


# ---------------------------------------------------------------------------
# WeatherService
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weather_cache_miss_fetches_from_api(test_redis):
    """Cold cache → API call → returns fresh data."""
    with patch(
        "argplant.modules.agroclimate.service.OpenWeatherClient.current",
        new_callable=AsyncMock,
    ) as mock_current:
        mock_current.return_value = MOCK_OWM_RAW

        service = WeatherService(test_redis)
        result, is_stale = await service.get(-33.89, -60.57)

        assert isinstance(result, WeatherResponse)
        assert result.temp == 25.3
        assert result.humidity == 55
        assert result.wind_speed == 3.6
        assert result.conditions == "clear sky"
        assert is_stale is False
        mock_current.assert_called_once_with(-33.89, -60.57)


@pytest.mark.asyncio
async def test_weather_cache_hit_skips_api(test_redis):
    """Warm cache → no API call → returns cached data."""
    with patch(
        "argplant.modules.agroclimate.service.OpenWeatherClient.current",
        new_callable=AsyncMock,
    ) as mock_current:
        mock_current.return_value = MOCK_OWM_RAW

        service = WeatherService(test_redis)

        # First call: cache miss → API call
        r1, _ = await service.get(-33.89, -60.57)
        assert mock_current.call_count == 1

        # Second call: cache hit → no API call
        r2, _ = await service.get(-33.89, -60.57)
        assert mock_current.call_count == 1
        assert r2.temp == r1.temp


@pytest.mark.asyncio
async def test_weather_api_fail_returns_stale(test_redis):
    """API fails → stale cache → returns with is_stale=True."""
    with patch(
        "argplant.modules.agroclimate.service.OpenWeatherClient.current",
        new_callable=AsyncMock,
    ) as mock_current:
        # First: successful call to populate cache
        mock_current.return_value = MOCK_OWM_RAW
        service = WeatherService(test_redis)
        await service.get(-33.89, -60.57)

        # Delete fresh key to simulate expiry, keep stale
        from argplant.modules.agroclimate.service import _weather_cache_key
        cache_key = _weather_cache_key(-33.89, -60.57)
        await test_redis.delete(cache_key)

        # Second: API fails
        mock_current.side_effect = httpx.ConnectError("down")

        result, is_stale = await service.get(-33.89, -60.57)
        assert result.temp == 25.3
        assert is_stale is True


@pytest.mark.asyncio
async def test_weather_cold_cache_api_fail_raises(test_redis):
    """Cold cache + API failure → ServiceUnavailableError."""
    with patch(
        "argplant.modules.agroclimate.service.OpenWeatherClient.current",
        new_callable=AsyncMock,
    ) as mock_current:
        mock_current.side_effect = httpx.ConnectError("down")

        service = WeatherService(test_redis)
        with pytest.raises(ServiceUnavailableError) as exc_info:
            await service.get(-34.0, -61.0)
        assert "weather" in str(exc_info.value)


# ---------------------------------------------------------------------------
# PowerService
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_power_cache_miss_fetches(test_redis):
    """Cold cache → NASA POWER → returns parameters."""
    with patch(
        "argplant.modules.agroclimate.service.NasaPowerClient.daily",
        new_callable=AsyncMock,
    ) as mock_daily:
        mock_daily.return_value = MOCK_POWER_RAW

        service = PowerService(test_redis)
        result, is_stale = await service.get(
            -33.89, -60.57, "20260101", "20260102", ["temp", "precip"]
        )

        assert isinstance(result, PowerResponse)
        assert result.lat == -33.89
        assert len(result.parameters) == 2
        assert result.unit_map["T2M"] == "°C"
        assert result.unit_map["PRECTOTCORR"] == "mm"
        assert is_stale is False


@pytest.mark.asyncio
async def test_power_cache_hit_skips_api(test_redis):
    """Warm cache → no API call."""
    with patch(
        "argplant.modules.agroclimate.service.NasaPowerClient.daily",
        new_callable=AsyncMock,
    ) as mock_daily:
        mock_daily.return_value = MOCK_POWER_RAW

        service = PowerService(test_redis)
        await service.get(-33.89, -60.57, "20260101", "20260102", ["temp"])
        assert mock_daily.call_count == 1

        await service.get(-33.89, -60.57, "20260101", "20260102", ["temp"])
        assert mock_daily.call_count == 1  # second call was cached


@pytest.mark.asyncio
async def test_power_handles_missing_values(test_redis):
    """-999 values in POWER response are converted to None."""
    with patch(
        "argplant.modules.agroclimate.service.NasaPowerClient.daily",
        new_callable=AsyncMock,
    ) as mock_daily:
        mock_daily.return_value = MOCK_POWER_MISSING

        service = PowerService(test_redis)
        result, _ = await service.get(
            -33.89, -60.57, "20260101", "20260102", ["temp"]
        )

        values = result.parameters[0].values
        assert values[0] == 25.0
        assert values[1] is None  # -999 → None


@pytest.mark.asyncio
async def test_power_unknown_parameter_raises(test_redis):
    """Unknown parameter short-name raises ValueError at the client layer."""
    service = PowerService(test_redis)
    with pytest.raises(ValueError, match="Unknown parameter"):
        await service.get(-33.89, -60.57, "20260101", "20260102", ["bananas"])


@pytest.mark.asyncio
async def test_power_api_fail_stale_fallback(test_redis):
    """API fail → stale cache → is_stale=True."""
    with patch(
        "argplant.modules.agroclimate.service.NasaPowerClient.daily",
        new_callable=AsyncMock,
    ) as mock_daily:
        # Prime cache
        mock_daily.return_value = MOCK_POWER_RAW
        service = PowerService(test_redis)
        await service.get(-33.89, -60.57, "20260101", "20260102", ["temp"])

        # Delete fresh, keep stale
        from argplant.modules.agroclimate.service import _power_cache_key
        cache_key = _power_cache_key(-33.89, -60.57, "20260101", "20260102", ["temp"])
        await test_redis.delete(cache_key)

        # API fails
        mock_daily.side_effect = httpx.ConnectError("down")
        result, is_stale = await service.get(
            -33.89, -60.57, "20260101", "20260102", ["temp"]
        )
        assert is_stale is True
        assert result.unit_map["T2M"] == "°C"


@pytest.mark.asyncio
async def test_power_cold_cache_api_fail_raises(test_redis):
    """Cold cache + NASA POWER down → ServiceUnavailableError."""
    with patch(
        "argplant.modules.agroclimate.service.NasaPowerClient.daily",
        new_callable=AsyncMock,
    ) as mock_daily:
        mock_daily.side_effect = httpx.ConnectError("down")

        service = PowerService(test_redis)
        with pytest.raises(ServiceUnavailableError):
            await service.get(-34.0, -61.0, "20260101", "20260102", ["temp"])


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def test_weather_cache_key_format():
    """Weather cache key uses consistent format."""
    from argplant.modules.agroclimate.service import _weather_cache_key
    key = _weather_cache_key(-33.89, -60.57)
    assert key == "weather:-33.89:-60.57"


def test_power_cache_key_includes_sorted_params():
    """POWER cache key includes sorted parameter names."""
    from argplant.modules.agroclimate.service import _power_cache_key
    key = _power_cache_key(-33.89, -60.57, "20260101", "20260130", ["temp", "solar", "precip"])
    expected = "power:-33.89:-60.57:20260101:20260130:precip,solar,temp"
    assert key == expected
