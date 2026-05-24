"""OperationalRecommendationsAgent — AGENT-ALT-REC-001.

Suggests operational actions based on event type and severity.
Best practices loaded from prompts/templates.py (PRD §8.4.3).
"""

from typing import Any

from src.ai.agents.operational_recommendations.prompts.templates import (
    BEST_PRACTICES,
    DEFAULT_ACTIONS,
    NL_TEMPLATE,
)
from src.ai.agents.operational_recommendations.schemas import (
    OperationalRecommendationsOutputSchema,
)


class OperationalRecommendationsAgent:
    def __init__(self) -> None:
        self.name = "operational_recommendations"

    def execute(self, context: dict, **kwargs: Any) -> dict:
        alert_cls = context.get("alert_classification", {})
        event_type = alert_cls.get("event_type", "soil_moisture")
        severity = alert_cls.get("severity", "info")

        # Look up best practices
        by_event = BEST_PRACTICES.get(event_type, {})
        actions_raw = by_event.get(severity, by_event.get("warning", DEFAULT_ACTIONS))

        actions = [
            {"action": a, "priority": p, "deadline": d, "responsible": r}
            for a, p, d, r in actions_raw
        ]

        confidence = 0.7 if actions else 0.0
        top = actions[0]["action"] if actions else "N/A"

        raw = {
            "recommended_actions": actions,
            "confidence_score": round(confidence, 4),
            "data_completeness": 1.0,
            "natural_language_output": NL_TEMPLATE.format(
                count=len(actions), top=top, confidence=confidence,
            ),
        }
        return OperationalRecommendationsOutputSchema(**raw).model_dump(mode="json")
