"""Pydantic schemas for the DroughtAgent.

Re-exports and validates the DroughtOutput dataclass from domain models
as a Pydantic BaseModel for runtime validation within the agent.
"""

from pydantic import BaseModel, Field

from src.ai.domain.models import DroughtCategory, DroughtSignal, SpiStatus


class DroughtOutputSchema(BaseModel):
    """Pydantic validation model for DroughtAgent output.

    Mirrors the dataclass in src/ai/domain/models.py but provides
    runtime validation before the agent returns its result.
    """

    spi_30d: float | None = Field(
        default=None,
        description="Standardized Precipitation Index at 30-day scale",
    )
    spi_90d: float | None = Field(
        default=None,
        description="Standardized Precipitation Index at 90-day scale",
    )
    spi_status: SpiStatus = Field(
        default=SpiStatus.NORMAL,
        description="SPI-based moisture status (normal/moderate_drought/severe_drought/extreme_drought)",
    )
    drought_category: DroughtCategory = Field(
        default=DroughtCategory.NONE,
        description="Drought severity category from SPI thresholds",
    )
    drought_signal: DroughtSignal = Field(
        default=DroughtSignal.NONE,
        description="Actionable drought signal for orchestrator",
    )
    duration_weeks: int | None = Field(
        default=None,
        description="Estimated drought duration in weeks",
    )
    spatial_extent_pct: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Percent of area affected by drought conditions",
    )
    trend: str = Field(
        default="stable",
        description="Drought trend direction (improving/stable/worsening)",
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
