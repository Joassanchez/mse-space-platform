"""RiskCommunicationAgent — AGENT-ALT-COM-001.

Generates differentiated messages per audience type using versioned templates.
Audience profiles are stored in prompts/ per PRD §4.2 plugin structure.
"""

from typing import Any

from src.ai.agents.risk_communication.prompts.templates import NL_TEMPLATE
from src.ai.agents.risk_communication.schemas import RiskCommunicationOutputSchema
from src.ai.domain.models import AlertEventType, AlertSeverity, TargetAudience


# Versioned audience message templates (PRD §8.4.2)
_AUDIENCE_TEMPLATES = {
    TargetAudience.MUNICIPALITIES: {
        "title": "Alerta {severity}: {event_type} detectado en {zone}",
        "body": (
            "Se ha detectado {event_type} con nivel {severity} en {zone}. "
            "Recomendamos activar protocolos de emergencia y monitorear "
            "las zonas afectadas. {actionable}"
        ),
    },
    TargetAudience.PRODUCERS: {
        "title": "Alerta {severity}: {event_type} — {zone}",
        "body": (
            "Condiciones {event_type} detectadas en {zone} (severidad: {severity}). "
            "Se recomienda evaluar cultivos y preparar medidas de mitigación. "
            "{actionable}"
        ),
    },
    TargetAudience.COOPERATIVES: {
        "title": "Reporte {severity}: {event_type} en {zone}",
        "body": (
            "Evento de {event_type} registrado en {zone}. "
            "Nivel de alerta: {severity}. "
            "Coordinar con productores de la zona para evaluación conjunta. "
            "{actionable}"
        ),
    },
    TargetAudience.INSURERS: {
        "title": "Notificación {severity}: {event_type} — {zone}",
        "body": (
            "Evento asegurable potencial detectado: {event_type} en {zone}. "
            "Severidad: {severity}. "
            "Se recomienda revisar pólizas activas en la zona afectada. "
            "{actionable}"
        ),
    },
}


class RiskCommunicationAgent:
    def __init__(self) -> None:
        self.name = "risk_communication"

    def execute(self, context: dict, **kwargs: Any) -> dict:
        hydric = context.get("hydric_output", {})
        alert_cls = context.get("alert_classification", {})

        severity = alert_cls.get("severity", "info")
        event_type = alert_cls.get("event_type", "soil_moisture")
        zone_names = [r.get("name", "unknown") for r in context.get("regions", [])]
        zone_str = ", ".join(zone_names) if zone_names else "la región"

        # Actionable recommendation per severity
        actionable_map = {
            "critical": "Activar respuesta inmediata.",
            "alert": "Preparar equipos de respuesta.",
            "warning": "Monitorear evolución.",
            "info": "Sin acción requerida por ahora.",
        }
        actionable = actionable_map.get(severity, "")

        messages = {}
        for audience in TargetAudience:
            tmpl = _AUDIENCE_TEMPLATES[audience]
            body = tmpl["body"].format(
                severity=severity, event_type=event_type,
                zone=zone_str, actionable=actionable,
            )
            messages[audience.value] = body

        aud_list = list(messages.keys())
        confidence = 0.8 if zone_names else 0.3

        raw = {
            "messages": messages,
            "confidence_score": round(confidence, 4),
            "data_completeness": 1.0,
            "natural_language_output": NL_TEMPLATE.format(
                audiences=", ".join(aud_list), confidence=confidence,
            ),
        }
        return RiskCommunicationOutputSchema(**raw).model_dump(mode="json")
