"""Pydantic schemas for the analysis module.

Defines the unified analysis request/response that aggregates data from
agroclimate, satellite, agronomy, and economy modules into a single endpoint.
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class AnalysisRequest(BaseModel):
    """Parameters for a unified analysis query."""

    lot_id: str
    crop: str  # "soy" or "corn"
    lat: float
    lon: float
    date: date


# ---------------------------------------------------------------------------
# Section models
# ---------------------------------------------------------------------------


class AgroclimateSection(BaseModel):
    """Weather (current) and POWER (historical) data for the query location."""

    current: dict[str, Any]  # weather response
    historical: dict[str, Any]  # aggregated POWER data (precip, solar, temp)


class SatelliteSection(BaseModel):
    """SMAP soil moisture and Sentinel optical scenes for the query area."""

    soil_moisture: list[dict[str, Any]]  # SMAP scenes
    optical: list[dict[str, Any]]  # Sentinel scenes


class AgronomySection(BaseModel):
    """Crop catalog info and estimated current BBCH stage."""

    crop_info: dict[str, Any]
    current_stage: dict[str, Any] | None


class EconomySection(BaseModel):
    """Latest grain price and weekly series for the queried crop."""

    latest_price: dict[str, Any] | None
    series: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Meta & Response
# ---------------------------------------------------------------------------


class AnalysisMeta(BaseModel):
    """Metadata about the analysis request — status, missing modules, caching."""

    status: str  # "complete" | "partial"
    missing_modules: list[str]
    cached_at: datetime | None


class AnalysisResponse(BaseModel):
    """Unified analysis response aggregating all four data modules."""

    query: AnalysisRequest
    agroclimate: AgroclimateSection | None
    satellite: SatelliteSection | None
    agronomy: AgronomySection | None
    economy: EconomySection | None
    meta: AnalysisMeta

    model_config = {"from_attributes": True}
