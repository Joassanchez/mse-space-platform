"""Geo API endpoints — PostGIS-powered GeoJSON layers."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db_session
from backend.schemas.geo import GeoJSONFeatureCollection
from backend.services.geo_service import (
    get_region_geometries,
    get_processed_layers,
    get_risk_zone_geometries,
    get_alert_geometries,
    get_flood_extent,
)
from backend.core.cache import cache_manager, CacheManager

router = APIRouter(tags=["geo"])


@router.get("/geo/regions/", response_model=GeoJSONFeatureCollection)
async def geo_regions(
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db_session),
):
    """Return region boundary polygons as GeoJSON FeatureCollection."""
    cache_key = CacheManager.make_key("geo:regions", "all" if active_only else "inactive")
    cached = await cache_manager.get(cache_key)
    if cached:
        return GeoJSONFeatureCollection(**cached)

    result = await get_region_geometries(db, active_only=active_only)
    await cache_manager.set(cache_key, result.model_dump(), ttl=CacheManager.get_ttl("geo"))
    return result


@router.get("/geo/layers/", response_model=GeoJSONFeatureCollection)
async def geo_layers(
    variable_name: str | None = Query(None, description="Filter by variable name (e.g. soil_moisture, flood)"),
    source_code: str | None = Query(None, description="Filter by source (e.g. SMAP)"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: AsyncSession = Depends(get_db_session),
):
    """Return processed geospatial layer footprints as GeoJSON.

    This is the closest match to the PRD's soil-moisture endpoint.
    Use variable_name=soil_moisture for SMAP moisture layers.
    """
    cache_key = CacheManager.make_key("geo:layers", variable_name or "all")
    cached = await cache_manager.get(cache_key)
    if cached:
        return GeoJSONFeatureCollection(**cached)

    result = await get_processed_layers(db, variable_name, source_code, date_from, date_to)
    await cache_manager.set(cache_key, result.model_dump(), ttl=CacheManager.get_ttl("geo"))
    return result


@router.get("/geo/risk-zones/", response_model=GeoJSONFeatureCollection)
async def geo_risk_zones(
    min_risk: str | None = Query(None, description="Minimum risk level: low, medium, high, critical"),
    region_id: int | None = Query(None, description="Filter by region ID"),
    db: AsyncSession = Depends(get_db_session),
):
    """Return risk assessment zones as GeoJSON, joined with region geometry."""
    result = await get_risk_zone_geometries(db, min_risk=min_risk, region_id=region_id)
    return result


@router.get("/geo/alerts/", response_model=GeoJSONFeatureCollection)
async def geo_alerts(
    region_id: int | None = Query(None),
    severity: str | None = Query(None, description="Filter by severity: info, warning, severe, critical"),
    db: AsyncSession = Depends(get_db_session),
):
    """Return active alert geometries as GeoJSON."""
    result = await get_alert_geometries(db, region_id=region_id, severity=severity)
    return result


@router.get("/geo/flood-extent/", response_model=GeoJSONFeatureCollection)
async def geo_flood_extent(
    region_id: int | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: AsyncSession = Depends(get_db_session),
):
    """Return flood extent layers as GeoJSON (variable_name LIKE '%flood%')."""
    result = await get_flood_extent(db, region_id=region_id, date_from=date_from, date_to=date_to)
    return result
