"""ExecutiveSummaryAgent — AGENT-ALT-EX-001.

Synthesises all alert components into a single executive report.
Template-based, deterministic — no LLM calls per MVP decision.
"""

from typing import Any

from src.ai.agents.executive_summary.prompts.templates import EXEC_TEMPLATE
from src.ai.agents.executive_summary.schemas import ExecutiveSummaryOutputSchema


class ExecutiveSummaryAgent:
    def __init__(self) -> None:
        self.name = "executive_summary"

    def execute(self, context: dict, **kwargs: Any) -> dict:
        alert_cls = context.get("alert_classification", {})
        comm = context.get("risk_communication", {})

        severity = alert_cls.get("severity", "info")
        event_type = alert_cls.get("event_type", "unknown")
        messages = comm.get("messages", {})

        # Build sections
        situation = f"Evento {event_type} detectado con nivel {severity}"
        n_audiences = len(messages)
        risk = f"Severidad {severity}. {n_audiences} audiencias notificadas."
        actions = "Consultar sección de recomendaciones operativas."

        summary = EXEC_TEMPLATE.format(
            severity=severity, event_type=event_type,
            situation=situation, risk=risk, actions=actions,
            confidence=0.8,
        )

        raw = {
            "executive_summary": summary,
            "situation": situation,
            "risk": risk,
            "actions": actions,
            "confidence_score": 0.8,
            "data_completeness": 1.0,
            "natural_language_output": summary,
        }
        return ExecutiveSummaryOutputSchema(**raw).model_dump(mode="json")
