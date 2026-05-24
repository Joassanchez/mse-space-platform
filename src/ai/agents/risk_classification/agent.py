"""RiskClassificationAgent — AGENT-RISK-CL-001.

Stateless agent that assigns risk levels based on hydric-environmental
condition, historical risk data, land use, and infrastructure.
Consumes pre-built context from ContextEngine including territorial variables.
"""

from typing import Any

from src.ai.agents.risk_classification.prompts.templates import NL_TEMPLATE, UNAVAILABLE_MSG
from src.ai.agents.risk_classification.schemas import RiskClassificationOutputSchema
from src.ai.domain.models import HydricCondition, RiskLevel


class RiskClassificationAgent:
    """Stateless risk classification agent."""

    def __init__(self) -> None:
        self.name = "risk_classification"

    def execute(self, context: dict, **kwargs: Any) -> dict:
        indicators = context.get("indicators", [])
        regions = context.get("regions", [])
        hydric = context.get("hydric_output", {})

        # Extract hydric condition from pre-built hydric output
        hydric_condition = self._extract_hydric_condition(hydric)

        # Extract historical risk from indicators
        historical_risk = self._extract_historical_risk(indicators)

        # Extract territorial variables from region metadata
        land_use_risk, infra_risk = self._extract_territorial_risk(regions)

        # Compute risk level
        risk_level, risk_score, factors = self._compute_risk(
            hydric_condition, historical_risk, land_use_risk, infra_risk
        )

        # Data completeness
        found_codes = self._get_found_codes(context)
        data_completeness = self._calc_data_completeness(found_codes)

        # Confidence
        confidence = data_completeness * 0.8 if data_completeness > 0 else 0.0

        # NL output
        factors_str = ", ".join(factors) if factors else "none"
        nl = NL_TEMPLATE.format(
            risk_level=risk_level.value,
            score=risk_score,
            factors=factors_str,
            confidence=confidence,
        )

        raw = {
            "risk_level": risk_level.value,
            "risk_score": round(risk_score, 4),
            "contributing_factors": factors,
            "confidence_score": round(confidence, 4),
            "data_completeness": round(data_completeness, 4),
            "natural_language_output": nl,
        }
        return RiskClassificationOutputSchema(**raw).model_dump(mode="json")

    def _extract_hydric_condition(self, hydric: dict) -> str:
        return hydric.get("overall_hydric_condition", "moderate")

    def _extract_historical_risk(self, indicators: list[dict]) -> float:
        for ind in indicators:
            code = ind.get("indicator_code", "").upper()
            if code == "HISTORICAL_RISK":
                val = ind.get("value")
                return float(val) if val is not None else 0.5
        return 0.5

    def _extract_territorial_risk(
        self, regions: list[dict]
    ) -> tuple[float, float]:
        land_use_risk = 0.3
        infra_risk = 0.3
        for r in regions:
            meta = r.get("metadata", {})
            land_use_risk = meta.get("land_use_risk", land_use_risk)
            infra_risk = meta.get("infrastructure_risk", infra_risk)
        return land_use_risk, infra_risk

    def _compute_risk(
        self,
        hydric_condition: str,
        historical_risk: float,
        land_use_risk: float,
        infra_risk: float,
    ) -> tuple[RiskLevel, float, list[str]]:
        factors = []

        # Hydric condition weight: 0.4
        hydric_map = {
            "critical": 1.0, "stressed": 0.7,
            "moderate": 0.4, "optimal": 0.1,
        }
        hydric_score = hydric_map.get(hydric_condition, 0.4)
        if hydric_score > 0.5:
            factors.append(f"hydric_condition={hydric_condition}")

        # Historical risk weight: 0.3
        if historical_risk > 0.6:
            factors.append(f"historical_risk={historical_risk:.2f}")

        # Territorial weights: 0.15 each
        if land_use_risk > 0.5:
            factors.append("land_use_risk=high")
        if infra_risk > 0.5:
            factors.append("infrastructure_risk=high")

        risk_score = (
            hydric_score * 0.4
            + historical_risk * 0.3
            + land_use_risk * 0.15
            + infra_risk * 0.15
        )
        risk_score = max(0.0, min(1.0, risk_score))

        if risk_score >= 0.8:
            level = RiskLevel.CRITICAL
        elif risk_score >= 0.6:
            level = RiskLevel.HIGH
        elif risk_score >= 0.3:
            level = RiskLevel.MODERATE
        else:
            level = RiskLevel.LOW

        return level, risk_score, factors

    def _get_found_codes(self, context: dict) -> set[str]:
        codes = set()
        for ind in context.get("indicators", []):
            c = ind.get("indicator_code", "").upper()
            if c in {"HISTORICAL_RISK"}:
                codes.add(c)
        return codes

    def _calc_data_completeness(self, found: set[str]) -> float:
        if not found:
            return 0.0
        if "HISTORICAL_RISK" in found:
            return 1.0
        return 0.5
