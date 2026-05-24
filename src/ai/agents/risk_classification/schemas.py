"""Pydantic schemas for the RiskClassificationAgent."""

from pydantic import BaseModel, Field

from src.ai.domain.models import RiskLevel


class RiskClassificationOutputSchema(BaseModel):
    """Pydantic validation model for RiskClassificationAgent output."""

    risk_level: RiskLevel = Field(default=RiskLevel.LOW)
    risk_score: float = Field(default=0.0, ge=0, le=1)
    contributing_factors: list[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0, le=1)
    data_completeness: float = Field(default=0.0, ge=0, le=1)
    natural_language_output: str = Field(default="")
