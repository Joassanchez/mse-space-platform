-- Seed 002: Geospatial storage reference data for MSE Space Platform
-- Slice 2: Seeds & Data Lineage
--
-- Run: psql -U mse_user -d mse_platform -f seeds/002_geospatial_storage.sql
--
-- Idempotent: uses ON CONFLICT DO NOTHING / conditional UPDATE.
-- Safe to run multiple times.

BEGIN;

-- ============================================================
-- UPDATE SMAP data_source with M3 config fields
-- ============================================================
-- Note: UPDATE uses WHERE, not ON CONFLICT (not an INSERT).
-- Only updates if the SMAP source exists.
UPDATE data_sources
SET config = config || '{
    "spatial_resolution_m": 9000,
    "temporal_resolution": "daily",
    "native_crs": "EPSG:6933",
    "description": "SMAP L4 Global 9km EASE-Grid Surface and Root Zone Soil Moisture"
}'::jsonb
WHERE code = 'SMAP';

-- ============================================================
-- INSERT pilot region: Chaco province, Argentina
-- ============================================================
INSERT INTO regions (
    name, geometry, region_type, country, province,
    bbox, metadata
) VALUES (
    'Chaco',
    ST_GeomFromText('MULTIPOLYGON(((-61.5 -26.0, -61.5 -24.5, -59.0 -24.5, -59.0 -26.0, -61.5 -26.0)))', 4326),
    'administrative',
    'Argentina',
    'Chaco',
    ARRAY[-61.5, -26.0, -59.0, -24.5],
    '{"description": "Pilot province for MVP testing"}'::jsonb
)
ON CONFLICT (name, country, province) DO NOTHING;

-- ============================================================
-- Verification queries (informational, not part of transaction)
-- ============================================================
-- SELECT COUNT(*) AS data_source_count FROM data_sources WHERE code = 'SMAP';
-- SELECT COUNT(*) AS region_count FROM regions WHERE name = 'Chaco';

COMMIT;
