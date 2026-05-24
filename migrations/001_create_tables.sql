-- Migration 001: Core tables for MSE Space Platform metadata registry
-- Slice 2: PostgreSQL (plain, no PostGIS)
-- 
-- Run: psql -U mse_user -d mse_platform -f migrations/001_create_tables.sql

BEGIN;

-- ============================================================
-- DATA SOURCES
-- ============================================================
CREATE TABLE IF NOT EXISTS data_sources (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(50)  NOT NULL UNIQUE,
    name            VARCHAR(255) NOT NULL,
    provider        VARCHAR(100) NOT NULL,
    source_type     VARCHAR(50)  NOT NULL DEFAULT 'satellite',
    access_method   VARCHAR(50)  NOT NULL DEFAULT 'earthaccess',
    requires_auth   BOOLEAN      NOT NULL DEFAULT TRUE,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    config          JSONB,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- DATASETS (products within a source)
-- ============================================================
CREATE TABLE IF NOT EXISTS datasets (
    id                  SERIAL PRIMARY KEY,
    source_id           INTEGER      NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    short_name          VARCHAR(100) NOT NULL,
    version             VARCHAR(20)  NOT NULL,
    format              VARCHAR(20)  NOT NULL DEFAULT 'HDF5',
    variables           TEXT[],
    spatial_resolution  VARCHAR(50),
    temporal_resolution VARCHAR(50),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (source_id, short_name, version)
);

-- ============================================================
-- INGESTION JOBS
-- ============================================================
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id              VARCHAR(50)  PRIMARY KEY,
    source_id       INTEGER      NOT NULL REFERENCES data_sources(id),
    dataset_id      INTEGER      REFERENCES datasets(id),
    region_id       VARCHAR(100),
    date_from       DATE         NOT NULL,
    date_to         DATE         NOT NULL,
    bbox            NUMERIC[]    NOT NULL,
    status          VARCHAR(30)  NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'completed', 'completed_with_warnings', 'failed')),
    ready_for_etl   BOOLEAN      NOT NULL DEFAULT FALSE,
    search_only     BOOLEAN      NOT NULL DEFAULT FALSE,
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ingestion_jobs_status ON ingestion_jobs(status);
CREATE INDEX idx_ingestion_jobs_created ON ingestion_jobs(created_at DESC);

-- ============================================================
-- RAW FILES
-- ============================================================
CREATE TABLE IF NOT EXISTS raw_files (
    id                  SERIAL PRIMARY KEY,
    ingestion_job_id    VARCHAR(50)   NOT NULL REFERENCES ingestion_jobs(id) ON DELETE CASCADE,
    source_id           INTEGER       NOT NULL REFERENCES data_sources(id),
    dataset_id          INTEGER       REFERENCES datasets(id),
    granule_id          VARCHAR(255),
    source_product_id   VARCHAR(100)  NOT NULL,
    remote_url          TEXT          NOT NULL,
    acquisition_date    DATE,
    file_path           TEXT          NOT NULL,
    file_name           VARCHAR(255)  NOT NULL,
    file_format         VARCHAR(20)   NOT NULL DEFAULT 'HDF5',
    size_bytes          BIGINT        NOT NULL DEFAULT 0,
    checksum_sha256     VARCHAR(64)   NOT NULL,
    metadata_json       JSONB,
    status              VARCHAR(30)   NOT NULL DEFAULT 'downloaded'
                            CHECK (status IN ('downloaded', 'already_downloaded', 'error')),
    error_message       TEXT,
    ready_for_etl       BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_raw_files_job_id ON raw_files(ingestion_job_id);
CREATE INDEX idx_raw_files_status ON raw_files(status);
CREATE INDEX idx_raw_files_ready ON raw_files(ready_for_etl) WHERE ready_for_etl = TRUE;

COMMIT;
