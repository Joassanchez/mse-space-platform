"""Pydantic schemas for the SoilMoistureAgent.

Re-exports and validates the SoilMoistureOutput dataclass from domain models
as a Pydantic BaseModel for runtime validation within the agent.
"""

from pydantic import BaseModel, Field

from src.ai.domain.models import SoilMoistureStatus


class SoilMoistureOutputSchema(BaseModel):
    """Pydantic validation model for SoilMoistureAgent output.

    Mirrors the dataclass in src/ai/domain/models.py but provides
    runtime validation before the agent returns its result.
    """

    surface_moisture: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Surface soil moisture (m3/m3, 0-5cm depth)",
    )
    rootzone_moisture: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Rootzone soil moisture (m3/m3, 0-100cm depth)",
    )
    sm_surface_status: SoilMoistureStatus = Field(
        default=SoilMoistureStatus.UNAVAILABLE,
        description="Surface moisture classification",
    )
    sm_rootzone_status: SoilMoistureStatus = Field(
        default=SoilMoistureStatus.UNAVAILABLE,
        description="Rootzone moisture classification",
    )
    trend_7d: str | None = Field(
        default=None,
        description="7-day trend direction (stable/increasing/decreasing)",
    )
    anomaly_pct: float | None = Field(
        default=None,
        description="Percent deviation from historical average",
    )
    confidence_score: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="Execution confidence (0-1)",
    )
    data_completeness: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="Fraction of expected indicators found (0-1)",
    )
    natural_language_output: str = Field(
        default="",
        description="Template-based natural language summary",
    )
