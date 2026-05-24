-- Migration 002: Geospatial processing tables for MSE Space Platform
-- Slice 1: Foundation (geospatial_processing_jobs, processed_geospatial_layers)
--
-- Run: psql -U mse_user -d mse_platform -f migrations/002_create_tables.sql

BEGIN;

-- ============================================================
-- GEOSPATIAL PROCESSING JOBS
-- Tracks the state of each geospatial processing attempt.
-- ============================================================
CREATE TABLE IF NOT EXISTS geospatial_processing_jobs (
    id              VARCHAR(50) PRIMARY KEY,
    raw_file_id     INTEGER     NOT NULL REFERENCES raw_files(id),
    source_code     VARCHAR(20) NOT NULL,          -- e.g. 'SMAP'
    status          VARCHAR(30) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'completed', 'completed_with_warnings', 'failed', 'skipped')),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    error_message   TEXT,
    warnings        TEXT[],
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_geospatial_jobs_status ON geospatial_processing_jobs(status);
CREATE INDEX idx_geospatial_jobs_raw_file ON geospatial_processing_jobs(raw_file_id);

-- ============================================================
-- PROCESSED GEOSPATIAL LAYERS
-- Records each processed GeoTIFF layer with its spatial metadata.
-- ============================================================
CREATE TABLE IF NOT EXISTS processed_geospatial_layers (
    id                  SERIAL PRIMARY KEY,
    processing_job_id   VARCHAR(50) NOT NULL REFERENCES geospatial_processing_jobs(id),
    raw_file_id         INTEGER     NOT NULL REFERENCES raw_files(id),
    source_code         VARCHAR(20) NOT NULL,
    variable_name       VARCHAR(50) NOT NULL,
    display_name        VARCHAR(100),
    file_path           TEXT        NOT NULL,
    file_format         VARCHAR(10) NOT NULL DEFAULT 'GeoTIFF',
    crs                 VARCHAR(100),
    bbox                NUMERIC[],
    resolution_x        NUMERIC,
    resolution_y        NUMERIC,
    width               INTEGER,
    height              INTEGER,
    nodata_value        NUMERIC,
    min_value           NUMERIC,
    max_value           NUMERIC,
    mean_value          NUMERIC,
    valid_pixel_count   INTEGER,
    nodata_pixel_count  INTEGER,
    acquisition_date    DATE,
    processing_version  VARCHAR(20) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (raw_file_id, variable_name, processing_version),
    UNIQUE (file_path)
);

CREATE INDEX idx_processed_layers_raw_file ON processed_geospatial_layers(raw_file_id);
CREATE INDEX idx_processed_layers_variable ON processed_geospatial_layers(variable_name);

COMMIT;
