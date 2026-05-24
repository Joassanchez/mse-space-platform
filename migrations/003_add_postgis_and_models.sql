-- Migration 003: PostGIS extension + geospatial storage tables for MSE Space Platform
-- Slice 1: Foundation (PostGIS enablement, new tables, non-destructive alters)
--
-- Run: psql -U mse_user -d mse_platform -f migrations/003_add_postgis_and_models.sql
--
-- Non-destructive: preserves existing columns (bbox NUMERIC[]), uses IF NOT EXISTS / IF NOT EXISTS everywhere.
-- Safe to run multiple times (idempotent).

BEGIN;

-- ============================================================
-- POSTGIS EXTENSION
-- ============================================================
CREATE EXTENSION IF NOT EXISTS postgis;

-- ============================================================
-- REGIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS regions (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    geometry        GEOMETRY(MultiPolygon, 4326) NOT NULL,
    region_type     VARCHAR(50)  NOT NULL DEFAULT 'administrative',
    country         VARCHAR(100),
    province        VARCHAR(100),
    bbox            NUMERIC[],
    area_km2        NUMERIC,
    metadata        JSONB        DEFAULT '{}',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_regions_geometry ON regions USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_regions_type ON regions (region_type);
CREATE INDEX IF NOT EXISTS idx_regions_active ON regions (is_active) WHERE is_active = TRUE;
ALTER TABLE regions ADD CONSTRAINT IF NOT EXISTS uq_regions_name_country_province UNIQUE (name, country, province);

-- ============================================================
-- INDICATORS
-- ============================================================
CREATE TABLE IF NOT EXISTS indicators (
    id                  SERIAL PRIMARY KEY,
    region_id           INTEGER      NOT NULL REFERENCES regions(id),
    processed_layer_id  INTEGER      REFERENCES processed_geospatial_layers(id),
    indicator_code      VARCHAR(50)  NOT NULL,
    indicator_name      VARCHAR(255),
    indicator_type      VARCHAR(50),
    value               NUMERIC,
    unit                VARCHAR(50),
    classification      VARCHAR(50),
    confidence          NUMERIC,
    calculation_method  VARCHAR(100),
    temporal_start      DATE,
    temporal_end        DATE,
    metadata            JSONB        DEFAULT '{}',
    created_at          TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_indicators_region ON indicators (region_id);
CREATE INDEX IF NOT EXISTS idx_indicators_code ON indicators (indicator_code);
CREATE INDEX IF NOT EXISTS idx_indicators_layer ON indicators (processed_layer_id);

-- ============================================================
-- RISK ASSESSMENTS
-- ============================================================
CREATE TABLE IF NOT EXISTS risk_assessments (
    id              SERIAL PRIMARY KEY,
    region_id       INTEGER      NOT NULL REFERENCES regions(id),
    indicator_id    INTEGER      REFERENCES indicators(id),
    risk_type       VARCHAR(50)  NOT NULL CHECK (risk_type IN ('drought', 'flood', 'hydric_stress', 'agroenvironmental')),
    risk_level      VARCHAR(20)  NOT NULL CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    risk_score      NUMERIC,
    confidence      NUMERIC,
    method          VARCHAR(100),
    explanation     TEXT,
    temporal_start  DATE,
    temporal_end    DATE,
    metadata        JSONB        DEFAULT '{}',
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_assessments_region ON risk_assessments (region_id);
CREATE INDEX IF NOT EXISTS idx_risk_assessments_type ON risk_assessments (risk_type);
CREATE INDEX IF NOT EXISTS idx_risk_assessments_level ON risk_assessments (risk_level);
CREATE INDEX IF NOT EXISTS idx_risk_assessments_indicator ON risk_assessments (indicator_id);

-- ============================================================
-- ALERTS
-- ============================================================
CREATE TABLE IF NOT EXISTS alerts (
    id                  SERIAL PRIMARY KEY,
    region_id           INTEGER      NOT NULL REFERENCES regions(id),
    risk_assessment_id  INTEGER      REFERENCES risk_assessments(id),
    alert_type          VARCHAR(50)  NOT NULL,
    severity            VARCHAR(20)  NOT NULL CHECK (severity IN ('info', 'warning', 'severe', 'critical')),
    title               VARCHAR(255) NOT NULL,
    message             TEXT,
    status              VARCHAR(20)  NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'acknowledged', 'resolved', 'dismissed')),
    issued_at           TIMESTAMPTZ  DEFAULT NOW(),
    resolved_at         TIMESTAMPTZ,
    metadata            JSONB        DEFAULT '{}',
    created_at          TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_region ON alerts (region_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts (status);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts (severity);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts (status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_alerts_risk ON alerts (risk_assessment_id);

-- ============================================================
-- ECONOMIC IMPACTS
-- ============================================================
CREATE TABLE IF NOT EXISTS economic_impacts (
    id                  SERIAL PRIMARY KEY,
    region_id           INTEGER      NOT NULL REFERENCES regions(id),
    risk_assessment_id  INTEGER      REFERENCES risk_assessments(id),
    impact_type         VARCHAR(50)  NOT NULL,
    estimated_loss_usd  NUMERIC,
    affected_area_ha    NUMERIC,
    crop_type           VARCHAR(100),
    yield_loss_pct      NUMERIC,
    method              VARCHAR(100),
    assumptions         TEXT,
    confidence          NUMERIC,
    metadata            JSONB        DEFAULT '{}',
    created_at          TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_economic_impacts_region ON economic_impacts (region_id);
CREATE INDEX IF NOT EXISTS idx_economic_impacts_risk ON economic_impacts (risk_assessment_id);
CREATE INDEX IF NOT EXISTS idx_economic_impacts_type ON economic_impacts (impact_type);

-- ============================================================
-- AUDIT LOGS
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id          SERIAL PRIMARY KEY,
    entity_type VARCHAR(50)  NOT NULL,
    entity_id   VARCHAR(100),
    action      VARCHAR(50)  NOT NULL,
    actor_type  VARCHAR(20)  NOT NULL DEFAULT 'system' CHECK (actor_type IN ('system', 'user', 'agent')),
    actor_id    VARCHAR(100),
    message     TEXT,
    metadata    JSONB        DEFAULT '{}',
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action);

-- ============================================================
-- ALTER PROCESSED_GEOSPATIAL_LAYERS (non-destructive)
-- ============================================================
ALTER TABLE processed_geospatial_layers ADD COLUMN IF NOT EXISTS footprint_geometry GEOMETRY(Polygon, 4326);
ALTER TABLE processed_geospatial_layers ADD COLUMN IF NOT EXISTS data_source_id INTEGER REFERENCES data_sources(id);

CREATE INDEX IF NOT EXISTS idx_processed_layers_footprint ON processed_geospatial_layers USING GIST (footprint_geometry);
CREATE INDEX IF NOT EXISTS idx_processed_layers_data_source ON processed_geospatial_layers (data_source_id);

COMMIT;
