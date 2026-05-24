-- Seed: Socioeconomic demo indicators (Módulo 6)
-- DEMO DATA — not actual INDEC data. Market as reference/test.
--
-- Load: psql -U mse_user -d mse_platform -f seeds/003_socioeconomic_demo.sql
--
-- These indicators are consumed by ContextEngine for EconomicOrchestrator
-- contract validation. Replace with real data when INDEC connector is active.

BEGIN;

-- ============================================================
-- SEED CHECK: only insert if regions exist
-- ============================================================
DO $$
DECLARE
    demo_region INTEGER;
BEGIN
    -- Use first active region as demo target
    SELECT id INTO demo_region FROM regions WHERE is_active = true ORDER BY id LIMIT 1;

    IF demo_region IS NULL THEN
        RAISE NOTICE 'No active regions found — skipping socioeconomic seed.';
        RETURN;
    END IF;

    -- Crop yield indicator (demo)
    INSERT INTO indicators (region_id, indicator_code, indicator_name, value, unit, classification, confidence, metadata)
    VALUES (demo_region, 'ECO_CROP_YIELD', 'Crop Yield (demo)', 4500.0, 'kg/ha', 'reference', 0.5,
            '{"source": "indec", "is_demo": true, "note": "DEMO DATA — not actual INDEC data", "crop": "soybean", "campaign": "2023/2024"}')
    ON CONFLICT DO NOTHING;

    -- Affected area (demo)
    INSERT INTO indicators (region_id, indicator_code, indicator_name, value, unit, classification, confidence, metadata)
    VALUES (demo_region, 'ECO_AFFECTED_AREA', 'Affected Agricultural Area (demo)', 12500.0, 'ha', 'reference', 0.5,
            '{"source": "indec", "is_demo": true, "note": "DEMO DATA"}')
    ON CONFLICT DO NOTHING;

    -- Estimated loss USD (demo)
    INSERT INTO indicators (region_id, indicator_code, indicator_name, value, unit, classification, confidence, metadata)
    VALUES (demo_region, 'ECO_ESTIMATED_LOSS', 'Estimated Economic Loss (demo)', 2500000.0, 'USD', 'reference', 0.5,
            '{"source": "indec", "is_demo": true, "note": "DEMO DATA"}')
    ON CONFLICT DO NOTHING;

    -- Commodity price (demo)
    INSERT INTO indicators (region_id, indicator_code, indicator_name, value, unit, classification, confidence, metadata)
    VALUES (demo_region, 'ECO_COMMODITY_PRICE', 'Soybean Price (demo)', 320.0, 'USD/tn', 'reference', 0.5,
            '{"source": "indec", "is_demo": true, "note": "DEMO DATA"}')
    ON CONFLICT DO NOTHING;

    -- Population density (demo)
    INSERT INTO indicators (region_id, indicator_code, indicator_name, value, unit, classification, confidence, metadata)
    VALUES (demo_region, 'ECO_POP_DENSITY', 'Population Density (demo)', 25.0, 'hab/km2', 'reference', 0.5,
            '{"source": "indec", "is_demo": true, "note": "DEMO DATA"}')
    ON CONFLICT DO NOTHING;

    RAISE NOTICE 'Socioeconomic demo indicators inserted for region %', demo_region;
END $$;

COMMIT;
