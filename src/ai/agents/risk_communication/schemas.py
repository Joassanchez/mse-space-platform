"""Pydantic schemas for RiskCommunicationAgent."""

from pydantic import BaseModel, Field


class RiskCommunicationOutputSchema(BaseModel):
    messages: dict[str, str] = Field(default_factory=dict)
    confidence_score: float = Field(default=0.0, ge=0, le=1)
    data_completeness: float = Field(default=0.0, ge=0, le=1)
    natural_language_output: str = ""
