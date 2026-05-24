"""TerritorialPrioritizationAgent — AGENT-RISK-PR-001.

Stateless agent that identifies priority zones based on risk level,
population exposure, and vulnerability. Consumes risk classification
output and territorial variables from context.
"""

from typing import Any

from src.ai.agents.territorial_prioritization.prompts.templates import (
    NL_TEMPLATE,
    UNAVAILABLE_MSG,
)
from src.ai.agents.territorial_prioritization.schemas import (
    PrioritizationZoneSchema,
    TerritorialPrioritizationOutputSchema,
)
from src.ai.domain.models import RiskLevel


class TerritorialPrioritizationAgent:
    """Stateless territorial prioritization agent."""

    def __init__(self) -> None:
        self.name = "territorial_prioritization"

    def execute(self, context: dict, **kwargs: Any) -> dict:
        regions = context.get("regions", [])
        risk_output = context.get("risk_output", {})

        zones = self._build_zones(regions, risk_output)
        zones.sort(key=lambda z: z.priority_score, reverse=True)
        ranking = [z.zone_name for z in zones]

        confidence = 0.7 if zones else 0.0
        data_completeness = min(len(zones) / 3, 1.0) if zones else 0.0

        top = ranking[0] if ranking else "none"
        nl = NL_TEMPLATE.format(
            count=len(zones), top=top, confidence=confidence
        )

        raw = {
            "priority_zones": [z.model_dump() for z in zones],
            "ranking": ranking,
            "confidence_score": round(confidence, 4),
            "data_completeness": round(data_completeness, 4),
            "natural_language_output": nl,
        }
        return TerritorialPrioritizationOutputSchema(**raw).model_dump(mode="json")

    def _build_zones(
        self, regions: list[dict], risk_output: dict
    ) -> list[PrioritizationZoneSchema]:
        zones = []
        for r in regions:
            meta = r.get("metadata", {})
            pop_density = meta.get("population_density", 0.0)
            priority = pop_density * 0.6 + 0.4  # base + density factor
            priority = min(priority, 1.0)

            zones.append(PrioritizationZoneSchema(
                zone_id=str(r.get("id", "")),
                zone_name=r.get("name", "unknown"),
                priority_score=round(priority, 4),
                risk_level=risk_output.get("risk_level", "low"),
                reason=f"population_density={pop_density:.2f}" if pop_density > 0 else "base_zone",
            ))
        return zones
