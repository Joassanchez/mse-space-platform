"""Unit tests for ContextEngine.build_enriched_context()."""

from unittest.mock import MagicMock

import pytest

from src.ai.infrastructure.context.context_engine import ContextEngineImpl
from src.geospatial.domain.models import Region


@pytest.fixture
def repos():
    return {
        "region": MagicMock(),
        "layer": MagicMock(),
        "indicator": MagicMock(),
        "risk": MagicMock(),
        "weather": MagicMock(),
    }


@pytest.fixture
def engine(repos):
    repos["region"].get_by_id.return_value = Region(
        name="Test", country="AR", region_type="province"
    )
    repos["indicator"].find_by_region.return_value = []
    repos["risk"].find_by_region_and_date.return_value = []

    return ContextEngineImpl(
        region_repo=repos["region"],
        layer_repo=repos["layer"],
        indicator_repo=repos["indicator"],
        risk_repo=repos["risk"],
        weather_repo=repos["weather"],
    )


class TestBuildEnrichedContext:
    def test_basic_context_included(self, engine, repos):
        """build_enriched_context returns standard context fields."""
        ctx = engine.build_enriched_context(region_ids=[1])
        assert "regions" in ctx
        assert "indicators" in ctx

    def test_weather_attached_when_data_exists(self, engine, repos):
        """When weather_repo has data, weather key is populated."""
        repos["weather"].find_latest_by_region.return_value = MagicMock(
            region_id=1,
            observed_at="2026-05-24T12:00:00Z",
            temp_celsius=22.5,
            humidity_pct=65,
            wind_speed_ms=3.2,
            rainfall_mm=0.0,
            pressure_hpa=1013,
            weather_condition="clear",
            source="openweather",
        )

        ctx = engine.build_enriched_context(region_ids=[1])
        assert "weather" in ctx
        assert len(ctx["weather"]) == 1
        assert ctx["weather"][0]["temp_celsius"] == 22.5

    def test_weather_warning_when_no_data(self, engine, repos):
        """When no weather snapshots exist, a warning is added."""
        repos["weather"].find_latest_by_region.return_value = None

        ctx = engine.build_enriched_context(region_ids=[1])
        assert "weather" in ctx
        assert len(ctx["weather"]) == 0
        assert any("weather_data" in w for w in ctx.get("warnings", []))

    def test_weather_skipped_when_flag_false(self, engine, repos):
        """include_weather=False skips weather lookup."""
        ctx = engine.build_enriched_context(region_ids=[1], include_weather=False)
        assert "weather" not in ctx
        repos["weather"].find_latest_by_region.assert_not_called()

    def test_no_weather_repo_does_not_crash(self, repos):
        """ContextEngine without weather_repo handles gracefully."""
        engine = ContextEngineImpl(
            region_repo=repos["region"],
            layer_repo=repos["layer"],
            indicator_repo=repos["indicator"],
            risk_repo=repos["risk"],
            weather_repo=None,
        )
        ctx = engine.build_enriched_context(region_ids=[1])
        assert "weather" not in ctx
