"""Geo service — PostGIS queries returning GeoJSON FeatureCollections.

Uses raw SQL with ST_AsGeoJSON to avoid GeoAlchemy2 dependency.
All functions return dicts ready for GeoJSON serialization.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.schemas.geo import GeoJSONFeatureCollection, GeoJSONFeature


async def _raw_geojson(
    db: AsyncSession,
    sql: str,
    params: dict | None = None,
    metadata: dict | None = None,
) -> GeoJSONFeatureCollection:
    """Execute a raw SQL query that returns GeoJSON features, wrap in FeatureCollection."""
    result = await db.execute(text(sql), params or {})
    rows = result.fetchall()

    features = []
    for row in rows:
        geom = row[0]  # expected as a dict from ::jsonb cast
        props = row[1] if len(row) > 1 else {}
        if isinstance(geom, str):
            import json
            geom = json.loads(geom)
        features.append(
            GeoJSONFeature(
                geometry=geom if isinstance(geom, dict) else {},
                properties=props if isinstance(props, dict) else {},
            )
        )

    return GeoJSONFeatureCollection(features=features, metadata=metadata)


async def get_region_geometries(
    db: AsyncSession,
    active_only: bool = True,
) -> GeoJSONFeatureCollection:
    """Return region polygons as GeoJSON FeatureCollection."""
    sql = """
        SELECT ST_AsGeoJSON(r.geometry)::jsonb AS geom,
               jsonb_build_object(
                   'region_id', r.id,
                   'name', r.name,
                   'region_type', r.region_type,
                   'country', r.country,
                   'province', r.province,
                   'is_active', r.is_active
               ) AS props
        FROM regions r
        WHERE (:active_only = false OR r.is_active = true)
        ORDER BY r.name
    """
    return await _raw_geojson(
        db, sql, {"active_only": active_only},
        metadata={"type": "region_boundaries"},
    )


async def get_processed_layers(
    db: AsyncSession,
    variable_name: str | None = None,
    source_code: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> GeoJSONFeatureCollection:
    """Return processed geospatial layer footprints as GeoJSON.

    Closest match to the PRD's soil-moisture, flood-extent endpoints.
    """
    conditions = ["1=1"]
    params: dict = {}

    if variable_name:
        conditions.append("pl.variable_name = :variable_name")
        params["variable_name"] = variable_name
    if source_code:
        conditions.append("pl.source_code = :source_code")
        params["source_code"] = source_code
    if date_from:
        conditions.append("pl.acquisition_date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("pl.acquisition_date <= :date_to")
        params["date_to"] = date_to

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT COALESCE(ST_AsGeoJSON(pl.footprint_geometry)::jsonb, '{{}}'::jsonb) AS geom,
               jsonb_build_object(
                   'layer_id', pl.id,
                   'variable_name', pl.variable_name,
                   'display_name', pl.display_name,
                   'source_code', pl.source_code,
                   'acquisition_date', pl.acquisition_date::text,
                   'file_path', pl.file_path,
                   'crs', pl.crs
               ) AS props
        FROM processed_geospatial_layers pl
        WHERE {where_clause}
          AND pl.footprint_geometry IS NOT NULL
        ORDER BY pl.acquisition_date DESC NULLS LAST
        LIMIT 100
    """
    return await _raw_geojson(
        db, sql, params,
        metadata={"type": "processed_layers", "filter": variable_name or "all"},
    )


async def get_risk_zone_geometries(
    db: AsyncSession,
    min_risk: str | None = None,
    region_id: int | None = None,
) -> GeoJSONFeatureCollection:
    """Return risk assessment zones as GeoJSON, joined with region geometry."""
    conditions = ["1=1"]
    params: dict = {}

    if min_risk:
        risk_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        min_val = risk_order.get(min_risk, 1)
        params["min_val"] = min_val
        conditions.append(
            "CASE WHEN ra.risk_level = 'low' THEN 1"
            " WHEN 'medium' THEN 2 WHEN 'high' THEN 3 WHEN 'critical' THEN 4 END >= :min_val"
        )
    if region_id:
        conditions.append("ra.region_id = :region_id")
        params["region_id"] = region_id

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT ST_AsGeoJSON(r.geometry)::jsonb AS geom,
               jsonb_build_object(
                   'risk_id', ra.id,
                   'risk_type', ra.risk_type,
                   'risk_level', ra.risk_level,
                   'risk_score', ra.risk_score,
                   'confidence', ra.confidence,
                   'explanation', ra.explanation,
                   'region_id', ra.region_id,
                   'region_name', r.name,
                   'created_at', ra.created_at::text
               ) AS props
        FROM risk_assessments ra
        JOIN regions r ON r.id = ra.region_id
        WHERE {where_clause}
        ORDER BY ra.risk_level DESC, ra.created_at DESC
        LIMIT 100
    """
    return await _raw_geojson(
        db, sql, params,
        metadata={"type": "risk_zones"},
    )


async def get_alert_geometries(
    db: AsyncSession,
    region_id: int | None = None,
    severity: str | None = None,
) -> GeoJSONFeatureCollection:
    """Return active alert geometries as GeoJSON, joined with region geometry."""
    conditions = ["a.status = 'active'"]
    params: dict = {}

    if region_id:
        conditions.append("a.region_id = :region_id")
        params["region_id"] = region_id
    if severity:
        conditions.append("a.severity = :severity")
        params["severity"] = severity

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT ST_AsGeoJSON(r.geometry)::jsonb AS geom,
               jsonb_build_object(
                   'alert_id', a.id,
                   'alert_type', a.alert_type,
                   'severity', a.severity,
                   'title', a.title,
                   'status', a.status,
                   'region_id', a.region_id,
                   'region_name', r.name,
                   'issued_at', a.issued_at::text
               ) AS props
        FROM alerts a
        JOIN regions r ON r.id = a.region_id
        WHERE {where_clause}
        ORDER BY a.severity DESC, a.issued_at DESC
        LIMIT 100
    """
    return await _raw_geojson(
        db, sql, params,
        metadata={"type": "active_alerts"},
    )


async def get_flood_extent(
    db: AsyncSession,
    region_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> GeoJSONFeatureCollection:
    """Return flood extent layers as GeoJSON.

    Filters processed_geospatial_layers by variable_name LIKE '%flood%'.
    """
    conditions = ["pl.variable_name ILIKE '%flood%'"]
    params: dict = {}

    if region_id:
        conditions.append("rf.region_id = :region_id")
        params["region_id"] = region_id
    if date_from:
        conditions.append("pl.acquisition_date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("pl.acquisition_date <= :date_to")
        params["date_to"] = date_to

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT COALESCE(ST_AsGeoJSON(pl.footprint_geometry)::jsonb, '{{}}'::jsonb) AS geom,
               jsonb_build_object(
                   'layer_id', pl.id,
                   'variable_name', pl.variable_name,
                   'display_name', pl.display_name,
                   'acquisition_date', pl.acquisition_date::text,
                   'file_path', pl.file_path
               ) AS props
        FROM processed_geospatial_layers pl
        LEFT JOIN raw_files rf ON rf.id = pl.raw_file_id
        WHERE {where_clause}
          AND pl.footprint_geometry IS NOT NULL
        ORDER BY pl.acquisition_date DESC NULLS LAST
        LIMIT 100
    """
    return await _raw_geojson(
        db, sql, params,
        metadata={"type": "flood_extent"},
    )
