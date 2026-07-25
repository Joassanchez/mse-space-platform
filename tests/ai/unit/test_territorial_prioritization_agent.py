"""Unit tests for TerritorialPrioritizationAgent (AGENT-RISK-PR-001)."""

import pytest

from src.ai.agents.territorial_prioritization.agent import TerritorialPrioritizationAgent


@pytest.fixture
def agent():
    return TerritorialPrioritizationAgent()


def _make_ctx(pop_density: float | None = None) -> dict:
    meta = {}
    if pop_density is not None:
        meta["population_density"] = pop_density
    return {
        "regions": [{"id": 1, "name": "Zone A", "metadata": meta}],
        "risk_output": {"risk_level": "high"},
    }


class TestPrioritization:
    def test_single_zone(self, agent):
        ctx = _make_ctx(pop_density=0.8)
        result = agent.execute(ctx)
        assert len(result["priority_zones"]) == 1
        assert len(result["ranking"]) == 1
        assert result["ranking"][0] == "Zone A"

    def test_priority_score_from_density(self, agent):
        ctx = _make_ctx(pop_density=0.9)
        result = agent.execute(ctx)
        zone = result["priority_zones"][0]
        assert zone["priority_score"] >= 0.5
        assert zone["zone_name"] == "Zone A"


class TestContract:
    def test_has_name(self, agent):
        assert agent.name == "territorial_prioritization"

    def test_execute_returns_dict(self, agent):
        result = agent.execute(_make_ctx())
        assert isinstance(result, dict)

    def test_required_fields(self, agent):
        result = agent.execute(_make_ctx())
        for f in ("priority_zones", "ranking", "confidence_score",
                  "data_completeness", "natural_language_output"):
            assert f in result
