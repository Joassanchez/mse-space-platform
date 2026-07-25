"""Integration tests for the analysis API router.

Tests the unified analysis endpoint with mocked orchestrator to verify:
- Full response schema
- Cache HIT/MISS headers
- X-Partial header for partial responses
- Input validation (invalid crop, coordinates)
- 502 on orchestrator failure
"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from argplant.main import app
from argplant.modules.analysis.models import (
    AgroclimateSection,
    AgronomySection,
    AnalysisMeta,
    AnalysisRequest,
    AnalysisResponse,
    EconomySection,
    SatelliteSection,
)

# ---------------------------------------------------------------------------
# Mock response factory
# ---------------------------------------------------------------------------


def _make_full_response(
    lot_id: str = "lote-123",
    crop: str = "soy",
    lat: float = -33.89,
    lon: float = -60.57,
    query_date: date | None = None,
    partial: bool = False,
) -> AnalysisResponse:
    """Build a representative AnalysisResponse for test assertions."""
    if query_date is None:
        query_date = date(2026, 7, 21)
    query = AnalysisRequest(lot_id=lot_id, crop=crop, lat=lat, lon=lon, date=query_date)
    meta = AnalysisMeta(
        status="partial" if partial else "complete",
        missing_modules=["economy"] if partial else [],
        cached_at=None,
    )
    return AnalysisResponse(
        query=query,
        agroclimate=AgroclimateSection(
            current={
                "temp": 25.3, "humidity": 55, "wind_speed": 3.6,
                "conditions": "clear sky", "lat": -33.89, "lon": -60.57,
                "timestamp": "2026-07-21T14:00:00Z",
            },
            historical={
                "precipitation_15d_mm": 8.5,
                "solar_radiation_avg": 18.7,
                "temp_avg_15d": 22.1,
            },
        ),
        satellite=SatelliteSection(
            soil_moisture=[
                {
                    "scene_id": "SMAP_001",
                    "acquisition_date": "2026-07-20T12:00:00Z",
                    "granule_ur": "SMAP_001",
                    "platform": "smap",
                    "bbox": [-61.0, -34.0, -60.0, -33.0],
                }
            ],
            optical=[
                {
                    "id": "S2B_001",
                    "acquisition_date": "2026-07-18T14:30:00Z",
                    "cloud_cover": 3.2,
                    "thumbnail_url": None,
                    "platform": "Sentinel-2",
                    "bbox": [-61.0, -34.0, -60.0, -33.0],
                }
            ],
        ),
        agronomy=AgronomySection(
            crop_info={
                "id": "soy", "name": "Soja", "scientific_name": "Glycine max",
                "growing_season_days": 120,
                "temperature": {"optimal_min": 20, "optimal_max": 30, "stress_min": 35},
            },
            current_stage={
                "bbch_code": "75", "name": "Llenado de vainas",
                "kc": 1.05, "water_stress_sensitivity": "high",
            },
        ),
        economy=None if partial else EconomySection(
            latest_price={"fecha": "2026-07-21", "promedio": 498851, "modal": 498000},
            series=[
                {"fecha": "2026-07-14", "minimo": 481000, "maximo": 490000, "promedio": 486978},
            ],
        ),
        meta=meta,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_orchestrator_gather():
    """Mock AnalysisOrchestrator.gather to return a full response echoing the request."""
    with patch(
        "argplant.modules.analysis.router.AnalysisOrchestrator.gather",
        new_callable=AsyncMock,
    ) as mock:

        async def _gather(lot_id, crop, lat, lon, query_date, **kwargs):
            return _make_full_response(
                lot_id=lot_id, crop=crop, lat=lat, lon=lon, query_date=query_date
            )

        mock.side_effect = _gather
        yield mock


@pytest.fixture
def mock_orchestrator_partial():
    """Mock AnalysisOrchestrator.gather to return a partial response echoing the request."""
    with patch(
        "argplant.modules.analysis.router.AnalysisOrchestrator.gather",
        new_callable=AsyncMock,
    ) as mock:

        async def _gather(lot_id, crop, lat, lon, query_date, **kwargs):
            return _make_full_response(
                lot_id=lot_id, crop=crop, lat=lat, lon=lon,
                query_date=query_date, partial=True,
            )

        mock.side_effect = _gather
        yield mock


@pytest.fixture
def mock_orchestrator_failing():
    """Mock AnalysisOrchestrator.gather to raise an exception."""
    with patch(
        "argplant.modules.analysis.router.AnalysisOrchestrator.gather",
        new_callable=AsyncMock,
    ) as mock:
        mock.side_effect = Exception("Pipeline crash")
        yield mock


# ---------------------------------------------------------------------------
# Full success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analysis_returns_200_full_response(
    test_client: AsyncClient, mock_orchestrator_gather: AsyncMock
):
    """Full analysis response returns 200 with all four sections."""
    params = {
        "lot_id": "lote-123",
        "crop": "soy",
        "lat": -33.89,
        "lon": -60.57,
        "date": "2026-07-21",
    }
    response = await test_client.get("/api/v1/analysis", params=params)
    assert response.status_code == 200

    body = response.json()
    assert body["meta"]["status"] == "complete"
    assert body["meta"]["missing_modules"] == []

    # Verify each section exists
    assert body["agroclimate"] is not None
    assert body["agroclimate"]["current"]["temp"] == 25.3
    assert body["agroclimate"]["historical"]["precipitation_15d_mm"] == 8.5

    assert body["satellite"] is not None
    assert len(body["satellite"]["soil_moisture"]) == 1
    assert len(body["satellite"]["optical"]) == 1

    assert body["agronomy"] is not None
    assert body["agronomy"]["crop_info"]["name"] == "Soja"
    assert body["agronomy"]["current_stage"]["name"] == "Llenado de vainas"

    assert body["economy"] is not None
    assert body["economy"]["latest_price"]["promedio"] == 498851
    assert len(body["economy"]["series"]) == 1


@pytest.mark.asyncio
async def test_analysis_response_includes_query_echo(
    test_client: AsyncClient, mock_orchestrator_gather: AsyncMock
):
    """Response echoes back the query parameters."""
    params = {
        "lot_id": "lote-456",
        "crop": "corn",
        "lat": -34.5,
        "lon": -61.2,
        "date": "2026-07-22",
    }
    response = await test_client.get("/api/v1/analysis", params=params)
    assert response.status_code == 200

    body = response.json()
    assert body["query"]["lot_id"] == "lote-456"
    assert body["query"]["crop"] == "corn"
    assert body["query"]["lat"] == -34.5
    assert body["query"]["lon"] == -61.2
    assert body["query"]["date"] == "2026-07-22"


# ---------------------------------------------------------------------------
# Cache headers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analysis_first_call_returns_x_cache_miss(
    test_client: AsyncClient, mock_orchestrator_gather: AsyncMock
):
    """First call (cache miss) → X-Cache: MISS."""
    params = {
        "lot_id": "lote-789",
        "crop": "soy",
        "lat": -33.89,
        "lon": -60.57,
        "date": "2026-07-23",
    }
    response = await test_client.get("/api/v1/analysis", params=params)
    assert response.status_code == 200
    assert response.headers.get("x-cache") == "MISS"


@pytest.mark.asyncio
async def test_analysis_second_call_returns_x_cache_hit(
    test_client: AsyncClient, mock_orchestrator_gather: AsyncMock
):
    """Second call with same params → X-Cache: HIT, orchestrator called once."""
    params = {
        "lot_id": "lote-999",
        "crop": "soy",
        "lat": -33.89,
        "lon": -60.57,
        "date": "2026-07-24",
    }

    # First call
    r1 = await test_client.get("/api/v1/analysis", params=params)
    assert r1.status_code == 200
    assert r1.headers.get("x-cache") == "MISS"
    assert mock_orchestrator_gather.call_count == 1

    # Second call — should hit cache
    r2 = await test_client.get("/api/v1/analysis", params=params)
    assert r2.status_code == 200
    assert r2.headers.get("x-cache") == "HIT"
    # Orchestrator should not have been called again
    assert mock_orchestrator_gather.call_count == 1


# ---------------------------------------------------------------------------
# Partial response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analysis_partial_response_sets_x_partial(
    test_client: AsyncClient, mock_orchestrator_partial: AsyncMock
):
    """Partial analysis → X-Partial: true, status 'partial'."""
    params = {
        "lot_id": "lote-555",
        "crop": "soy",
        "lat": -33.89,
        "lon": -60.57,
        "date": "2026-07-25",
    }
    response = await test_client.get("/api/v1/analysis", params=params)
    assert response.status_code == 200

    body = response.json()
    assert body["meta"]["status"] == "partial"
    assert "economy" in body["meta"]["missing_modules"]
    assert body["economy"] is None
    assert response.headers.get("x-partial") == "true"


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analysis_rejects_invalid_crop(test_client: AsyncClient):
    """Invalid crop parameter → 400."""
    params = {
        "lot_id": "lote-1",
        "crop": "sunflower",
        "lat": -33.89,
        "lon": -60.57,
        "date": "2026-07-21",
    }
    response = await test_client.get("/api/v1/analysis", params=params)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_analysis_rejects_invalid_lat(test_client: AsyncClient):
    """Lat outside [-90, 90] → 422."""
    params = {
        "lot_id": "lote-1",
        "crop": "soy",
        "lat": 999,
        "lon": -60.57,
        "date": "2026-07-21",
    }
    response = await test_client.get("/api/v1/analysis", params=params)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analysis_rejects_invalid_lon(test_client: AsyncClient):
    """Lon outside [-180, 180] → 422."""
    params = {
        "lot_id": "lote-1",
        "crop": "soy",
        "lat": -33.89,
        "lon": 999,
        "date": "2026-07-21",
    }
    response = await test_client.get("/api/v1/analysis", params=params)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analysis_rejects_missing_required_params(test_client: AsyncClient):
    """Missing required query params → 422."""
    response = await test_client.get("/api/v1/analysis")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Orchestrator failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analysis_orchestrator_failure_returns_502(
    test_client: AsyncClient, mock_orchestrator_failing: AsyncMock
):
    """Orchestrator crashes → 502."""
    params = {
        "lot_id": "lote-1",
        "crop": "soy",
        "lat": -33.89,
        "lon": -60.57,
        "date": "2026-07-21",
    }
    response = await test_client.get("/api/v1/analysis", params=params)
    assert response.status_code == 502


# ---------------------------------------------------------------------------
# Cache key isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_different_params_produce_different_cache_keys(
    test_client: AsyncClient, mock_orchestrator_gather: AsyncMock
):
    """Different lot/crop/date combos → separate cache entries."""
    params_a = {"lot_id": "a", "crop": "soy", "lat": -33.89, "lon": -60.57, "date": "2026-07-20"}
    params_b = {"lot_id": "b", "crop": "soy", "lat": -33.89, "lon": -60.57, "date": "2026-07-20"}

    r1 = await test_client.get("/api/v1/analysis", params=params_a)
    r2 = await test_client.get("/api/v1/analysis", params=params_b)

    assert r1.headers.get("x-cache") == "MISS"
    assert r2.headers.get("x-cache") == "MISS"
    # Both should have triggered orchestrator calls (different cache keys)
    assert mock_orchestrator_gather.call_count == 2
