"""Tests for RiskCommunicationAgent."""

import pytest
from src.ai.agents.risk_communication.agent import RiskCommunicationAgent


@pytest.fixture
def agent():
    return RiskCommunicationAgent()


def _ctx(severity="warning", event="drought", regions=None):
    return {
        "hydric_output": {},
        "alert_classification": {"severity": severity, "event_type": event},
        "regions": regions or [{"id": 1, "name": "Cordoba"}],
    }


class TestMessages:
    def test_generates_all_audiences(self, agent):
        r = agent.execute(_ctx())
        assert len(r["messages"]) == 4
        assert "municipalities" in r["messages"]
        assert "producers" in r["messages"]
        assert "cooperatives" in r["messages"]
        assert "insurers" in r["messages"]

    def test_message_includes_event_type(self, agent):
        r = agent.execute(_ctx(event="flood"))
        msg = next(iter(r["messages"].values()))
        assert "flood" in msg


class TestContract:
    def test_has_name(self, agent):
        assert agent.name == "risk_communication"

    def test_required_fields(self, agent):
        r = agent.execute(_ctx())
        for f in ("messages", "confidence_score", "natural_language_output"):
            assert f in r
