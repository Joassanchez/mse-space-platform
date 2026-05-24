"""Tests for ExecutiveSummaryAgent."""

import pytest
from src.ai.agents.executive_summary.agent import ExecutiveSummaryAgent


@pytest.fixture
def agent():
    return ExecutiveSummaryAgent()


def _ctx(severity="alert", event="drought"):
    return {
        "alert_classification": {"severity": severity, "event_type": event},
        "risk_communication": {"messages": {"municipalities": "msg1", "producers": "msg2"}},
    }


class TestSummary:
    def test_summary_includes_severity(self, agent):
        r = agent.execute(_ctx(severity="critical"))
        assert "critical" in r["executive_summary"]

    def test_summary_includes_event_type(self, agent):
        r = agent.execute(_ctx(event="flood"))
        assert "flood" in r["executive_summary"]


class TestContract:
    def test_has_name(self, agent):
        assert agent.name == "executive_summary"

    def test_required_fields(self, agent):
        r = agent.execute(_ctx())
        for f in ("executive_summary", "situation", "risk", "actions", "confidence_score"):
            assert f in r
