"""Unit tests for WeatherAgent (AGENT-HYD-MET-001).

Tests cover:
- All condition classifications (FAR_BELOW, BELOW_AVERAGE, AVERAGE, ABOVE_AVERAGE, FAR_ABOVE)
- No data (graceful degradation)
- Partial data (only rainfall, only anomaly)
- Confidence calculation
- Data completeness
- Template NL output
- Stateless behavior (two executions, different results)
"""

import pytest

from src.ai.agents.weather.agent import WeatherAgent
from src.ai.domain.models import WeatherCondition


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def agent():
    """Create a fresh WeatherAgent instance."""
    return WeatherAgent()


def _make_context(
    rainfall_30d: float | None = None,
    anomaly_pct: float | None = None,
    temperature_anomaly: float | None = None,
    forecast_relevance: float | None = None,
    rainfall_classification: str = "adequate",
    anomaly_classification: str = "adequate",
    rainfall_confidence: float = 0.85,
    anomaly_confidence: float = 0.85,
    warnings: list[str] | None = None,
) -> dict:
    """Helper to build a context dict with weather indicators."""
    indicators = []

    if rainfall_30d is not None:
        indicators.append(
            {
                "id": 1,
                "region_id": 1,
                "indicator_code": "RAINFALL_30D",
                "indicator_name": "30-Day Accumulated Rainfall",
                "value": rainfall_30d,
                "unit": "mm",
                "classification": rainfall_classification,
                "confidence": rainfall_confidence,
                "temporal_start": "2026-04-24T00:00:00Z",
                "temporal_end": "2026-05-24T00:00:00Z",
            }
        )

    if anomaly_pct is not None:
        indicators.append(
            {
                "id": 2,
                "region_id": 1,
                "indicator_code": "RAINFALL_ANOMALY",
                "indicator_name": "Rainfall Anomaly Percentage",
                "value": anomaly_pct,
                "unit": "percent",
                "classification": anomaly_classification,
                "confidence": anomaly_confidence,
                "temporal_start": "2026-04-24T00:00:00Z",
                "temporal_end": "2026-05-24T00:00:00Z",
            }
        )

    if temperature_anomaly is not None:
        indicators.append(
            {
                "id": 3,
                "region_id": 1,
                "indicator_code": "TEMPERATURE_ANOMALY",
                "indicator_name": "Temperature Anomaly",
                "value": temperature_anomaly,
                "unit": "°C",
                "classification": "adequate",
                "confidence": 0.8,
                "temporal_start": "2026-04-24T00:00:00Z",
                "temporal_end": "2026-05-24T00:00:00Z",
            }
        )

    if forecast_relevance is not None:
        indicators.append(
            {
                "id": 4,
                "region_id": 1,
                "indicator_code": "FORECAST_RELEVANCE",
                "indicator_name": "Forecast Relevance Score",
                "value": forecast_relevance,
                "unit": "score",
                "classification": "adequate",
                "confidence": 0.7,
                "temporal_start": "2026-05-24T00:00:00Z",
                "temporal_end": "2026-05-31T00:00:00Z",
            }
        )

    return {
        "regions": [{"id": 1, "name": "Test Region"}],
        "layers": [],
        "indicators": indicators,
        "risk_assessments": [],
        "metadata": {
            "entity_counts": {"regions": 1, "indicators": len(indicators)},
            "generated_at": "2026-05-24T00:00:00Z",
        },
        "warnings": warnings or [],
    }


# ============================================================
# Condition Classification Tests
# ============================================================


