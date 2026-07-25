"""Pydantic schemas for the agronomy module.

Agronomy data is loaded from YAML fixtures at startup. No SQLAlchemy models
are needed for the MVP — the catalog is purely in-memory.
"""

from pydantic import BaseModel


class CropInfo(BaseModel):
    """Public API representation of a supported crop."""

    id: str
    name: str
    scientific_name: str


class GrowthStage(BaseModel):
    """A single BBCH phenological growth stage."""

    bbch_code: str
    name: str
    description: str
    kc: float
    water_stress_sensitivity: str
    temp_sensitivity: str


class CropListResponse(BaseModel):
    """Response wrapper for the crop listing endpoint."""

    crops: list[CropInfo]


class GrowthStagesResponse(BaseModel):
    """Response wrapper for the growth stages endpoint."""

    crop_id: str
    stages: list[GrowthStage]
