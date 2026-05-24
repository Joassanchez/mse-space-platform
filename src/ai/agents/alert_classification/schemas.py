"""Alert Classification Agent — AGENT-ALT-CL-001."""

from pydantic import BaseModel, Field

from src.ai.domain.models import AlertEventType, AlertSeverity


class AlertClassificationOutputSchema(BaseModel):
    severity: AlertSeverity = AlertSeverity.INFO
    event_type: AlertEventType = AlertEventType.SOIL_MOISTURE
    affected_zones: list[dict] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0, le=1)
    data_completeness: float = Field(default=0.0, ge=0, le=1)
    natural_language_output: str = ""
