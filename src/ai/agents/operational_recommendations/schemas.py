"""Pydantic schemas for OperationalRecommendationsAgent."""

from pydantic import BaseModel, Field


class RecommendedActionSchema(BaseModel):
    action: str = ""
    priority: str = "medium"
    deadline: str = ""
    responsible: str = ""


class OperationalRecommendationsOutputSchema(BaseModel):
    recommended_actions: list[dict] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0, le=1)
    data_completeness: float = Field(default=0.0, ge=0, le=1)
    natural_language_output: str = ""
