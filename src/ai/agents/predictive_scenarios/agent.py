"""PredictiveScenariosAgent — AGENT-RISK-SC-001.

Stateless agent that projects risk scenarios at 7, 30, and 90 day horizons.
For MVP: deterministic template-based projections using current risk level
and hydric condition as inputs.
"""

from typing import Any

from src.ai.agents.predictive_scenarios.prompts.templates import NL_TEMPLATE, UNAVAILABLE_MSG
from src.ai.agents.predictive_scenarios.schemas import (
    PredictiveScenariosOutputSchema,
    ScenarioSchema,
)
from src.ai.domain.models import RiskLevel


class PredictiveScenariosAgent:
    """Stateless predictive scenarios agent."""

    def __init__(self) -> None:
        self.name = "predictive_scenarios"

    def execute(self, context: dict, **kwargs: Any) -> dict:
        risk_output = context.get("risk_output", {})

        risk_level = risk_output.get("risk_level", "low")
        hydric_condition = context.get("hydric_output", {}).get(
            "overall_hydric_condition", "moderate"
        )

        scenarios = self._build_scenarios(risk_level, hydric_condition)

        confidence = 0.6 if scenarios else 0.0
        data_completeness = 0.7  # MVP: always partial without real models

        probable_7d = scenarios[0].description if scenarios else "N/A"
        nl = NL_TEMPLATE.format(
            count=len(scenarios),
            probable_7d=probable_7d,
            confidence=confidence,
        )

        raw = {
            "scenarios": [s.model_dump() for s in scenarios],
            "confidence_score": round(confidence, 4),
            "data_completeness": round(data_completeness, 4),
            "natural_language_output": nl,
        }
        return PredictiveScenariosOutputSchema(**raw).model_dump(mode="json")

    def _build_scenarios(
        self, risk_level: str, hydric: str
    ) -> list[ScenarioSchema]:
        scenarios = []

        # Scenario descriptions based on current conditions
        if risk_level in ("high", "critical"):
            optimistic = "Conditions may stabilize with preventive measures"
            probable = "Risk conditions likely to persist or worsen"
            pessimistic = "Deterioration expected without intervention"
        elif risk_level == "moderate":
            optimistic = "Gradual improvement expected"
            probable = "Stable conditions in the short term"
            pessimistic = "Potential escalation if conditions worsen"
        else:
            optimistic = "Favorable conditions expected to continue"
            probable = "Low risk conditions persist"
            pessimistic = "Minor deterioration possible"

        horizons = [
            (7, "short term"),
            (30, "medium term"),
            (90, "long term"),
        ]

        probs = {"probable": 0.6, "pessimistic": 0.3, "optimistic": 0.1}

        for horizon, horizon_name in horizons:
            for stype, base_prob in probs.items():
                scenarios.append(ScenarioSchema(
                    horizon_days=horizon,
                    scenario_type=stype,
                    risk_level=risk_level,
                    probability_score=round(base_prob, 2),
                    description=locals()[stype],
                ))

        return scenarios
