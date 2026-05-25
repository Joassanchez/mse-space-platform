"""Pydantic schemas for GeoJSON responses."""

from pydantic import BaseModel


class GeoJSONFeature(BaseModel):
    """A single GeoJSON Feature."""

    type: str = "Feature"
    geometry: dict
    properties: dict


class GeoJSONFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection with optional metadata."""

    type: str = "FeatureCollection"
    features: list[GeoJSONFeature]
    metadata: dict | None = None
