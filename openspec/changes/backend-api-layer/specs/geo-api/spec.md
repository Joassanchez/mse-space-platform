# Geo API — Specification

## Purpose

Expose geospatial layers as valid GeoJSON FeatureCollections for map rendering (Mapbox GL JS / Leaflet). Queries PostGIS via GeoAlchemy2 and shapely.

## Requirements

### Requirement: Region polygons

The system MUST expose GET /api/v1/geo/regions/ returning region polygons with basic metadata, filterable by active_only.

#### Scenario: Returns region polygons as GeoJSON

- GIVEN regions exist in the database with geometry
- WHEN GET /api/v1/geo/regions/
- THEN the system MUST return a GeoJSON FeatureCollection where each feature has geometry (Polygon) and properties (region_id, name, active)

### Requirement: Soil moisture layer

The system MUST expose GET /api/v1/geo/soil-moisture/ returning zones with sm_surface, sm_rootzone, and status properties, filterable by region_id and date.

#### Scenario: Returns soil moisture GeoJSON

- GIVEN soil moisture data exists for cordoba_pilot on 2024-01-15
- WHEN GET /api/v1/geo/soil-moisture/?region_id=cordoba_pilot&date=2024-01-15
- THEN the system MUST return a FeatureCollection with features containing sm_surface, sm_rootzone, status, and anomaly_pct properties
- AND metadata MUST include date, source, and confidence

### Requirement: Risk zones layer

The system MUST expose GET /api/v1/geo/risk-zones/ returning zones classified by risk level, filterable by region_id, date, and min_risk.

#### Scenario: Returns risk zones filtered by minimum risk

- GIVEN zones exist with risk_level "high", "medium", and "low"
- WHEN GET /api/v1/geo/risk-zones/?region_id=cordoba_pilot&min_risk=high
- THEN the system MUST return only features with risk_level "high"
- AND each feature MUST include risk_level and probability_score

### Requirement: Alert geometries

The system MUST expose GET /api/v1/geo/alerts/ returning point/polygon geometries for active alerts, filterable by region_id and severity.

#### Scenario: Returns alert geometries

- GIVEN active alerts with associated geometries exist for cordoba_pilot
- WHEN GET /api/v1/geo/alerts/?region_id=cordoba_pilot
- THEN the system MUST return a FeatureCollection with alert geometries and properties including alert_id, severity, and event_type

### Requirement: Flood extent layer

The system MUST expose GET /api/v1/geo/flood-extent/ returning detected flood extent when available, filterable by region_id and date.

#### Scenario: Returns flood extent when available

- GIVEN flood extent data exists for cordoba_pilot
- WHEN GET /api/v1/geo/flood-extent/?region_id=cordoba_pilot&date=2024-01-15
- THEN the system MUST return a FeatureCollection with flood extent geometry

#### Scenario: Returns empty when no flood data

- GIVEN no flood extent data exists for the requested region and date
- WHEN GET /api/v1/geo/flood-extent/?region_id=cordoba_pilot&date=2024-01-01
- THEN the system MUST return an empty FeatureCollection (features: [])
