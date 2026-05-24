-- Migration 004: AI Foundation tables for MSE Space Platform
-- Slice 1: Foundation (ai_workflow_states, ai_execution_traces, ai_prompt_metadata)
--
-- Run: psql -U mse_user -d mse_platform -f migrations/004_ai_foundation.sql
--
-- Non-destructive: uses IF NOT EXISTS everywhere. Safe to run multiple times (idempotent).
-- No FK constraints to M3 tables — references are logical (application-level validation).

BEGIN;

-- ============================================================
-- AI WORKFLOW STATES
-- Tracks the lifecycle of AI workflow executions.
-- Logical references to M3 entities (no FKs).
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_workflow_states (
    id              SERIAL PRIMARY KEY,
    workflow_id     VARCHAR(100) NOT NULL UNIQUE,
    status          VARCHAR(30)  NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    context         JSONB        DEFAULT '{}',
    metadata        JSONB        DEFAULT '{}',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_workflow_states_status ON ai_workflow_states (status);
CREATE INDEX IF NOT EXISTS idx_ai_workflow_states_created ON ai_workflow_states (created_at DESC);

-- ============================================================
-- AI EXECUTION TRACES
-- Records individual steps within a workflow execution.
-- Logical reference to ai_workflow_states (no FK for decoupling).
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_execution_traces (
    id              SERIAL PRIMARY KEY,
    state_id        INTEGER      NOT NULL,  -- logical ref to ai_workflow_states.id
    step            VARCHAR(100) NOT NULL,
    action          VARCHAR(100) NOT NULL,
    result          JSONB,
    error           TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_execution_traces_state ON ai_execution_traces (state_id);
CREATE INDEX IF NOT EXISTS idx_ai_execution_traces_step ON ai_execution_traces (step);
CREATE INDEX IF NOT EXISTS idx_ai_execution_traces_created ON ai_execution_traces (created_at DESC);

-- ============================================================
-- AI PROMPT METADATA
-- Stores metadata and production overrides for prompt templates.
-- Source of truth for prompts is data/prompts/ files (versioned in git).
-- This table holds only metadata: active version, overrides, audit trail.
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_prompt_metadata (
    id              SERIAL PRIMARY KEY,
    template_name   VARCHAR(100) NOT NULL UNIQUE,
    active_version  VARCHAR(20)  NOT NULL DEFAULT '1.0.0',
    override_content TEXT,       -- production override (null = use file)
    updated_by      VARCHAR(100),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_prompt_metadata_name ON ai_prompt_metadata (template_name);

-- ============================================================
-- AUDIT LOGS actor_type check
-- Migration 003 already includes 'agent' in the CHECK constraint:
--   CHECK (actor_type IN ('system', 'user', 'agent'))
-- No ALTER needed — M4 can write actor_type='agent' immediately.
-- ============================================================

COMMIT;
