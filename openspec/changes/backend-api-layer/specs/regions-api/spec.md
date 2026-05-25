# Regions API — Specification

## Purpose

Expose configured regions with bounding boxes, metadata, active data sources, and latest analysis reference. Simple read-only endpoints.

## Requirements

### Requirement: List active regions

The system MUST expose GET /api/v1/regions/ returning all active regions with bounding box and basic metadata.

#### Scenario: Returns regions list

- GIVEN regions exist in the database
- WHEN GET /api/v1/regions/
- THEN the system MUST return a list of regions each with region_id, name, bbox, active, and created_at

### Requirement: Single region detail

The system MUST expose GET /api/v1/regions/{region_id} returning full region detail including bbox, area_sqkm, active data sources, and latest analysis reference.

#### Scenario: Returns region detail

- GIVEN region "cordoba_pilot" exists with metadata
- WHEN GET /api/v1/regions/cordoba_pilot
- THEN the system MUST return region_id, name, bbox, area_sqkm, active_data_sources, and latest_analysis_id

#### Scenario: Returns 404 for unknown region

- GIVEN region "unknown" does not exist
- WHEN GET /api/v1/regions/unknown
- THEN the system MUST return 404
