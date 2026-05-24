# Geospatial Storage Specification

## Purpose
Defines the storage architecture for vector data, administrative regions, and analytical outcomes (indicators, risks, alerts, economic impacts) utilizing PostGIS capabilities.

## Requirements

### Requirement: PostGIS Enablement
The system MUST use a PostGIS-enabled PostgreSQL 15 image (e.g., `postgis/postgis:15-3.4-alpine`). The extension MUST be enabled via a SQL migration (`CREATE EXTENSION IF NOT EXISTS postgis`). Changing the Docker image MUST document rollback procedures and volume compatibility risks, as it is not an automatically safe operation.

#### Scenario: Enable PostGIS on existing DB
- GIVEN an existing PostgreSQL 15 instance without PostGIS
- WHEN the initial geospatial-storage migration is applied
- THEN the `postgis` extension is created successfully
- AND existing tables remain unaffected

### Requirement: Regions Storage
The system MUST persist regions with EPSG:4326 MultiPolygon geometries, creating a GIST index on the `geometry` column.

#### Scenario: Store a new region
- GIVEN a valid GeoJSON polygon for a province
- WHEN the region is saved to the database
- THEN it is stored in the `regions` table with EPSG:4326 CRS
- AND area_km2 is calculated if not explicitly provided

### Requirement: Analytical Entities Storage
The system MUST store `indicators`, `risk_assessments`, `alerts`, and `economic_impacts` with foreign keys to `regions` and appropriate JSONB metadata.

#### Scenario: Save risk assessment
- GIVEN a calculated drought risk for a region
- WHEN persistence is invoked
- THEN a record is created in `risk_assessments` linked to `regions.id`
- AND the risk level and confidence are correctly persisted