"""Pydantic schemas for the WeatherAgent.

Re-exports and validates the WeatherOutput dataclass from domain models
as a Pydantic BaseModel for runtime validation within the agent.
"""

from pydantic import BaseModel, Field

from src.ai.domain.models import WeatherCondition


class WeatherOutputSchema(BaseModel):
    """Pydantic validation model for WeatherAgent output.

    Mirrors the dataclass in src/ai/domain/models.py but provides
    runtime validation before the agent returns its result.
    Includes all PRD §5.4.4 fields: rainfall, temperature, humidity, wind, forecast.
    """

    rainfall_30d_mm: float | None = Field(
        default=None,
        description="Accumulated rainfall over last 30 days (mm)",
    )
    rainfall_7d_mm: float | None = Field(
        default=None,
        description="Accumulated rainfall over last 7 days (mm)",
    )
    rainfall_anomaly_pct: float | None = Field(
        default=None,
        description="Percent deviation from historical average",
    )
    condition: WeatherCondition = Field(
        default=WeatherCondition.AVERAGE,
        description="Rainfall condition classification",
    )
    temperature_anomaly: float | None = Field(
        default=None,
        description="Temperature deviation from average (°C)",
    )
    temp_avg: float | None = Field(
        default=None,
        description="Average temperature (°C)",
    )
    humidity: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Relative humidity (%)",
    )
    wind_speed: float | None = Field(
        default=None,
        ge=0,
        description="Wind speed (m/s)",
    )
    forecast_relevance: float | None = Field(
        default=None,
        description="Whether short-term forecast affects analysis (0-1)",
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
