"""Unit tests for PredictiveScenariosAgent (AGENT-RISK-SC-001)."""

import pytest

from src.ai.agents.predictive_scenarios.agent import PredictiveScenariosAgent


@pytest.fixture
def agent():
    return PredictiveScenariosAgent()


def _make_ctx(risk_level: str = "moderate", hydric: str = "moderate") -> dict:
    return {
        "risk_output": {"risk_level": risk_level},
        "hydric_output": {"overall_hydric_condition": hydric},
    }


class TestScenarios:
    def test_returns_9_scenarios(self, agent):
        """3 scenario types x 3 horizons = 9 scenarios."""
        ctx = _make_ctx()
        result = agent.execute(ctx)
        assert len(result["scenarios"]) == 9

    def test_critical_risk_level(self, agent):
        ctx = _make_ctx(risk_level="critical")
        result = agent.execute(ctx)
        descs = [s["description"] for s in result["scenarios"]]
        assert any("deterioration" in d or "worsen" in d for d in descs)

    def test_low_risk_optimistic(self, agent):
        ctx = _make_ctx(risk_level="low")
        result = agent.execute(ctx)
        optimistic = [s for s in result["scenarios"] if s["scenario_type"] == "optimistic"]
        assert any("favorable" in o["description"] or "continue" in o["description"] for o in optimistic)

    def test_scenario_has_horizons(self, agent):
        ctx = _make_ctx()
        result = agent.execute(ctx)
        horizons = {s["horizon_days"] for s in result["scenarios"]}
        assert horizons == {7, 30, 90}


class TestContract:
    def test_has_name(self, agent):
        assert agent.name == "predictive_scenarios"

    def test_required_fields(self, agent):
        ctx = _make_ctx()
        result = agent.execute(ctx)
        for f in ("scenarios", "confidence_score", "data_completeness",
                  "natural_language_output"):
            assert f in result

    def test_confidence_range(self, agent):
        ctx = _make_ctx()
        result = agent.execute(ctx)
        assert 0.0 <= result["confidence_score"] <= 1.0
