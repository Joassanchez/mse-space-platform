-- Migration 006: Change agent_executions.id from SERIAL to UUID
-- Módulo 5: Area Orchestrators & Hydric Environmental Agents
--
-- Idempotent: only runs if id is still INTEGER type.
-- Uses pgcrypto for gen_random_uuid().
--
-- Run: psql -U mse_user -d mse_platform -f migrations/006_agent_executions_uuid.sql

BEGIN;

-- Enable pgcrypto extension for UUID generation (idempotent)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Migrate only if id is still INTEGER (not yet UUID)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'agent_executions'
        AND column_name = 'id'
        AND data_type = 'integer'
    ) THEN
        -- Drop sequence auto-created by SERIAL
        DROP SEQUENCE IF EXISTS agent_executions_id_seq CASCADE;

        -- Drop existing primary key constraint
        ALTER TABLE agent_executions DROP CONSTRAINT IF EXISTS agent_executions_pkey CASCADE;

        -- Remove SERIAL default
        ALTER TABLE agent_executions ALTER COLUMN id DROP DEFAULT;

        -- Cast to UUID, generating a unique UUID per existing row
        ALTER TABLE agent_executions ALTER COLUMN id TYPE UUID USING gen_random_uuid();

        -- Set new default for future inserts
        ALTER TABLE agent_executions ALTER COLUMN id SET DEFAULT gen_random_uuid();

        -- Re-add primary key
        ALTER TABLE agent_executions ADD PRIMARY KEY (id);
    END IF;
END $$;

COMMIT;
