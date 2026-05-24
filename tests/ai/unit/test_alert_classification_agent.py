"""Tests for AlertClassificationAgent."""

import pytest
from src.ai.agents.alert_classification.agent import AlertClassificationAgent


@pytest.fixture
def agent():
    return AlertClassificationAgent()


def _ctx(hydric=None, risk=None, regions=None):
    return {
        "hydric_output": hydric or {},
        "risk_output": risk or {},
        "regions": regions or [{"id": 1, "name": "Test"}],
    }


class TestSeverity:
    def test_critical(self, agent):
        r = agent.execute(_ctx(hydric={"overall_hydric_condition": "critical"}))
        assert r["severity"] == "critical"

    def test_alert(self, agent):
        r = agent.execute(_ctx(hydric={"overall_hydric_condition": "stressed"}))
        assert r["severity"] == "alert"

    def test_warning(self, agent):
        r = agent.execute(_ctx(hydric={"overall_hydric_condition": "moderate"}))
        assert r["severity"] == "warning"


class TestContract:
    def test_has_name(self, agent):
        assert agent.name == "alert_classification"

    def test_required_fields(self, agent):
        r = agent.execute(_ctx())
        for f in ("severity", "event_type", "affected_zones", "confidence_score", "natural_language_output"):
            assert f in r
