"""Unit tests for Context Engine (mocked repositories).

Tests:
- Context building with mocked M3 repositories
- Summarization with limits
- Stale data warning
- Field selection per entity
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.ai.domain.errors import ContextError
from src.geospatial.domain.models import Indicator, ProcessedLayer, Region, RiskAssessment
from src.ai.infrastructure.context.context_engine import ContextEngineImpl


@pytest.fixture
def mock_repos():
    """Create mock repositories with test data."""
    region_repo = MagicMock()
    layer_repo = MagicMock()
    indicator_repo = MagicMock()
    risk_repo = MagicMock()

    # Create test region
    test_region = Region(
        id=1,
        name="Test Region",
        region_type="administrative",
        country="Argentina",
        province="Buenos Aires",
        bbox=[-60.0, -35.0, -58.0, -33.0],
        area_km2=10000.0,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    region_repo.get_by_id.return_value = test_region

    # Create test indicators
    test_indicators = [
        Indicator(
            id=1,
            region_id=1,
            indicator_code="SM_INDEX",
            indicator_name="Soil Moisture Index",
            value=0.45,
            unit="m3/m3",
            classification="normal",
            confidence=0.8,
            temporal_start=(datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat(),
            temporal_end=datetime.now(timezone.utc).date().isoformat(),
        ),
        Indicator(
            id=2,
            region_id=1,
            indicator_code="NDVI",
            indicator_name="Vegetation Index",
            value=0.65,
            unit="index",
            classification="healthy",
            confidence=0.9,
            temporal_start=(datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat(),
            temporal_end=datetime.now(timezone.utc).date().isoformat(),
        ),
    ]
    indicator_repo.find_by_region.return_value = test_indicators

    # Create test risk assessments
    test_risks = [
        RiskAssessment(
            id=1,
            region_id=1,
            risk_type="drought",
            risk_level="medium",
            risk_score=0.5,
            confidence=0.7,
            explanation="Moderate drought risk based on soil moisture levels",
            temporal_start=(datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat(),
            temporal_end=datetime.now(timezone.utc).date().isoformat(),
        ),
    ]
    risk_repo.find_by_region_and_date.return_value = test_risks

    return {
        "region_repo": region_repo,
        "layer_repo": layer_repo,
        "indicator_repo": indicator_repo,
        "risk_repo": risk_repo,
    }


@pytest.fixture
def engine(mock_repos):
    """Create ContextEngineImpl with mock repositories."""
    return ContextEngineImpl(
        region_repo=mock_repos["region_repo"],
        layer_repo=mock_repos["layer_repo"],
        indicator_repo=mock_repos["indicator_repo"],
        risk_repo=mock_repos["risk_repo"],
    )


class TestContextEngineBuildContext:
    """Test context building."""

    def test_build_context_returns_structured_output(self, engine):
        """build_context returns dict with expected keys."""
        result = engine.build_context(region_ids=[1])

        assert "regions" in result
        assert "indicators" in result
        assert "risk_assessments" in result
        assert "metadata" in result
        assert "warnings" in result

    def test_build_context_includes_region_data(self, engine):
        """Context includes region summary fields."""
        result = engine.build_context(region_ids=[1])

        assert len(result["regions"]) == 1
        region = result["regions"][0]
        assert region["id"] == 1
        assert region["name"] == "Test Region"
        assert region["country"] == "Argentina"

    def test_build_context_includes_indicators(self, engine):
        """Context includes indicator data."""
        result = engine.build_context(region_ids=[1])

        assert len(result["indicators"]) == 2
        assert result["indicators"][0]["indicator_code"] == "SM_INDEX"

    def test_build_context_filters_by_indicator_codes(self, engine):
        """Context filters indicators by code when specified."""
        result = engine.build_context(
            region_ids=[1],
            indicator_codes=["SM_INDEX"],
        )

        assert len(result["indicators"]) == 1
        assert result["indicators"][0]["indicator_code"] == "SM_INDEX"

    def test_build_context_includes_risk_assessments(self, engine):
        """Context includes risk assessment data."""
        result = engine.build_context(region_ids=[1])

        assert len(result["risk_assessments"]) == 1
        assert result["risk_assessments"][0]["risk_type"] == "drought"

    def test_build_context_metadata_has_entity_counts(self, engine):
        """Context metadata includes entity counts."""
        result = engine.build_context(region_ids=[1])

        counts = result["metadata"]["entity_counts"]
        assert counts["regions"] == 1
        assert counts["indicators"] == 2
        assert counts["risk_assessments"] == 1

    def test_build_context_empty_region_ids_raises(self, engine):
        """build_context raises ContextError for empty region_ids."""
        with pytest.raises(ContextError, match="region_ids cannot be empty"):
            engine.build_context(region_ids=[])

    def test_build_context_missing_region_warns(self, engine, mock_repos):
        """build_context warns when a region is not found."""
        mock_repos["region_repo"].get_by_id.return_value = None

        result = engine.build_context(region_ids=[999])

        assert len(result["warnings"]) == 1
        assert "not found" in result["warnings"][0]


class TestContextEngineStaleData:
    """Test stale data warnings."""

    def test_stale_data_warning_when_old(self, engine, mock_repos):
        """Stale data warning is included when data exceeds max_age_hours."""
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).date().isoformat()

        # Override ALL repos to return old data — otherwise risks/region mask stale signal
        mock_repos["indicator_repo"].find_by_region.return_value = [
            Indicator(
                id=1,
                region_id=1,
                indicator_code="SM_INDEX",
                indicator_name="Soil Moisture Index",
                value=0.45,
                unit="m3/m3",
                classification="normal",
                confidence=0.8,
                temporal_start=old_date,
                temporal_end=old_date,
            ),
        ]
        mock_repos["risk_repo"].find_by_region_and_date.return_value = [
            RiskAssessment(
                id=1,
                region_id=1,
                risk_type="drought",
                risk_level="medium",
                risk_score=0.5,
                confidence=0.7,
                explanation="Old risk",
                temporal_start=old_date,
                temporal_end=old_date,
            ),
        ]
        mock_repos["region_repo"].get_by_id.return_value = Region(
            id=1,
            name="Old Region",
            region_type="administrative",
            country="Argentina",
            province="Bs As",
            updated_at=old_date,
        )

        result = engine.build_context(region_ids=[1], max_age_hours=720)

        assert any("stale_data" in w for w in result["warnings"])

    def test_no_stale_warning_when_fresh(self, engine):
        """No stale data warning when data is within threshold."""
        result = engine.build_context(region_ids=[1], max_age_hours=720)

        assert not any("stale_data" in w for w in result["warnings"])


class TestContextEngineSummarize:
    """Test context summarization."""

    def test_summarize_no_truncation_when_within_limit(self, engine):
        """Context is not truncated when within token limit."""
        context = engine.build_context(region_ids=[1])

        # Large token limit — no truncation needed
        result = engine.summarize_context(context, max_tokens=10000)

        assert result["truncated"] is False

    def test_summarize_truncates_when_over_limit(self, engine):
        """Context is truncated when exceeding token limit."""
        context = engine.build_context(region_ids=[1])

        # Very small token limit — must truncate
        result = engine.summarize_context(context, max_tokens=10)

        assert result["truncated"] is True

    def test_summarize_preserves_metadata(self, engine):
        """Summarized context preserves metadata."""
        context = engine.build_context(region_ids=[1])
        result = engine.summarize_context(context, max_tokens=10)

        assert "metadata" in result
        assert "entity_counts" in result["metadata"]

    def test_summarize_keeps_essential_region_fields(self, engine):
        """Summarized regions keep only essential fields."""
        context = engine.build_context(region_ids=[1])
        result = engine.summarize_context(context, max_tokens=10)

        if result["regions"]:
            region = result["regions"][0]
            assert "id" in region
            assert "name" in region
            # bbox and area_km2 should be stripped in summary
            assert "bbox" not in region