class TestConditionClassification:
    """Test rainfall condition classification based on anomaly percentage."""

    def test_far_below(self, agent):
        """Anomaly < -50% → FAR_BELOW."""
        ctx = _make_context(anomaly_pct=-60.0)
        result = agent.execute(ctx)
        assert result["condition"] == WeatherCondition.FAR_BELOW.value

    def test_below_average(self, agent):
        """Anomaly between -50% and -20% → BELOW_AVERAGE."""
        ctx = _make_context(anomaly_pct=-35.0)
        result = agent.execute(ctx)
        assert result["condition"] == WeatherCondition.BELOW_AVERAGE.value

    def test_average(self, agent):
        """Anomaly between -20% and +20% → AVERAGE."""
        ctx = _make_context(anomaly_pct=5.0)
        result = agent.execute(ctx)
        assert result["condition"] == WeatherCondition.AVERAGE.value

    def test_average_boundary_low(self, agent):
        """Anomaly exactly -20% → AVERAGE (boundary)."""
        ctx = _make_context(anomaly_pct=-20.0)
        result = agent.execute(ctx)
        assert result["condition"] == WeatherCondition.AVERAGE.value

    def test_average_boundary_high(self, agent):
        """Anomaly exactly +20% → AVERAGE (boundary)."""
        ctx = _make_context(anomaly_pct=20.0)
        result = agent.execute(ctx)
        assert result["condition"] == WeatherCondition.AVERAGE.value

    def test_above_average(self, agent):
        """Anomaly between +20% and +50% → ABOVE_AVERAGE."""
        ctx = _make_context(anomaly_pct=35.0)
        result = agent.execute(ctx)
        assert result["condition"] == WeatherCondition.ABOVE_AVERAGE.value

    def test_far_above(self, agent):
        """Anomaly > +50% → FAR_ABOVE."""
        ctx = _make_context(anomaly_pct=75.0)
        result = agent.execute(ctx)
        assert result["condition"] == WeatherCondition.FAR_ABOVE.value

    def test_no_anomaly_defaults_average(self, agent):
        """No anomaly data → AVERAGE (default assumption)."""
        ctx = _make_context(rainfall_30d=50.0)  # No anomaly
        result = agent.execute(ctx)
        assert result["condition"] == WeatherCondition.AVERAGE.value


# ============================================================
# Graceful Degradation Tests
# ============================================================


class TestGracefulDegradation:
    """Test graceful degradation when data is missing."""

    def test_no_data(self, agent):
        """No weather indicators → defaults, confidence=0, completeness=0."""
        ctx = _make_context()  # No indicators
        result = agent.execute(ctx)

        assert result["rainfall_30d_mm"] is None
        assert result["rainfall_anomaly_pct"] is None
        assert result["condition"] == WeatherCondition.AVERAGE.value
        assert result["confidence_score"] == 0.0
        assert result["data_completeness"] == 0.0

    def test_partial_data_only_rainfall(self, agent):
        """Only rainfall indicator → data_completeness=0.4 (rainfall=0.4, rest 0)."""
        ctx = _make_context(rainfall_30d=50.0)
        result = agent.execute(ctx)

        assert result["data_completeness"] == 0.4
        assert result["rainfall_30d_mm"] == 50.0
        assert result["rainfall_anomaly_pct"] is None
        assert result["condition"] == WeatherCondition.AVERAGE.value

    def test_partial_data_only_anomaly(self, agent):
        """Only anomaly indicator → data_completeness=0.4 (anomaly=0.4, rest 0)."""
        ctx = _make_context(anomaly_pct=-30.0)
        result = agent.execute(ctx)

        assert result["data_completeness"] == 0.4
        assert result["rainfall_30d_mm"] is None
        assert result["rainfall_anomaly_pct"] == -30.0
        assert result["condition"] == WeatherCondition.BELOW_AVERAGE.value

    def test_never_crashes_empty_context(self, agent):
        """Empty context dict should not crash."""
        result = agent.execute({})

        assert result["condition"] == WeatherCondition.AVERAGE.value
        assert result["confidence_score"] == 0.0
        assert result["data_completeness"] == 0.0


# ============================================================
# Confidence Calculation Tests
# ============================================================


