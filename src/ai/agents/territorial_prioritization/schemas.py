"""Pydantic schemas for the TerritorialPrioritizationAgent."""

from pydantic import BaseModel, Field


class PrioritizationZoneSchema(BaseModel):
    """A prioritized zone with score."""
    zone_id: str = ""
    zone_name: str = ""
    priority_score: float = Field(default=0.0, ge=0, le=1)
    risk_level: str = "low"
    reason: str = ""


class TerritorialPrioritizationOutputSchema(BaseModel):
    """Pydantic validation model for TerritorialPrioritizationAgent output."""

    priority_zones: list[PrioritizationZoneSchema] = Field(default_factory=list)
    ranking: list[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0, le=1)
    data_completeness: float = Field(default=0.0, ge=0, le=1)
    natural_language_output: str = Field(default="")
