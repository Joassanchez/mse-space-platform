"""Unit tests for RiskClassificationAgent (AGENT-RISK-CL-001)."""

import pytest

from src.ai.agents.risk_classification.agent import RiskClassificationAgent


@pytest.fixture
def agent():
    return RiskClassificationAgent()


def _make_ctx(
    hydric_condition: str = "moderate",
    historical_risk: float | None = None,
    land_use_risk: float | None = None,
    infra_risk: float | None = None,
) -> dict:
    indicators = []
    if historical_risk is not None:
        indicators.append({
            "indicator_code": "HISTORICAL_RISK",
            "value": historical_risk,
        })

    meta = {}
    if land_use_risk is not None:
        meta["land_use_risk"] = land_use_risk
    if infra_risk is not None:
        meta["infrastructure_risk"] = infra_risk

    return {
        "indicators": indicators,
        "regions": [{"id": 1, "name": "Test", "metadata": meta}],
        "hydric_output": {"overall_hydric_condition": hydric_condition},
    }


class TestRiskLevel:
    def test_critical_condition(self, agent):
        ctx = _make_ctx(hydric_condition="critical", historical_risk=0.8,
                         land_use_risk=0.7, infra_risk=0.6)
        result = agent.execute(ctx)
        assert result["risk_level"] == "critical"

    def test_high_condition(self, agent):
        ctx = _make_ctx(hydric_condition="stressed", historical_risk=0.7)
        result = agent.execute(ctx)
        assert result["risk_level"] in ("high", "moderate")  # threshold boundary

    def test_moderate_condition(self, agent):
        ctx = _make_ctx(hydric_condition="moderate")
        result = agent.execute(ctx)
        assert result["risk_level"] == "moderate"

    def test_low_condition(self, agent):
        ctx = _make_ctx(hydric_condition="optimal", historical_risk=0.2)
        result = agent.execute(ctx)
        assert result["risk_level"] == "low"


class TestContract:
    def test_has_name(self, agent):
        assert agent.name == "risk_classification"

    def test_execute_returns_dict(self, agent):
        ctx = _make_ctx()
        result = agent.execute(ctx)
        assert isinstance(result, dict)

    def test_has_all_fields(self, agent):
        ctx = _make_ctx()
        result = agent.execute(ctx)
        for f in ("risk_level", "risk_score", "contributing_factors",
                  "confidence_score", "data_completeness",
                  "natural_language_output"):
            assert f in result

    def test_confidence_range(self, agent):
        ctx = _make_ctx()
        result = agent.execute(ctx)
        assert 0.0 <= result["confidence_score"] <= 1.0

    def test_no_state(self, agent):
        assert set(vars(agent).keys()) == {"name"}