class TestConfidenceCalculation:
    """Test confidence score calculation."""

    def test_full_data_high_confidence(self, agent):
        """Full data with good quality → high confidence."""
        ctx = _make_context(
            rainfall_30d=50.0,
            anomaly_pct=10.0,
            rainfall_classification="good",
            anomaly_classification="good",
            rainfall_confidence=0.9,
            anomaly_confidence=0.9,
        )
        result = agent.execute(ctx)

        assert result["confidence_score"] > 0.5
        assert result["data_completeness"] == 0.8

    def test_stale_data_penalty(self, agent):
        """Stale data warning reduces freshness factor."""
        ctx = _make_context(
            rainfall_30d=50.0,
            anomaly_pct=10.0,
            warnings=["stale_data: true — latest data is 100 hours old"],
        )
        result = agent.execute(ctx)

        # Confidence should be lower than without stale warning
        ctx_fresh = _make_context(rainfall_30d=50.0, anomaly_pct=10.0)
        result_fresh = agent.execute(ctx_fresh)

        assert result["confidence_score"] < result_fresh["confidence_score"]

    def test_no_data_zero_confidence(self, agent):
        """No data → confidence = 0."""
        ctx = _make_context()
        result = agent.execute(ctx)
        assert result["confidence_score"] == 0.0


# ============================================================
# Data Completeness Tests
# ============================================================


class TestDataCompleteness:
    """Test data completeness calculation."""

    def test_complete_data(self, agent):
        """Both rainfall and anomaly → completeness = 0.8 (0.4+0.4)."""
        ctx = _make_context(rainfall_30d=50.0, anomaly_pct=10.0)
        result = agent.execute(ctx)
        assert result["data_completeness"] == 0.8

    def test_partial_rainfall_only(self, agent):
        """Only rainfall → completeness = 0.4."""
        ctx = _make_context(rainfall_30d=50.0)
        result = agent.execute(ctx)
        assert result["data_completeness"] == 0.4

    def test_partial_anomaly_only(self, agent):
        """Only anomaly → completeness = 0.4."""
        ctx = _make_context(anomaly_pct=10.0)
        result = agent.execute(ctx)
        assert result["data_completeness"] == 0.4

    def test_no_data(self, agent):
        """No indicators → completeness = 0.0."""
        ctx = _make_context()
        result = agent.execute(ctx)
        assert result["data_completeness"] == 0.0


# ============================================================
# Natural Language Output Tests
# ============================================================


class TestNaturalLanguageOutput:
    """Test template-based natural language output."""

    def test_normal_nl_format(self, agent):
        """NL output follows expected template format with all fields."""
        ctx = _make_context(rainfall_30d=50.0, anomaly_pct=10.0)
        result = agent.execute(ctx)

        nl = result["natural_language_output"]
        assert "Rainfall:" in nl
        assert "30d=" in nl
        assert "anomaly:" in nl
        assert "condition:" in nl
        assert "Temperature:" in nl
        assert "Humidity:" in nl
        assert "Wind:" in nl
        assert "Data confidence:" in nl

    def test_unavailable_nl_message(self, agent):
        """No data → specific unavailable message."""
        ctx = _make_context()
        result = agent.execute(ctx)

        assert (
            result["natural_language_output"]
            == "Weather data is currently unavailable for this region."
        )

    def test_nl_includes_values(self, agent):
        """NL output includes actual rainfall values."""
        ctx = _make_context(rainfall_30d=75.5, anomaly_pct=-30.0)
        result = agent.execute(ctx)

        nl = result["natural_language_output"]
        assert "75.5" in nl
        assert "-30.0" in nl

    def test_nl_with_temperature_anomaly(self, agent):
        """NL output includes temperature anomaly when present."""
        ctx = _make_context(
            rainfall_30d=50.0,
            anomaly_pct=10.0,
            temperature_anomaly=2.5,
        )
        result = agent.execute(ctx)

        nl = result["natural_language_output"]
        assert "2.5" in nl
        assert "°C" in nl


# ============================================================
# Optional Fields Tests
# ============================================================


