-- Migration 007: Weather snapshots table
-- Módulo 6: Data Connectors & Context Enrichment
--
-- Stores normalised meteorological observations ingested from
-- OpenWeather or similar providers. Consumed by ContextEngine
-- for Risk and Alerts orchestrators.
--
-- Idempotent: uses IF NOT EXISTS everywhere.

BEGIN;

CREATE TABLE IF NOT EXISTS weather_snapshots (
    id                SERIAL PRIMARY KEY,
    region_id         INTEGER       NOT NULL REFERENCES regions(id),
    observed_at       TIMESTAMPTZ   NOT NULL,
    temp_celsius      NUMERIC(5,2),
    humidity_pct      NUMERIC(5,2),
    wind_speed_ms     NUMERIC(5,2),
    rainfall_mm       NUMERIC(7,2),
    pressure_hpa      NUMERIC(7,2),
    weather_condition VARCHAR(50)   DEFAULT '',
    source            VARCHAR(50)   NOT NULL DEFAULT 'openweather',
    metadata          JSONB         DEFAULT '{}',
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_weather_snapshots_region
    ON weather_snapshots (region_id);
CREATE INDEX IF NOT EXISTS idx_weather_snapshots_observed
    ON weather_snapshots (observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_weather_snapshots_region_observed
    ON weather_snapshots (region_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_weather_snapshots_source
    ON weather_snapshots (source);

COMMIT;
