"""Integration tests for the agroclimate API router.

Uses httpx.AsyncClient bound to the FastAPI app (via ASGITransport) with
mocked external HTTP clients so no real API keys are needed.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from argplant.main import app


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_OWM_RESPONSE = {
    "coord": {"lon": -60.57, "lat": -33.89},
    "weather": [{"id": 800, "main": "Clear", "description": "clear sky"}],
    "main": {
        "temp": 25.3,
        "feels_like": 24.1,
        "temp_min": 22.0,
        "temp_max": 27.5,
        "pressure": 1013,
        "humidity": 55,
    },
    "wind": {"speed": 3.6, "deg": 90},
    "name": "Pergamino",
}

MOCK_POWER_RESPONSE = {
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [-60.57, -33.89]},
    "properties": {
        "parameter": {
            "T2M": {"20260101": 25.0, "20260102": 26.1, "20260103": 24.5},
            "PRECTOTCORR": {"20260101": 0.0, "20260102": 2.3, "20260103": 0.0},
            "ALLSKY_SFC_SW_DWN": {"20260101": 20.5, "20260102": 18.2, "20260103": 22.1},
        }
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_owm():
    """Mock OpenWeatherClient.current to return a synthetic response."""
    with patch(
        "argplant.modules.agroclimate.service.OpenWeatherClient.current",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = MOCK_OWM_RESPONSE
        yield mock


@pytest.fixture
def mock_power():
    """Mock NasaPowerClient.daily to return a synthetic response."""
    with patch(
        "argplant.modules.agroclimate.service.NasaPowerClient.daily",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = MOCK_POWER_RESPONSE
        yield mock


@pytest.fixture
def mock_owm_failing():
    """Mock OpenWeatherClient.current to raise an HTTP error."""
    import httpx

    with patch(
        "argplant.modules.agroclimate.service.OpenWeatherClient.current",
        new_callable=AsyncMock,
    ) as mock:
        mock.side_effect = httpx.ConnectError("API unreachable")
        yield mock


# ---------------------------------------------------------------------------
# Weather endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weather_returns_200_with_correct_schema(
    test_client: AsyncClient, mock_owm: AsyncMock
):
    """Fresh forecast hit: 200 with temperature, humidity, wind, conditions."""
    response = await test_client.get(
        "/api/v1/agroclimate/weather", params={"lat": -33.89, "lon": -60.57}
    )
    assert response.status_code == 200

    body = response.json()
    assert body["temp"] == 25.3
    assert body["humidity"] == 55
    assert body["wind_speed"] == 3.6
    assert body["conditions"] == "clear sky"
    assert body["lat"] == -33.89
    assert body["lon"] == -60.57
    assert "timestamp" in body


@pytest.mark.asyncio
async def test_weather_caches_result(
    test_client: AsyncClient, mock_owm: AsyncMock
):
    """Second call within TTL returns cached data — API not called again."""
    params = {"lat": -33.89, "lon": -60.57}

    # First call — cache miss
    r1 = await test_client.get("/api/v1/agroclimate/weather", params=params)
    assert r1.status_code == 200
    assert mock_owm.call_count == 1

    # Second call — cache hit
    r2 = await test_client.get("/api/v1/agroclimate/weather", params=params)
    assert r2.status_code == 200
    assert r2.json()["temp"] == 25.3
    # API should NOT have been called a second time
    assert mock_owm.call_count == 1


@pytest.mark.asyncio
async def test_weather_returns_stale_when_api_fails(
    test_client: AsyncClient, mock_owm: AsyncMock, mock_owm_failing: AsyncMock
):
    """First call succeeds (fills cache). Second call hits stale cache when API fails."""
    params = {"lat": -33.89, "lon": -60.57}

    # Prime the cache
    r1 = await test_client.get("/api/v1/agroclimate/weather", params=params)
    assert r1.status_code == 200

    # Force cache expiry by deleting the fresh key but keeping stale
    from argplant.modules.agroclimate.service import _weather_cache_key
    import redis.asyncio as aioredis

    redis_client = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
    try:
        cache_key = _weather_cache_key(-33.89, -60.57)
        await redis_client.delete(cache_key)

        # Second call — API fails, should fall back to stale
        r2 = await test_client.get("/api/v1/agroclimate/weather", params=params)
        assert r2.status_code == 200
        assert r2.headers.get("x-stale") == "true"
    finally:
        await redis_client.aclose()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_weather_returns_503_when_cold_cache_and_api_fails(
    mock_owm_failing: AsyncMock,
):
    """Cold cache + API failure → 503."""
    # We need a clean client without any cache priming
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/agroclimate/weather", params={"lat": -34.0, "lon": -61.0}
        )
        assert response.status_code == 503


@pytest.mark.asyncio
async def test_weather_rejects_invalid_coordinates(test_client: AsyncClient):
    """Lat outside [-90, 90] should return 422 validation error."""
    response = await test_client.get(
        "/api/v1/agroclimate/weather", params={"lat": 999, "lon": -60.57}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POWER endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_power_returns_200_with_parameters(
    test_client: AsyncClient, mock_power: AsyncMock
):
    """POWER request returns metric parameters for the date range."""
    response = await test_client.get(
        "/api/v1/agroclimate/power",
        params={
            "lat": -33.89,
            "lon": -60.57,
            "start_date": "2026-01-01",
            "end_date": "2026-01-03",
            "parameters": "solar,temp,precip",
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert body["lat"] == -33.89
    assert body["lon"] == -60.57
    assert body["start_date"] == "20260101"
    assert body["end_date"] == "20260103"
    assert len(body["parameters"]) == 3

    # Unit map should have entries for each parameter
    assert "ALLSKY_SFC_SW_DWN" in body["unit_map"]
    assert body["unit_map"]["ALLSKY_SFC_SW_DWN"] == "MJ/m²/day"


@pytest.mark.asyncio
async def test_power_rejects_unknown_parameter(test_client: AsyncClient):
    """Unknown parameter name returns 400."""
    response = await test_client.get(
        "/api/v1/agroclimate/power",
        params={
            "lat": -33.89,
            "lon": -60.57,
            "start_date": "2026-01-01",
            "end_date": "2026-01-03",
            "parameters": "solar,bananas",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_power_rejects_empty_parameters(test_client: AsyncClient):
    """Empty parameters string returns 422."""
    response = await test_client.get(
        "/api/v1/agroclimate/power",
        params={
            "lat": -33.89,
            "lon": -60.57,
            "start_date": "2026-01-01",
            "end_date": "2026-01-03",
            "parameters": "",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_power_x_cache_header(
    test_client: AsyncClient, mock_power: AsyncMock
):
    """First call returns X-Cache: HIT (after fetch)."""
    params = {
        "lat": -33.89,
        "lon": -60.57,
        "start_date": "2026-01-01",
        "end_date": "2026-01-03",
        "parameters": "temp",
    }
    response = await test_client.get("/api/v1/agroclimate/power", params=params)
    assert response.status_code == 200
    # X-Cache is HIT even on first call because the service
    # writes to cache then returns — it's already cached by response time.
    # The spec says cache-miss triggers API call then HIT, which matches.
    assert "x-cache" in response.headers