class TestOptionalFields:
    """Test extraction of optional fields."""

    def test_temperature_anomaly_extracted(self, agent):
        """Temperature anomaly is extracted when present."""
        ctx = _make_context(
            rainfall_30d=50.0,
            anomaly_pct=10.0,
            temperature_anomaly=-1.5,
        )
        result = agent.execute(ctx)
        assert result["temperature_anomaly"] == -1.5

    def test_temperature_anomaly_none_when_absent(self, agent):
        """Temperature anomaly is None when not present."""
        ctx = _make_context(rainfall_30d=50.0, anomaly_pct=10.0)
        result = agent.execute(ctx)
        assert result["temperature_anomaly"] is None

    def test_forecast_relevance_extracted(self, agent):
        """Forecast relevance is extracted when present."""
        ctx = _make_context(
            rainfall_30d=50.0,
            anomaly_pct=10.0,
            forecast_relevance=0.8,
        )
        result = agent.execute(ctx)
        assert result["forecast_relevance"] == 0.8

    def test_forecast_relevance_none_when_absent(self, agent):
        """Forecast relevance is None when not present."""
        ctx = _make_context(rainfall_30d=50.0, anomaly_pct=10.0)
        result = agent.execute(ctx)
        assert result["forecast_relevance"] is None


# ============================================================
# Stateless Behavior Tests
# ============================================================


class TestStatelessBehavior:
    """Test that agent is stateless between executions."""

    def test_different_contexts_different_results(self, agent):
        """Two executions with different contexts give different results."""
        ctx_dry = _make_context(rainfall_30d=10.0, anomaly_pct=-60.0)
        ctx_wet = _make_context(rainfall_30d=150.0, anomaly_pct=75.0)

        result_dry = agent.execute(ctx_dry)
        result_wet = agent.execute(ctx_wet)

        assert result_dry["condition"] != result_wet["condition"]
        assert result_dry["rainfall_30d_mm"] != result_wet["rainfall_30d_mm"]
        assert result_dry["natural_language_output"] != result_wet["natural_language_output"]

    def test_same_context_same_results(self, agent):
        """Same context produces same result (deterministic)."""
        ctx = _make_context(rainfall_30d=50.0, anomaly_pct=10.0)

        result1 = agent.execute(ctx)
        result2 = agent.execute(ctx)

        assert result1 == result2


# ============================================================
# Agent Contract Tests
# ============================================================


class TestAgentContract:
    """Test agent contract compliance."""

    def test_has_name_attribute(self, agent):
        """Agent has a name attribute."""
        assert hasattr(agent, "name")
        assert agent.name == "weather"

    def test_execute_returns_dict(self, agent):
        """Execute method returns a dict."""
        ctx = _make_context(rainfall_30d=50.0, anomaly_pct=10.0)
        result = agent.execute(ctx)
        assert isinstance(result, dict)

    def test_execute_has_all_required_fields(self, agent):
        """Execute result has all required WeatherOutput fields."""
        ctx = _make_context(rainfall_30d=50.0, anomaly_pct=10.0)
        result = agent.execute(ctx)

        required_fields = [
            "rainfall_30d_mm",
            "rainfall_anomaly_pct",
            "condition",
            "temperature_anomaly",
            "forecast_relevance",
            "confidence_score",
            "data_completeness",
            "natural_language_output",
        ]

        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_confidence_in_valid_range(self, agent):
        """Confidence score is always between 0 and 1."""
        ctx = _make_context(rainfall_30d=50.0, anomaly_pct=10.0)
        result = agent.execute(ctx)
        assert 0.0 <= result["confidence_score"] <= 1.0

    def test_data_completeness_in_valid_range(self, agent):
        """Data completeness is always between 0 and 1."""
        ctx = _make_context(rainfall_30d=50.0, anomaly_pct=10.0)
        result = agent.execute(ctx)
        assert 0.0 <= result["data_completeness"] <= 1.0

    def test_no_init_state(self, agent):
        """Agent __init__ has no state beyond name."""
        assert set(vars(agent).keys()) == {"name"}
