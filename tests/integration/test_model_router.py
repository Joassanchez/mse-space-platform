"""Integration tests for the model prediction endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient

from argplant.main import app


@pytest.fixture
async def model_client():
    """Test client with analysis orchestrator mocked to return known data."""
    mock_analysis = {
        "agroclimate": {
            "current": {"temp": 25.3, "humidity": 55, "wind_speed": 3.6},
            "historical": {"precipitation_15d_mm": 3.0, "solar_radiation_avg": 18.2, "temp_avg_15d": 22.1},
        },
        "satellite": {
            "soil_moisture_value": {"soil_moisture": 0.10, "soil_moisture_pct": 10.0},
            "soil_moisture": [],
            "optical": [],
        },
        "agronomy": {
            "crop_info": {
                "id": "soy", "name": "Soja",
                "temperature": {"optimal_min": 20, "optimal_max": 30, "stress_min": 35},
            },
            "current_stage": {"bbch_code": "75", "name": "Llenado de vainas", "kc": 1.15, "water_stress_sensitivity": "high"},
        },
        "economy": {"latest_price": {"fecha": "2026-07-21", "promedio": 498851}, "series": []},
        "query": {"lot_id": "lote-123", "crop": "soy", "lat": -33.89, "lon": -60.57, "date": "2026-07-21"},
        "meta": {"status": "complete", "missing_modules": [], "cached_at": None},
    }

    with patch(
        "argplant.modules.analysis.orchestrator.AnalysisOrchestrator.gather",
        new_callable=AsyncMock,
    ) as mock_gather:
        from argplant.modules.analysis.models import AnalysisResponse
        mock_gather.return_value = AnalysisResponse(**mock_analysis)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


class TestPredictEndpoint:
    """Integration tests for POST /api/v1/predict."""

    @pytest.mark.asyncio
    async def test_predict_returns_200(self, model_client):
        response = await model_client.post("/api/v1/predict", json={
            "lot_id": "lote-123",
            "crop": "soy",
            "lat": -33.89,
            "lon": -60.57,
            "date": "2026-07-21",
        })
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_predict_response_has_anomalies(self, model_client):
        response = await model_client.post("/api/v1/predict", json={
            "lot_id": "lote-123", "crop": "soy", "lat": -33.89, "lon": -60.57, "date": "2026-07-21",
        })
        data = response.json()
        assert "anomalies" in data
        assert len(data["anomalies"]) > 0

    @pytest.mark.asyncio
    async def test_predict_response_has_risk(self, model_client):
        response = await model_client.post("/api/v1/predict", json={
            "lot_id": "lote-123", "crop": "soy", "lat": -33.89, "lon": -60.57, "date": "2026-07-21",
        })
        data = response.json()
        assert "risk_assessment" in data
        assert "overall" in data["risk_assessment"]

    @pytest.mark.asyncio
    async def test_predict_response_has_recommendations(self, model_client):
        response = await model_client.post("/api/v1/predict", json={
            "lot_id": "lote-123", "crop": "soy", "lat": -33.89, "lon": -60.57, "date": "2026-07-21",
        })
        data = response.json()
        assert len(data["recommendations"]) > 0

    @pytest.mark.asyncio
    async def test_predict_response_has_yield(self, model_client):
        response = await model_client.post("/api/v1/predict", json={
            "lot_id": "lote-123", "crop": "soy", "lat": -33.89, "lon": -60.57, "date": "2026-07-21",
        })
        data = response.json()
        assert data["yield_prediction"] is not None

    @pytest.mark.asyncio
    async def test_predict_validates_lat_range(self, model_client):
        response = await model_client.post("/api/v1/predict", json={
            "lot_id": "lote-123", "crop": "soy", "lat": 999, "lon": -60.57, "date": "2026-07-21",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_predict_handles_unknown_crop(self, model_client):
        response = await model_client.post("/api/v1/predict", json={
            "lot_id": "lote-123", "crop": "wheat", "lat": -33.89, "lon": -60.57, "date": "2026-07-21",
        })
        # Unknown crop should still return 200 but with no/limited agronomy data
        assert response.status_code == 200
