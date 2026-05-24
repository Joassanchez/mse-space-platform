"""Pydantic schemas for the PredictiveScenariosAgent."""

from pydantic import BaseModel, Field


class ScenarioSchema(BaseModel):
    """A single scenario projection."""
    horizon_days: int = 7
    scenario_type: str = "probable"
    risk_level: str = "low"
    probability_score: float = Field(default=0.0, ge=0, le=1)
    description: str = ""


class PredictiveScenariosOutputSchema(BaseModel):
    """Pydantic validation model for PredictiveScenariosAgent output."""

    scenarios: list[ScenarioSchema] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0, le=1)
    data_completeness: float = Field(default=0.0, ge=0, le=1)
    natural_language_output: str = Field(default="")
