"""Unit tests for SoilMoistureAgent (AGENT-HYD-SM-001).

Tests cover:
- Normal conditions (DRY, WET, NORMAL, CRITICAL_DRY, CRITICAL_WET)
- No data (graceful degradation → UNAVAILABLE)
- Partial data (only surface indicator)
- Confidence calculation
- Data completeness
- Template NL output
- Stateless behavior (two executions, different results)
"""

import pytest

from src.ai.agents.soil_moisture.agent import SoilMoistureAgent
from src.ai.domain.models import SoilMoistureStatus


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def agent():
    """Create a fresh SoilMoistureAgent instance."""
    return SoilMoistureAgent()


def _make_context(
    surface_value: float | None = None,
    rootzone_value: float | None = None,
    surface_code: str = "SM_SURFACE",
    rootzone_code: str = "SM_ROOTZONE",
    surface_classification: str = "adequate",
    rootzone_classification: str = "adequate",
    surface_confidence: float = 0.85,
    rootzone_confidence: float = 0.85,
    warnings: list[str] | None = None,
) -> dict:
    """Helper to build a context dict with soil moisture indicators."""
    indicators = []

    if surface_value is not None:
        indicators.append(
            {
                "id": 1,
                "region_id": 1,
                "indicator_code": surface_code,
                "indicator_name": "Surface Soil Moisture",
                "value": surface_value,
                "unit": "m3/m3",
                "classification": surface_classification,
                "confidence": surface_confidence,
                "temporal_start": "2026-05-17T00:00:00Z",
                "temporal_end": "2026-05-24T00:00:00Z",
            }
        )

    if rootzone_value is not None:
        indicators.append(
            {
                "id": 2,
                "region_id": 1,
                "indicator_code": rootzone_code,
                "indicator_name": "Rootzone Soil Moisture",
                "value": rootzone_value,
                "unit": "m3/m3",
                "classification": rootzone_classification,
                "confidence": rootzone_confidence,
                "temporal_start": "2026-05-17T00:00:00Z",
                "temporal_end": "2026-05-24T00:00:00Z",
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
# Status Classification Tests
# ============================================================


class TestSurfaceClassification:
    """Test surface moisture status classification."""

    def test_critical_dry(self, agent):
        """Surface moisture < 0.15 → CRITICAL_DRY."""
        ctx = _make_context(surface_value=0.10)
        result = agent.execute(ctx)
        assert result["sm_surface_status"] == SoilMoistureStatus.CRITICAL_DRY.value

    def test_dry(self, agent):
        """Surface moisture 0.15-0.25 → DRY."""
        ctx = _make_context(surface_value=0.20)
        result = agent.execute(ctx)
        assert result["sm_surface_status"] == SoilMoistureStatus.DRY.value

    def test_normal(self, agent):
        """Surface moisture 0.25-0.35 → NORMAL."""
        ctx = _make_context(surface_value=0.30)
        result = agent.execute(ctx)
        assert result["sm_surface_status"] == SoilMoistureStatus.NORMAL.value

    def test_wet(self, agent):
        """Surface moisture 0.35-0.45 → WET."""
        ctx = _make_context(surface_value=0.40)
        result = agent.execute(ctx)
        assert result["sm_surface_status"] == SoilMoistureStatus.WET.value

    def test_critical_wet(self, agent):
        """Surface moisture >= 0.45 → CRITICAL_WET."""
        ctx = _make_context(surface_value=0.50)
        result = agent.execute(ctx)
        assert result["sm_surface_status"] == SoilMoistureStatus.CRITICAL_WET.value


class TestRootzoneClassification:
    """Test rootzone moisture status classification."""

    def test_critical_dry(self, agent):
        """Rootzone moisture < 0.20 → CRITICAL_DRY."""
        ctx = _make_context(rootzone_value=0.15)
        result = agent.execute(ctx)
        assert result["sm_rootzone_status"] == SoilMoistureStatus.CRITICAL_DRY.value

    def test_dry(self, agent):
        """Rootzone moisture 0.20-0.30 → DRY."""
        ctx = _make_context(rootzone_value=0.25)
        result = agent.execute(ctx)
        assert result["sm_rootzone_status"] == SoilMoistureStatus.DRY.value

    def test_normal(self, agent):
        """Rootzone moisture 0.30-0.45 → NORMAL."""
        ctx = _make_context(rootzone_value=0.38)
        result = agent.execute(ctx)
        assert result["sm_rootzone_status"] == SoilMoistureStatus.NORMAL.value

    def test_wet(self, agent):
        """Rootzone moisture 0.45-0.55 → WET."""
        ctx = _make_context(rootzone_value=0.50)
        result = agent.execute(ctx)
        assert result["sm_rootzone_status"] == SoilMoistureStatus.WET.value

    def test_critical_wet(self, agent):
        """Rootzone moisture >= 0.55 → CRITICAL_WET."""
        ctx = _make_context(rootzone_value=0.60)
        result = agent.execute(ctx)
        assert result["sm_rootzone_status"] == SoilMoistureStatus.CRITICAL_WET.value


# ============================================================
# Graceful Degradation Tests
# ============================================================


class TestGracefulDegradation:
    """Test graceful degradation when data is missing."""

    def test_no_data_unavailable(self, agent):
        """No SMAP indicators → UNAVAILABLE, confidence=0, completeness=0."""
        ctx = _make_context()  # No indicators
        result = agent.execute(ctx)

        assert result["sm_surface_status"] == SoilMoistureStatus.UNAVAILABLE.value
        assert result["sm_rootzone_status"] == SoilMoistureStatus.UNAVAILABLE.value
        assert result["surface_moisture"] is None
        assert result["rootzone_moisture"] is None
        assert result["confidence_score"] == 0.0
        assert result["data_completeness"] == 0.0

    def test_partial_data_only_surface(self, agent):
        """Only surface indicator → data_completeness=0.5."""
        ctx = _make_context(surface_value=0.28)
        result = agent.execute(ctx)

        assert result["data_completeness"] == 0.5
        assert result["surface_moisture"] == 0.28
        assert result["rootzone_moisture"] is None
        assert result["sm_surface_status"] == SoilMoistureStatus.NORMAL.value
        assert result["sm_rootzone_status"] == SoilMoistureStatus.UNAVAILABLE.value

    def test_never_crashes_empty_context(self, agent):
        """Empty context dict should not crash."""
        result = agent.execute({})

        assert result["sm_surface_status"] == SoilMoistureStatus.UNAVAILABLE.value
        assert result["sm_rootzone_status"] == SoilMoistureStatus.UNAVAILABLE.value
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
            surface_value=0.28,
            rootzone_value=0.35,
            surface_classification="good",
            rootzone_classification="good",
            surface_confidence=0.9,
            rootzone_confidence=0.9,
        )
        result = agent.execute(ctx)

        assert result["confidence_score"] > 0.5
        assert result["data_completeness"] == 1.0

    def test_stale_data_penalty(self, agent):
        """Stale data warning reduces freshness factor."""
        ctx = _make_context(
            surface_value=0.28,
            rootzone_value=0.35,
            warnings=["stale_data: true — latest data is 100 hours old"],
        )
        result = agent.execute(ctx)

        # Confidence should be lower than without stale warning
        ctx_fresh = _make_context(surface_value=0.28, rootzone_value=0.35)
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
        """Both surface and rootzone → completeness = 1.0."""
        ctx = _make_context(surface_value=0.28, rootzone_value=0.35)
        result = agent.execute(ctx)
        assert result["data_completeness"] == 1.0

    def test_partial_surface_only(self, agent):
        """Only surface → completeness = 0.5."""
        ctx = _make_context(surface_value=0.28)
        result = agent.execute(ctx)
        assert result["data_completeness"] == 0.5

    def test_partial_rootzone_only(self, agent):
        """Only rootzone → completeness = 0.5."""
        ctx = _make_context(rootzone_value=0.35)
        result = agent.execute(ctx)
        assert result["data_completeness"] == 0.5

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
        """NL output follows expected template format."""
        ctx = _make_context(surface_value=0.20, rootzone_value=0.35)
        result = agent.execute(ctx)

        nl = result["natural_language_output"]
        assert "Soil moisture status at" in nl
        assert "Surface:" in nl
        assert "Rootzone:" in nl
        assert "Trend:" in nl
        assert "Data confidence:" in nl

    def test_unavailable_nl_message(self, agent):
        """No data → specific unavailable message."""
        ctx = _make_context()
        result = agent.execute(ctx)

        assert (
            result["natural_language_output"]
            == "Soil moisture data is currently unavailable for this region."
        )

    def test_nl_includes_values(self, agent):
        """NL output includes actual moisture values."""
        ctx = _make_context(surface_value=0.28, rootzone_value=0.35)
        result = agent.execute(ctx)

        nl = result["natural_language_output"]
        assert "0.28" in nl
        assert "0.35" in nl


# ============================================================
# Stateless Behavior Tests
# ============================================================


class TestStatelessBehavior:
    """Test that agent is stateless between executions."""

    def test_different_contexts_different_results(self, agent):
        """Two executions with different contexts give different results."""
        ctx_dry = _make_context(surface_value=0.10, rootzone_value=0.15)
        ctx_wet = _make_context(surface_value=0.40, rootzone_value=0.50)

        result_dry = agent.execute(ctx_dry)
        result_wet = agent.execute(ctx_wet)

        assert result_dry["sm_surface_status"] != result_wet["sm_surface_status"]
        assert result_dry["surface_moisture"] != result_wet["surface_moisture"]
        assert result_dry["natural_language_output"] != result_wet["natural_language_output"]

    def test_same_context_same_results(self, agent):
        """Same context produces same result (deterministic)."""
        ctx = _make_context(surface_value=0.28, rootzone_value=0.35)

        result1 = agent.execute(ctx)
        result2 = agent.execute(ctx)

        assert result1 == result2


# ============================================================
# Indicator Code Variants Tests
# ============================================================


class TestIndicatorCodeVariants:
    """Test different SM indicator code formats."""

    def test_sm_index_fallback(self, agent):
        """SM_INDEX used as fallback for surface moisture."""
        ctx = _make_context(
            surface_value=0.28,
            surface_code="SM_INDEX",
            rootzone_value=None,
        )
        result = agent.execute(ctx)

        assert result["surface_moisture"] == 0.28
        assert result["data_completeness"] == 0.5  # partial (no rootzone)

    def test_soil_moisture_generic_code(self, agent):
        """SOIL_MOISTURE generic code treated as surface."""
        ctx = _make_context(
            surface_value=0.30,
            surface_code="SOIL_MOISTURE",
            rootzone_value=0.40,
        )
        result = agent.execute(ctx)

        assert result["surface_moisture"] == 0.30
        assert result["rootzone_moisture"] == 0.40
        assert result["data_completeness"] == 1.0

    def test_non_sm_indicators_ignored(self, agent):
        """Non-SM indicators do not affect results."""
        ctx = {
            "regions": [{"id": 1, "name": "Test"}],
            "layers": [],
            "indicators": [
                {
                    "id": 1,
                    "region_id": 1,
                    "indicator_code": "NDVI",
                    "indicator_name": "Vegetation Index",
                    "value": 0.65,
                    "unit": "index",
                    "classification": "good",
                    "confidence": 0.9,
                    "temporal_start": "2026-05-17",
                    "temporal_end": "2026-05-24",
                }
            ],
            "risk_assessments": [],
            "metadata": {"entity_counts": {"indicators": 1}},
            "warnings": [],
        }
        result = agent.execute(ctx)

        assert result["sm_surface_status"] == SoilMoistureStatus.UNAVAILABLE.value
        assert result["data_completeness"] == 0.0


# ============================================================
# Agent Contract Tests
# ============================================================


class TestAgentContract:
    """Test agent contract compliance."""

    def test_has_name_attribute(self, agent):
        """Agent has a name attribute."""
        assert hasattr(agent, "name")
        assert agent.name == "soil-moisture"

    def test_execute_returns_dict(self, agent):
        """Execute method returns a dict."""
        ctx = _make_context(surface_value=0.28, rootzone_value=0.35)
        result = agent.execute(ctx)
        assert isinstance(result, dict)

    def test_execute_has_all_required_fields(self, agent):
        """Execute result has all required SoilMoistureOutput fields."""
        ctx = _make_context(surface_value=0.28, rootzone_value=0.35)
        result = agent.execute(ctx)

        required_fields = [
            "surface_moisture",
            "rootzone_moisture",
            "sm_surface_status",
            "sm_rootzone_status",
            "trend_7d",
            "anomaly_pct",
            "confidence_score",
            "data_completeness",
            "natural_language_output",
        ]

        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_confidence_in_valid_range(self, agent):
        """Confidence score is always between 0 and 1."""
        ctx = _make_context(surface_value=0.28, rootzone_value=0.35)
        result = agent.execute(ctx)
        assert 0.0 <= result["confidence_score"] <= 1.0

    def test_data_completeness_in_valid_range(self, agent):
        """Data completeness is always between 0 and 1."""
        ctx = _make_context(surface_value=0.28, rootzone_value=0.35)
        result = agent.execute(ctx)
        assert 0.0 <= result["data_completeness"] <= 1.0

    def test_no_init_state(self, agent):
        """Agent __init__ has no state beyond name."""
        # Only 'name' should be set in __init__
        assert set(vars(agent).keys()) == {"name"}
