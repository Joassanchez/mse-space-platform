"""Unit tests for DroughtAgent (AGENT-HYD-DR-001).

Tests cover:
- All drought categories (NONE, MILD, MODERATE, SEVERE with SPI values)
- No SPI data (graceful → NONE)
- Partial data (only SPI_30d, no SPI_90d)
- SPI_90d preference over SPI_30d
- Soil moisture escalation/de-escalation
- Trend calculation
- Confidence and completeness
- Drought signal mapping
- Template NL output
- Stateless behavior
"""

import pytest

from src.ai.agents.drought.agent import DroughtAgent
from src.ai.domain.models import DroughtCategory, DroughtSignal


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def agent():
    """Create a fresh DroughtAgent instance."""
    return DroughtAgent()


def _make_context(
    spi_30d: float | None = None,
    spi_90d: float | None = None,
    soil_moisture_classification: str | None = None,
    warnings: list[str] | None = None,
    spi_30d_classification: str = "adequate",
    spi_90d_classification: str = "adequate",
    spi_30d_confidence: float = 0.85,
    spi_90d_confidence: float = 0.85,
    duration_weeks: int | None = None,
    spatial_extent_pct: float | None = None,
) -> dict:
    """Helper to build a context dict with drought indicators."""
    indicators = []

    if spi_30d is not None:
        indicators.append(
            {
                "id": 1,
                "region_id": 1,
                "indicator_code": "SPI_30D",
                "indicator_name": "SPI 30-day",
                "value": spi_30d,
                "unit": "index",
                "classification": spi_30d_classification,
                "confidence": spi_30d_confidence,
                "temporal_start": "2026-04-24T00:00:00Z",
                "temporal_end": "2026-05-24T00:00:00Z",
                "duration_weeks": duration_weeks,
                "spatial_extent_pct": spatial_extent_pct,
            }
        )

    if spi_90d is not None:
        indicators.append(
            {
                "id": 2,
                "region_id": 1,
                "indicator_code": "SPI_90D",
                "indicator_name": "SPI 90-day",
                "value": spi_90d,
                "unit": "index",
                "classification": spi_90d_classification,
                "confidence": spi_90d_confidence,
                "temporal_start": "2026-02-24T00:00:00Z",
                "temporal_end": "2026-05-24T00:00:00Z",
            }
        )

    if soil_moisture_classification is not None:
        indicators.append(
            {
                "id": 3,
                "region_id": 1,
                "indicator_code": "SM_SURFACE",
                "indicator_name": "Surface Soil Moisture",
                "value": 0.20,
                "unit": "m3/m3",
                "classification": soil_moisture_classification,
                "confidence": 0.80,
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
# Drought Category Classification Tests
# ============================================================


class TestDroughtCategoryClassification:
    """Test SPI-based drought category classification."""

    def test_none_spi_positive(self, agent):
        """SPI >= -1.0 → NONE (positive SPI)."""
        ctx = _make_context(spi_30d=0.5, spi_90d=0.3)
        result = agent.execute(ctx)
        assert result["drought_category"] == DroughtCategory.NONE.value

    def test_none_spi_near_zero(self, agent):
        """SPI = -0.5 → NONE."""
        ctx = _make_context(spi_30d=-0.5, spi_90d=-0.8)
        result = agent.execute(ctx)
        assert result["drought_category"] == DroughtCategory.NONE.value

    def test_none_spi_boundary(self, agent):
        """SPI = -1.0 → NONE (boundary)."""
        ctx = _make_context(spi_30d=-1.0, spi_90d=-1.0)
        result = agent.execute(ctx)
        assert result["drought_category"] == DroughtCategory.NONE.value

    def test_mild_drought(self, agent):
        """-1.5 <= SPI < -1.0 → MILD."""
        ctx = _make_context(spi_30d=-1.2, spi_90d=-1.3)
        result = agent.execute(ctx)
        assert result["drought_category"] == DroughtCategory.MILD.value

    def test_moderate_drought(self, agent):
        """-2.0 <= SPI < -1.5 → MODERATE."""
        ctx = _make_context(spi_30d=-1.7, spi_90d=-1.8)
        result = agent.execute(ctx)
        assert result["drought_category"] == DroughtCategory.MODERATE.value

    def test_severe_drought(self, agent):
        """SPI < -2.0 → SEVERE."""
        ctx = _make_context(spi_30d=-2.2, spi_90d=-2.3)
        result = agent.execute(ctx)
        assert result["drought_category"] == DroughtCategory.SEVERE.value

    def test_extreme_drought_maps_to_severe(self, agent):
        """SPI < -2.5 → SEVERE (EXTREME reserved, MVP uses SEVERE)."""
        ctx = _make_context(spi_30d=-2.8, spi_90d=-3.0)
        result = agent.execute(ctx)
        assert result["drought_category"] == DroughtCategory.SEVERE.value


# ============================================================
# SPI Preference Tests
# ============================================================


class TestSPIPreference:
    """Test SPI_90d preference over SPI_30d."""

    def test_prefers_spi_90d_over_spi_30d(self, agent):
        """When both available, SPI_90d determines category."""
        # SPI_30d = -0.8 (NONE), SPI_90d = -1.3 (MILD) → should be MILD
        ctx = _make_context(spi_30d=-0.8, spi_90d=-1.3)
        result = agent.execute(ctx)
        assert result["drought_category"] == DroughtCategory.MILD.value

    def test_uses_spi_30d_when_90d_missing(self, agent):
        """Only SPI_30d available → use it for classification."""
        ctx = _make_context(spi_30d=-1.7, spi_90d=None)
        result = agent.execute(ctx)
        assert result["drought_category"] == DroughtCategory.MODERATE.value

    def test_uses_spi_90d_when_30d_missing(self, agent):
        """Only SPI_90d available → use it for classification."""
        ctx = _make_context(spi_30d=None, spi_90d=-1.2)
        result = agent.execute(ctx)
        assert result["drought_category"] == DroughtCategory.MILD.value


# ============================================================
# Graceful Degradation Tests
# ============================================================


class TestGracefulDegradation:
    """Test graceful degradation when data is missing."""

    def test_no_spi_data_none(self, agent):
        """No SPI indicators → NONE, confidence=0, completeness=0."""
        ctx = _make_context()
        result = agent.execute(ctx)

        assert result["drought_category"] == DroughtCategory.NONE.value
        assert result["drought_signal"] == DroughtSignal.NONE.value
        assert result["spi_30d"] is None
        assert result["spi_90d"] is None
        assert result["confidence_score"] == 0.0
        assert result["data_completeness"] == 0.0

    def test_never_crashes_empty_context(self, agent):
        """Empty context dict should not crash."""
        result = agent.execute({})

        assert result["drought_category"] == DroughtCategory.NONE.value
        assert result["trend"] == "stable"
        assert result["confidence_score"] == 0.0

    def test_partial_data_only_spi_30d(self, agent):
        """Only SPI_30d → data_completeness=0.5."""
        ctx = _make_context(spi_30d=-1.2, spi_90d=None)
        result = agent.execute(ctx)

        assert result["data_completeness"] == 0.5
        assert result["spi_30d"] == -1.2
        assert result["spi_90d"] is None


# ============================================================
# Soil Moisture Escalation/De-escalation Tests
# ============================================================


class TestSoilMoistureAdjustment:
    """Test soil moisture escalation and de-escalation logic."""

    def test_dry_soil_escalates_none_to_mild(self, agent):
        """SPI NONE + dry soil → MILD."""
        ctx = _make_context(
            spi_30d=-0.5,
            spi_90d=-0.5,
            soil_moisture_classification="dry",
        )
        result = agent.execute(ctx)
        assert result["drought_category"] == DroughtCategory.MILD.value

    def test_dry_soil_escalates_mild_to_moderate(self, agent):
        """SPI MILD + dry soil → MODERATE."""
        ctx = _make_context(
            spi_30d=-1.2,
            spi_90d=-1.2,
            soil_moisture_classification="dry",
        )
        result = agent.execute(ctx)
        assert result["drought_category"] == DroughtCategory.MODERATE.value

    def test_dry_soil_escalates_moderate_to_severe(self, agent):
        """SPI MODERATE + dry soil → SEVERE."""
        ctx = _make_context(
            spi_30d=-1.7,
            spi_90d=-1.7,
            soil_moisture_classification="dry",
        )
        result = agent.execute(ctx)
        assert result["drought_category"] == DroughtCategory.SEVERE.value

    def test_critical_dry_soil_escalates(self, agent):
        """CRITICAL_DRY soil also triggers escalation."""
        ctx = _make_context(
            spi_30d=-1.2,
            spi_90d=-1.2,
            soil_moisture_classification="critical_dry",
        )
        result = agent.execute(ctx)
        assert result["drought_category"] == DroughtCategory.MODERATE.value

    def test_wet_soil_de_escalates_mild_to_none(self, agent):
        """SPI MILD + wet soil → NONE."""
        ctx = _make_context(
            spi_30d=-1.2,
            spi_90d=-1.2,
            soil_moisture_classification="wet",
        )
        result = agent.execute(ctx)
        assert result["drought_category"] == DroughtCategory.NONE.value

    def test_wet_soil_de_escalates_moderate_to_mild(self, agent):
        """SPI MODERATE + wet soil → MILD."""
        ctx = _make_context(
            spi_30d=-1.7,
            spi_90d=-1.7,
            soil_moisture_classification="wet",
        )
        result = agent.execute(ctx)
        assert result["drought_category"] == DroughtCategory.MILD.value

    def test_normal_soil_de_escalates(self, agent):
        """NORMAL soil also triggers de-escalation."""
        ctx = _make_context(
            spi_30d=-1.2,
            spi_90d=-1.2,
            soil_moisture_classification="normal",
        )
        result = agent.execute(ctx)
        assert result["drought_category"] == DroughtCategory.NONE.value

    def test_no_soil_moisture_no_adjustment(self, agent):
        """No soil moisture data → category unchanged."""
        ctx = _make_context(spi_30d=-1.7, spi_90d=-1.7)
        result = agent.execute(ctx)
        assert result["drought_category"] == DroughtCategory.MODERATE.value


# ============================================================
# Drought Signal Tests
# ============================================================


class TestDroughtSignal:
    """Test drought signal calculation (simplified for orchestrator)."""

    def test_signal_none(self, agent):
        """DroughtCategory.NONE → DroughtSignal.NONE."""
        ctx = _make_context(spi_30d=0.0, spi_90d=0.0)
        result = agent.execute(ctx)
        assert result["drought_signal"] == DroughtSignal.NONE.value

    def test_signal_mild(self, agent):
        """DroughtCategory.MILD → DroughtSignal.MILD."""
        ctx = _make_context(spi_30d=-1.2, spi_90d=-1.2)
        result = agent.execute(ctx)
        assert result["drought_signal"] == DroughtSignal.MILD.value

    def test_signal_moderate(self, agent):
        """DroughtCategory.MODERATE → DroughtSignal.MODERATE."""
        ctx = _make_context(spi_30d=-1.7, spi_90d=-1.7)
        result = agent.execute(ctx)
        assert result["drought_signal"] == DroughtSignal.MODERATE.value

    def test_signal_severe_from_severe(self, agent):
        """DroughtCategory.SEVERE → DroughtSignal.SEVERE."""
        ctx = _make_context(spi_30d=-2.2, spi_90d=-2.2)
        result = agent.execute(ctx)
        assert result["drought_signal"] == DroughtSignal.SEVERE.value

    def test_signal_severe_from_extreme(self, agent):
        """DroughtCategory.EXTREME → DroughtSignal.SEVERE (collapsed)."""
        ctx = _make_context(spi_30d=-3.0, spi_90d=-3.0)
        result = agent.execute(ctx)
        assert result["drought_signal"] == DroughtSignal.SEVERE.value


# ============================================================
# Trend Calculation Tests
# ============================================================


class TestTrendCalculation:
    """Test trend determination from SPI comparison."""

    def test_improving_trend(self, agent):
        """SPI_30d > SPI_90d → improving (less negative = improving)."""
        ctx = _make_context(spi_30d=-0.8, spi_90d=-1.5)
        result = agent.execute(ctx)
        assert result["trend"] == "improving"

    def test_worsening_trend(self, agent):
        """SPI_30d < SPI_90d → worsening (more negative = worsening)."""
        ctx = _make_context(spi_30d=-1.8, spi_90d=-1.2)
        result = agent.execute(ctx)
        assert result["trend"] == "worsening"

    def test_stable_trend_equal(self, agent):
        """SPI_30d == SPI_90d → stable."""
        ctx = _make_context(spi_30d=-1.0, spi_90d=-1.0)
        result = agent.execute(ctx)
        assert result["trend"] == "stable"

    def test_stable_trend_partial_data(self, agent):
        """Only one SPI available → stable."""
        ctx = _make_context(spi_30d=-1.5, spi_90d=None)
        result = agent.execute(ctx)
        assert result["trend"] == "stable"

    def test_stable_trend_no_data(self, agent):
        """No SPI data → stable."""
        ctx = _make_context()
        result = agent.execute(ctx)
        assert result["trend"] == "stable"


# ============================================================
# Confidence Calculation Tests
# ============================================================


class TestConfidenceCalculation:
    """Test confidence score calculation."""

    def test_full_data_high_confidence(self, agent):
        """Full data with good quality → high confidence."""
        ctx = _make_context(
            spi_30d=-1.2,
            spi_90d=-1.3,
            spi_30d_classification="good",
            spi_90d_classification="good",
            spi_30d_confidence=0.9,
            spi_90d_confidence=0.9,
        )
        result = agent.execute(ctx)

        assert result["confidence_score"] > 0.5
        assert result["data_completeness"] == 1.0

    def test_stale_data_penalty(self, agent):
        """Stale data warning reduces freshness factor."""
        ctx = _make_context(
            spi_30d=-1.2,
            spi_90d=-1.3,
            warnings=["stale_data: true — latest data is 100 hours old"],
        )
        result = agent.execute(ctx)

        # Confidence should be lower than without stale warning
        ctx_fresh = _make_context(spi_30d=-1.2, spi_90d=-1.3)
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
        """Both SPI_30d and SPI_90d → completeness = 1.0."""
        ctx = _make_context(spi_30d=-1.2, spi_90d=-1.3)
        result = agent.execute(ctx)
        assert result["data_completeness"] == 1.0

    def test_partial_spi_30d_only(self, agent):
        """Only SPI_30d → completeness = 0.5."""
        ctx = _make_context(spi_30d=-1.2, spi_90d=None)
        result = agent.execute(ctx)
        assert result["data_completeness"] == 0.5

    def test_partial_spi_90d_only(self, agent):
        """Only SPI_90d → completeness = 0.5."""
        ctx = _make_context(spi_30d=None, spi_90d=-1.3)
        result = agent.execute(ctx)
        assert result["data_completeness"] == 0.5

    def test_no_data(self, agent):
        """No SPI indicators → completeness = 0.0."""
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
        ctx = _make_context(spi_30d=-1.2, spi_90d=-1.5)
        result = agent.execute(ctx)

        nl = result["natural_language_output"]
        assert "Drought conditions:" in nl
        assert "SPI 30d:" in nl
        assert "SPI 90d:" in nl
        assert "Trend:" in nl
        assert "Data confidence:" in nl

    def test_unavailable_nl_message(self, agent):
        """No data → specific unavailable message."""
        ctx = _make_context()
        result = agent.execute(ctx)

        assert (
            result["natural_language_output"]
            == "Drought data is currently unavailable for this region."
        )

    def test_nl_includes_spi_values(self, agent):
        """NL output includes actual SPI values."""
        ctx = _make_context(spi_30d=-1.2, spi_90d=-1.5)
        result = agent.execute(ctx)

        nl = result["natural_language_output"]
        assert "-1.20" in nl
        assert "-1.50" in nl


# ============================================================
# Stateless Behavior Tests
# ============================================================


class TestStatelessBehavior:
    """Test that agent is stateless between executions."""

    def test_different_contexts_different_results(self, agent):
        """Two executions with different contexts give different results."""
        ctx_none = _make_context(spi_30d=0.5, spi_90d=0.3)
        ctx_severe = _make_context(spi_30d=-2.2, spi_90d=-2.5)

        result_none = agent.execute(ctx_none)
        result_severe = agent.execute(ctx_severe)

        assert result_none["drought_category"] != result_severe["drought_category"]
        assert result_none["natural_language_output"] != result_severe["natural_language_output"]

    def test_same_context_same_results(self, agent):
        """Same context produces same result (deterministic)."""
        ctx = _make_context(spi_30d=-1.2, spi_90d=-1.5)

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
        assert agent.name == "drought"

    def test_execute_returns_dict(self, agent):
        """Execute method returns a dict."""
        ctx = _make_context(spi_30d=-1.2, spi_90d=-1.5)
        result = agent.execute(ctx)
        assert isinstance(result, dict)

    def test_execute_has_all_required_fields(self, agent):
        """Execute result has all required DroughtOutput fields."""
        ctx = _make_context(spi_30d=-1.2, spi_90d=-1.5)
        result = agent.execute(ctx)

        required_fields = [
            "spi_30d",
            "spi_90d",
            "drought_category",
            "drought_signal",
            "duration_weeks",
            "spatial_extent_pct",
            "trend",
            "confidence_score",
            "data_completeness",
            "natural_language_output",
        ]

        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_confidence_in_valid_range(self, agent):
        """Confidence score is always between 0 and 1."""
        ctx = _make_context(spi_30d=-1.2, spi_90d=-1.5)
        result = agent.execute(ctx)
        assert 0.0 <= result["confidence_score"] <= 1.0

    def test_data_completeness_in_valid_range(self, agent):
        """Data completeness is always between 0 and 1."""
        ctx = _make_context(spi_30d=-1.2, spi_90d=-1.5)
        result = agent.execute(ctx)
        assert 0.0 <= result["data_completeness"] <= 1.0

    def test_no_init_state(self, agent):
        """Agent __init__ has no state beyond name."""
        assert set(vars(agent).keys()) == {"name"}

    def test_non_drought_indicators_ignored(self, agent):
        """Non-drought indicators do not affect results."""
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

        assert result["drought_category"] == DroughtCategory.NONE.value
        assert result["data_completeness"] == 0.0

    def test_duration_and_spatial_extent_extracted(self, agent):
        """Duration and spatial extent are extracted from indicator metadata."""
        ctx = _make_context(
            spi_30d=-1.2,
            spi_90d=-1.5,
            duration_weeks=8,
            spatial_extent_pct=45.0,
        )
        result = agent.execute(ctx)

        assert result["duration_weeks"] == 8
        assert result["spatial_extent_pct"] == 45.0
