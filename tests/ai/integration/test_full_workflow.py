"""Integration tests for full AI workflow.

Tests:
- E2E: query → context → agent → response
- State persistence across workflow steps
- Audit logs for AI events
- Full workflow with observability

Run with: pytest -m integration tests/ai/integration/test_full_workflow.py
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from src.ai.agents.reference_agent.agent import ReferenceAgent
from src.ai.domain.models import AgentManifest, ExecutionLimits
from src.ai.infrastructure.observability.audit_logger import AIAuditLogger
from src.ai.infrastructure.observability.tracing import AITracer
from src.ai.infrastructure.runtime.agent_runtime import AgentRuntimeImpl
from src.ai.infrastructure.runtime.plugin_system import PluginSystem
from src.ai.infrastructure.state.state_manager import StateManagerImpl


def pg_available() -> bool:
    """Check if PostgreSQL is reachable and AI tables exist."""
    try:
        manager = StateManagerImpl()
        conn = manager._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ai_workflow_states')"
            )
            exists = cur.fetchone()[0]
        manager.close()
        return exists
    except Exception:
        return False


@pytest.mark.integration
class TestFullWorkflow:
    """Test end-to-end AI workflow."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure PostgreSQL is available and clean test data."""
        if not pg_available():
            pytest.skip(
                "PostgreSQL not available or AI tables not migrated — "
                "is docker compose up and migration 004 applied?"
            )

        self.manager = StateManagerImpl()
        # Clean up test data
        conn = self.manager._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM ai_execution_traces WHERE state_id IN "
                "(SELECT id FROM ai_workflow_states WHERE workflow_id LIKE 'test-e2e-%')"
            )
            cur.execute(
                "DELETE FROM ai_workflow_states WHERE workflow_id LIKE 'test-e2e-%'"
            )
            conn.commit()
        yield
        self.manager.close()

    def test_full_workflow_state_persistence(self):
        """E2E: create state → persist traces → update to completed."""
        # Step 1: Create workflow state
        state_id = self.manager.create_state(
            workflow_id="test-e2e-full-workflow",
            initial_state={
                "status": "pending",
                "context": {"region_ids": [1]},
                "metadata": {"test": "e2e"},
            },
        )
        assert state_id is not None

        # Step 2: Persist trace for context building
        trace_id_1 = self.manager.persist_trace(
            state_id=state_id,
            step="build_context",
            action="read_m3_data",
            result={"regions": 1, "indicators": 2},
        )
        assert trace_id_1 is not None

        # Step 3: Update to running
        self.manager.update_state(state_id, {"status": "running"})

        # Step 4: Persist trace for agent execution
        trace_id_2 = self.manager.persist_trace(
            state_id=state_id,
            step="execute_reference_agent",
            action="agent_complete",
            result={"conclusion": "Test result", "confidence": 0.5},
        )
        assert trace_id_2 is not None

        # Step 5: Update to completed
        self.manager.update_state(state_id, {"status": "completed"})

        # Verify final state
        conn = self.manager._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM ai_workflow_states WHERE id = %s",
                (state_id,),
            )
            status = cur.fetchone()[0]
        assert status == "completed"

        # Verify trace count
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM ai_execution_traces WHERE state_id = %s",
                (state_id,),
            )
            count = cur.fetchone()[0]
        assert count == 2  # Two traces persisted

    def test_workflow_idempotency(self):
        """E2E: duplicate workflow_id returns same state_id."""
        state_id_1 = self.manager.create_state(
            workflow_id="test-e2e-idempotent",
            initial_state={"status": "pending"},
        )

        state_id_2 = self.manager.create_state(
            workflow_id="test-e2e-idempotent",
            initial_state={"status": "pending"},
        )

        assert state_id_1 == state_id_2

    def test_reference_agent_execution(self):
        """E2E: reference agent executes and produces valid output."""
        agent = ReferenceAgent()
        runtime = AgentRuntimeImpl()

        mock_context = {
            "regions": [{"id": 1, "name": "Test Region"}],
            "indicators": [{"indicator_code": "SM_INDEX", "value": 0.45}],
            "risk_assessments": [],
            "metadata": {"entity_counts": {"regions": 1}},
            "warnings": [],
        }

        limits = ExecutionLimits(timeout_seconds=30)
        output = runtime.execute(agent, context=mock_context, limits=limits)

        assert "conclusion" in output
        assert "confidence" in output
        assert 0 <= output["confidence"] <= 1

    def test_audit_logger_with_workflow(self):
        """E2E: audit logger records workflow events."""
        audit_logger = AIAuditLogger(audit_repo=None)  # No repo, logging only

        # Log workflow lifecycle
        audit_logger.log_workflow_start("test-e2e-audit", workflow_type="test")
        audit_logger.log_agent_start("test-e2e-audit", "reference-agent")
        audit_logger.log_agent_complete(
            "test-e2e-audit",
            "reference-agent",
            model="gpt-4o-mini",
            token_usage={"total_tokens": 100},
            duration_ms=250.0,
        )
        audit_logger.log_workflow_complete(
            "test-e2e-audit",
            total_duration_ms=500.0,
            step_count=3,
            total_tokens=200,
        )

        # No exceptions — non-fatal mode works
        assert True

    def test_tracer_spans(self):
        """E2E: tracer creates spans without errors."""
        tracer = AITracer(service_name="test-ai")

        # These should not raise even without OTel configured
        with tracer.workflow_span("test-e2e-trace", "test") as span:
            with tracer.step_span("build_context", workflow_id="test-e2e-trace"):
                pass
            with tracer.tool_span("geospatial_query", agent_id="test"):
                pass
            with tracer.llm_span("gpt-4o-mini"):
                pass
