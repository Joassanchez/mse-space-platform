"""Unit tests for the model rule engine."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from argplant.modules.model.engine import RuleEngine
from argplant.modules.model.models import PredictRequest


@pytest.fixture
def engine() -> RuleEngine:
    return RuleEngine()


@pytest.fixture
def base_request() -> PredictRequest:
    return PredictRequest(
        lot_id="lote-123",
        crop="soy",
        lat=-33.89,
        lon=-60.57,
        date="2026-07-21",
    )


@pytest.fixture
def analysis_with_critical_water() -> dict:
    """Analysis data with critical soil moisture and water deficit."""
    return {
        "agroclimate": {
            "current": {"temp": 25.3, "humidity": 55, "wind_speed": 3.6},
            "historical": {"precipitation_15d_mm": 3.0, "solar_radiation_avg": 18.2, "temp_avg_15d": 22.1},
        },
        "satellite": {
            "soil_moisture_value": {"soil_moisture": 0.10, "soil_moisture_pct": 10.0},
            "optical": [],
        },
        "agronomy": {
            "crop_info": {
                "id": "soy", "name": "Soja",
                "temperature": {"optimal_min": 20, "optimal_max": 30, "stress_min": 35},
            },
            "current_stage": {"bbch_code": "75", "name": "Llenado de vainas", "kc": 1.15, "water_stress_sensitivity": "high"},
        },
        "economy": {"latest_price": {"fecha": "2026-07-21", "promedio": 498851}},
    }


@pytest.fixture
def analysis_healthy() -> dict:
    """Analysis data with healthy conditions."""
    return {
        "agroclimate": {
            "current": {"temp": 24.0, "humidity": 60},
            "historical": {"precipitation_15d_mm": 45.0, "solar_radiation_avg": 16.0, "temp_avg_15d": 21.0},
        },
        "satellite": {
            "soil_moisture_value": {"soil_moisture": 0.35},
            "optical": [],
        },
        "agronomy": {
            "crop_info": {"id": "soy", "name": "Soja", "temperature": {"stress_min": 35}},
            "current_stage": {"bbch_code": "25", "name": "Quinto nudo", "kc": 0.9, "water_stress_sensitivity": "medium"},
        },
        "economy": {},
    }


@pytest.fixture
def analysis_heat_only() -> dict:
    """Analysis with heat stress but normal water."""
    return {
        "agroclimate": {
            "current": {"temp": 37.0, "humidity": 30},
            "historical": {"precipitation_15d_mm": 20.0, "solar_radiation_avg": 22.0, "temp_avg_15d": 28.0},
        },
        "satellite": {
            "soil_moisture_value": {"soil_moisture": 0.30},
        },
        "agronomy": {
            "crop_info": {"id": "soy", "temperature": {"stress_min": 35}},
            "current_stage": {"bbch_code": "65", "name": "Floración", "water_stress_sensitivity": "high"},
        },
        "economy": {},
    }


class TestRuleEngine:
    """Core rule engine behavior."""

    def test_critical_water_stress_detected(self, engine, base_request, analysis_with_critical_water):
        result = engine.evaluate(base_request, analysis_with_critical_water)
        water = [a for a in result.anomalies if a.type == "water_stress"]
        assert len(water) >= 1
        assert any(a.severity == "critical" for a in water)

    def test_no_anomalies_when_healthy(self, engine, base_request, analysis_healthy):
        result = engine.evaluate(base_request, analysis_healthy)
        assert len(result.anomalies) == 0
        assert result.risk_assessment.overall == "low"

    def test_heat_stress_detected(self, engine, base_request, analysis_heat_only):
        result = engine.evaluate(base_request, analysis_heat_only)
        heat = [a for a in result.anomalies if a.type == "heat_stress"]
        assert len(heat) >= 1

    def test_risk_score_with_critical_anomalies(self, engine, base_request, analysis_with_critical_water):
        result = engine.evaluate(base_request, analysis_with_critical_water)
        assert result.risk_assessment.score > 50
        assert result.risk_assessment.overall in ("high", "critical")

    def test_risk_score_healthy_is_low(self, engine, base_request, analysis_healthy):
        result = engine.evaluate(base_request, analysis_healthy)
        assert result.risk_assessment.score < 25

    def test_yield_prediction_with_loss(self, engine, base_request, analysis_with_critical_water):
        result = engine.evaluate(base_request, analysis_with_critical_water)
        assert result.yield_prediction is not None
        assert result.yield_prediction.loss_pct > 0
        assert result.yield_prediction.estimate_kg_ha < result.yield_prediction.potential_kg_ha

    def test_yield_prediction_no_loss_healthy(self, engine, base_request, analysis_healthy):
        result = engine.evaluate(base_request, analysis_healthy)
        assert result.yield_prediction is not None
        assert result.yield_prediction.loss_pct == 0.0

    def test_economic_impact_computed(self, engine, base_request, analysis_with_critical_water):
        result = engine.evaluate(base_request, analysis_with_critical_water)
        assert result.economic_impact is not None
        assert result.economic_impact.estimated_loss_ars > 0

    def test_recommendations_generated_for_critical(self, engine, base_request, analysis_with_critical_water):
        result = engine.evaluate(base_request, analysis_with_critical_water)
        assert len(result.recommendations) > 0
        # Should have a riego recommendation
        riego = [r for r in result.recommendations if "riego" in r.action.lower() or "Riego" in r.action]
        assert len(riego) >= 1

    def test_recommendations_monitor_when_healthy(self, engine, base_request, analysis_healthy):
        result = engine.evaluate(base_request, analysis_healthy)
        assert len(result.recommendations) == 1
        assert result.recommendations[0].urgency == "monitor"

    def test_alerts_generated(self, engine, base_request, analysis_with_critical_water):
        result = engine.evaluate(base_request, analysis_with_critical_water)
        assert len(result.alerts) > 0

    def test_response_includes_query_echo(self, engine, base_request, analysis_with_critical_water):
        result = engine.evaluate(base_request, analysis_with_critical_water)
        assert result.query.lot_id == "lote-123"
        assert result.query.crop == "soy"

    def test_data_sources_included(self, engine, base_request, analysis_with_critical_water):
        result = engine.evaluate(base_request, analysis_with_critical_water)
        assert "agroclimate" in result.data_sources
        assert "agronomy" in result.data_sources

    def test_generated_at_is_iso8601(self, engine, base_request, analysis_with_critical_water):
        result = engine.evaluate(base_request, analysis_with_critical_water)
        assert "T" in result.generated_at  # ISO 8601

    def test_corn_crop(self, engine, analysis_healthy):
        req = PredictRequest(lot_id="l-456", crop="corn", lat=-33.0, lon=-61.0, date="2026-07-21")
        result = engine.evaluate(req, analysis_healthy)
        assert result.query.crop == "corn"
        assert result.yield_prediction is not None
