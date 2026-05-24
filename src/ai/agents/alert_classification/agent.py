"""AlertClassificationAgent — AGENT-ALT-CL-001.

Classifies alert severity and event type from hydric + risk context.
"""

from typing import Any

from src.ai.agents.alert_classification.prompts.templates import NL_TEMPLATE
from src.ai.agents.alert_classification.schemas import AlertClassificationOutputSchema
from src.ai.domain.models import AlertEventType, AlertSeverity


class AlertClassificationAgent:
    def __init__(self) -> None:
        self.name = "alert_classification"

    def execute(self, context: dict, **kwargs: Any) -> dict:
        hydric = context.get("hydric_output", {})
        risk = context.get("risk_output", {})
        regions = context.get("regions", [])

        severity = self._classify_severity(hydric, risk)
        event_type = self._classify_event_type(hydric, risk)
        zones = [{"id": r.get("id"), "name": r.get("name")} for r in regions]

        confidence = 0.7 if hydric or risk else 0.0
        data_completeness = 0.8 if zones else 0.0

        raw = {
            "severity": severity.value,
            "event_type": event_type.value,
            "affected_zones": zones,
            "confidence_score": round(confidence, 4),
            "data_completeness": round(data_completeness, 4),
            "natural_language_output": NL_TEMPLATE.format(
                severity=severity.value, event_type=event_type.value,
                zones=len(zones), confidence=confidence,
            ),
        }
        return AlertClassificationOutputSchema(**raw).model_dump(mode="json")

    def _classify_severity(self, hydric: dict, risk: dict) -> AlertSeverity:
        hc = hydric.get("overall_hydric_condition", "")
        rl = risk.get("risk_level", "")
        if hc == "critical" or rl == "critical":
            return AlertSeverity.CRITICAL
        if hc == "stressed" or rl == "high":
            return AlertSeverity.ALERT
        if hc == "moderate" or rl == "moderate":
            return AlertSeverity.WARNING
        return AlertSeverity.INFO

    def _classify_event_type(self, hydric: dict, risk: dict) -> AlertEventType:
        hc = hydric.get("overall_hydric_condition", "")
        ds = hydric.get("drought_signal", "")
        if ds in ("severe", "moderate"):
            return AlertEventType.DROUGHT
        if hc in ("critical", "stressed"):
            return AlertEventType.RISK_ESCALATION
        sm = hydric.get("soil_moisture_status", "")
        if sm in ("dry", "critical_dry", "wet", "critical_wet"):
            return AlertEventType.SOIL_MOISTURE
        return AlertEventType.WEATHER_ANOMALY
