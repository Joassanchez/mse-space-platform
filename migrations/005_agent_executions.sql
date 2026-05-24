-- Migration 005: Agent Executions table for MSE Space Platform
-- Módulo 5: Area Orchestrators & Hydric Environmental Agents
--
-- Run: psql -U mse_user -d mse_platform -f migrations/005_agent_executions.sql
--
-- Non-destructive: uses IF NOT EXISTS everywhere. Safe to run multiple times (idempotent).
-- No FK constraints to M3 or M4 tables — references are logical (application-level validation).

BEGIN;

-- ============================================================
-- AGENT EXECUTIONS
-- Records individual agent executions within area orchestrator workflows.
-- Used for analytics, debugging, and audit trails per agent run.
-- Logical references to ai_workflow_states (no FK for decoupling).
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_executions (
    id                    SERIAL PRIMARY KEY,
    agent_code            VARCHAR(50)   NOT NULL,          -- e.g. "AGENT-HYD-SM-001"
    orchestrator_area     VARCHAR(50)   NOT NULL,          -- e.g. "hydric-environmental"
    workflow_id           VARCHAR(100)  NOT NULL,          -- parent workflow run ID
    context_payload       JSONB,                           -- context passed to agent
    structured_output     JSONB,                           -- structured agent output
    natural_language_output TEXT,                          -- template-based NL summary
    confidence_score      NUMERIC(4,3),                    -- 0.000–1.000
    data_completeness     NUMERIC(4,3),                    -- 0.000–1.000
    llm_model_used        VARCHAR(100),                    -- LiteLLM model identifier
    started_at            TIMESTAMPTZ,                     -- execution start time
    finished_at           TIMESTAMPTZ,                     -- execution end time
    error_message         TEXT,                            -- error text if failed
    status                VARCHAR(30)   DEFAULT 'pending'
                              CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    created_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_executions_workflow ON agent_executions (workflow_id);
CREATE INDEX IF NOT EXISTS idx_agent_executions_agent ON agent_executions (agent_code);
CREATE INDEX IF NOT EXISTS idx_agent_executions_area ON agent_executions (orchestrator_area);
CREATE INDEX IF NOT EXISTS idx_agent_executions_status ON agent_executions (status);
CREATE INDEX IF NOT EXISTS idx_agent_executions_created ON agent_executions (created_at DESC);

COMMIT;
