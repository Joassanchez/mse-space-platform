"""Pydantic schemas for ExecutiveSummaryAgent."""

from pydantic import BaseModel, Field


class ExecutiveSummaryOutputSchema(BaseModel):
    executive_summary: str = ""
    situation: str = ""
    risk: str = ""
    actions: str = ""
    confidence_score: float = Field(default=0.0, ge=0, le=1)
    data_completeness: float = Field(default=0.0, ge=0, le=1)
    natural_language_output: str = ""
