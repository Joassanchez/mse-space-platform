"""Domain models for weather snapshots."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class WeatherSnapshot:
    """A weather observation snapshot for a region at a point in time.

    Stores normalised meteorological data ingested from OpenWeather or
    similar providers. All values are stored as-is from the provider;
    unit conversion happens at the connector level.
    """

    region_id: int
    observed_at: str  # ISO timestamp
    temp_celsius: Optional[float] = None
    humidity_pct: Optional[float] = None
    wind_speed_ms: Optional[float] = None
    rainfall_mm: Optional[float] = None
    pressure_hpa: Optional[float] = None
    weather_condition: str = ""  # e.g. "clear", "rain", "clouds"
    source: str = "openweather"
    metadata: dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    created_at: Optional[str] = None
