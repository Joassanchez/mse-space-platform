"""Integration tests for AI State Manager against PostgreSQL.

These tests require:
- Docker running with PostgreSQL (docker compose up -d)
- psycopg2-binary installed
- PG* env vars (or defaults matching docker-compose.yml)
- Migration 004 applied (ai_workflow_states, ai_execution_traces tables)

Run with: pytest -m integration tests/ai/integration/test_state_manager.py
"""

import os

import pytest

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
class TestStateManagerIntegration:
    """Test State Manager CRUD against real PostgreSQL."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure PostgreSQL is available and clean test data."""
        if not pg_available():
            pytest.skip(
                "PostgreSQL not available or AI tables not migrated — "
                "is docker compose up and migration 004 applied?"
            )

        self.manager = StateManagerImpl()
        # Clean up test data from previous runs
        conn = self.manager._get_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ai_execution_traces WHERE state_id IN "
                        "(SELECT id FROM ai_workflow_states WHERE workflow_id LIKE 'test-%')")
            cur.execute("DELETE FROM ai_workflow_states WHERE workflow_id LIKE 'test-%'")
            conn.commit()
        yield
        self.manager.close()

    def test_create_and_retrieve_state(self):
        """Create a workflow state and verify it persists."""
        state_id = self.manager.create_state(
            workflow_id="test-integration-001",
            initial_state={
                "status": "pending",
                "context": {"region_ids": [1]},
                "metadata": {"test": True},
            },
        )

        assert state_id is not None
        assert isinstance(state_id, int)

        # Verify in database
        conn = self.manager._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT workflow_id, status, context, metadata FROM ai_workflow_states WHERE id = %s",
                (state_id,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row[0] == "test-integration-001"
        assert row[1] == "pending"

    def test_update_state_status(self):
        """Update workflow state status."""
        state_id = self.manager.create_state(
            workflow_id="test-integration-002",
            initial_state={"status": "pending"},
        )

        self.manager.update_state(state_id, {"status": "running"})

        conn = self.manager._get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM ai_workflow_states WHERE id = %s", (state_id,))
            status = cur.fetchone()[0]

        assert status == "running"

    def test_update_state_context(self):
        """Update workflow state context."""
        state_id = self.manager.create_state(
            workflow_id="test-integration-003",
            initial_state={"status": "pending", "context": {}},
        )

        self.manager.update_state(
            state_id,
            {"context": {"result": "completed", "data": [1, 2, 3]}},
        )

        conn = self.manager._get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT context FROM ai_workflow_states WHERE id = %s", (state_id,))
            context = cur.fetchone()[0]

        assert context["result"] == "completed"

    def test_persist_trace(self):
        """Persist an execution trace."""
        state_id = self.manager.create_state(
            workflow_id="test-integration-004",
            initial_state={"status": "running"},
        )

        trace_id = self.manager.persist_trace(
            state_id=state_id,
            step="build_context",
            action="read_m3_data",
            result={"regions": 1, "indicators": 5},
        )

        assert trace_id is not None
        assert isinstance(trace_id, int)

        # Verify in database
        conn = self.manager._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT state_id, step, action, result FROM ai_execution_traces WHERE id = %s",
                (trace_id,),
            )
            row = cur.fetchone()

        assert row is not None
        assert row[0] == state_id
        assert row[1] == "build_context"
        assert row[2] == "read_m3_data"
        assert row[3]["regions"] == 1

    def test_full_workflow_lifecycle(self):
        """Test complete workflow: create → update → trace → complete."""
        # Create
        state_id = self.manager.create_state(
            workflow_id="test-integration-lifecycle",
            initial_state={
                "status": "pending",
                "context": {"region_ids": [1, 2]},
            },
        )

        # Update to running
        self.manager.update_state(state_id, {"status": "running"})

        # Persist trace
        self.manager.persist_trace(
            state_id=state_id,
            step="build_context",
            action="read_m3",
            result={"count": 2},
        )

        # Update to completed
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

        assert count == 1
