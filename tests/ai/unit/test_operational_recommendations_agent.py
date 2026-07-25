"""Tests for OperationalRecommendationsAgent."""

import pytest
from src.ai.agents.operational_recommendations.agent import OperationalRecommendationsAgent


@pytest.fixture
def agent():
    return OperationalRecommendationsAgent()


def _ctx(event="drought", severity="critical"):
    return {"alert_classification": {"event_type": event, "severity": severity}}


class TestActions:
    def test_drought_critical_returns_actions(self, agent):
        r = agent.execute(_ctx(event="drought", severity="critical"))
        assert len(r["recommended_actions"]) >= 3
        assert any("emergencia" in a["action"] for a in r["recommended_actions"])

    def test_warning_returns_fewer_actions(self, agent):
        r = agent.execute(_ctx(event="drought", severity="warning"))
        assert len(r["recommended_actions"]) >= 1

    def test_unknown_event_returns_default(self, agent):
        r = agent.execute(_ctx(event="unknown_event", severity="info"))
        assert len(r["recommended_actions"]) >= 1


class TestContract:
    def test_has_name(self, agent):
        assert agent.name == "operational_recommendations"

    def test_required_fields(self, agent):
        r = agent.execute(_ctx())
        for f in ("recommended_actions", "confidence_score", "natural_language_output"):
            assert f in r
