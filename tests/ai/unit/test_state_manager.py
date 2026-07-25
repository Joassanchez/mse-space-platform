"""Unit tests for State Manager (mocked database).

Tests:
- CRUD operations for workflow states
- Trace persistence
- Connection handling
- Idempotency: duplicate workflow_id returns existing state
- Idempotency: same-status update is no-op
- Idempotency: invalid state transitions are rejected
"""

from unittest.mock import MagicMock, call, patch

import pytest

from src.ai.infrastructure.state.state_manager import (
    StateManagerImpl,
    VALID_TRANSITIONS,
)


@pytest.fixture
def mock_conn():
    """Create a mock psycopg2 connection."""
    conn = MagicMock()
    conn.closed = False
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    # No default side_effect — each test sets its own fetchone behavior
    cursor.fetchone.return_value = None
    return conn


@pytest.fixture
def state_manager(mock_conn):
    """Create StateManagerImpl with mocked connection."""
    with patch("psycopg2.connect", return_value=mock_conn):
        manager = StateManagerImpl(
            host="localhost",
            database="test_db",
            user="test_user",
            password="test_pass",
        )
        manager._conn = mock_conn
        return manager


class TestStateManagerCreateState:
    """Test workflow state creation."""

    def test_create_state_returns_id(self, state_manager, mock_conn):
        """create_state returns the database-assigned ID."""
        cursor = mock_conn.cursor.return_value.__enter__.return_value
        # Two sequential calls: idempotency SELECT → None, INSERT RETURNING → (42,)
        cursor.fetchone.side_effect = [None, (42,)]

        state_id = state_manager.create_state(
            workflow_id="wf-001",
            initial_state={"status": "pending", "context": {}, "metadata": {}},
        )

        assert state_id == 42
        mock_conn.commit.assert_called()

    def test_create_state_inserts_correct_values(self, state_manager, mock_conn):
        """create_state inserts workflow_id, status, context, metadata."""
        cursor = mock_conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [None, (42,)]

        state_manager.create_state(
            workflow_id="wf-001",
            initial_state={"status": "running", "context": {"key": "value"}},
        )

        # Two execute calls: idempotency check + INSERT
        assert cursor.execute.call_count >= 1
        # Find the INSERT call
        insert_calls = [
            c for c in cursor.execute.call_args_list
            if "INSERT" in str(c)
        ]
        assert len(insert_calls) >= 1
        sql = insert_calls[0][0][0]
        params = insert_calls[0][0][1]

        assert "INSERT INTO ai_workflow_states" in sql
        assert params[0] == "wf-001"
        assert params[1] == "running"

    def test_create_state_idempotent_returns_existing(self, state_manager, mock_conn):
        """create_state returns existing state_id when workflow_id already exists."""
        cursor = mock_conn.cursor.return_value.__enter__.return_value
        # First call (idempotency check) returns existing state
        cursor.fetchone.side_effect = [(99,), None]

        state_id = state_manager.create_state(
            workflow_id="wf-existing",
            initial_state={"status": "pending"},
        )

        assert state_id == 99
        # Should NOT have called commit (no INSERT)
        mock_conn.commit.assert_not_called()


class TestStateManagerUpdateState:
    """Test workflow state updates."""

    def test_update_status(self, state_manager, mock_conn):
        """update_state can update status field."""
        cursor = mock_conn.cursor.return_value.__enter__.return_value
        # Idempotency check: current status is "pending", transition to "running" is valid
        cursor.fetchone.side_effect = [
            ("pending",),  # current status check
        ]

        state_manager.update_state(state_id=42, state={"status": "running"})

        assert "UPDATE ai_workflow_states" in str(cursor.execute.call_args_list)

    def test_update_context(self, state_manager, mock_conn):
        """update_state can update context field."""
        cursor = mock_conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [("pending",)]

        state_manager.update_state(
            state_id=42,
            state={"context": {"result": "done"}},
        )

        assert "context = %s" in str(cursor.execute.call_args_list)

    def test_update_empty_state_no_op(self, state_manager, mock_conn):
        """update_state does nothing when no fields provided."""
        cursor = mock_conn.cursor.return_value.__enter__.return_value

        state_manager.update_state(state_id=42, state={})

        cursor.execute.assert_not_called()

    def test_update_same_status_is_no_op(self, state_manager, mock_conn):
        """update_state skips when status is already the target."""
        cursor = mock_conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [("completed",)]

        state_manager.update_state(state_id=42, state={"status": "completed"})

        # Should not execute UPDATE for status
        update_calls = [
            c for c in cursor.execute.call_args_list
            if "UPDATE" in str(c)
        ]
        assert len(update_calls) == 0

    def test_update_invalid_transition_rejected(self, state_manager, mock_conn):
        """update_state rejects invalid transitions (completed → running)."""
        cursor = mock_conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [("completed",)]

        state_manager.update_state(state_id=42, state={"status": "running"})

        # Should NOT update status
        update_calls = [
            c for c in cursor.execute.call_args_list
            if "UPDATE" in str(c) and "status" in str(c)
        ]
        assert len(update_calls) == 0


class TestStateManagerValidTransitions:
    """Test valid state transition table."""

    def test_pending_can_go_to_running(self):
        """pending → running is valid."""
        assert "running" in VALID_TRANSITIONS["pending"]

    def test_running_can_go_to_completed(self):
        """running → completed is valid."""
        assert "completed" in VALID_TRANSITIONS["running"]

    def test_running_can_go_to_failed(self):
        """running → failed is valid."""
        assert "failed" in VALID_TRANSITIONS["running"]

    def test_completed_is_terminal(self):
        """completed is a terminal state."""
        assert VALID_TRANSITIONS["completed"] == set()

    def test_failed_is_terminal(self):
        """failed is a terminal state."""
        assert VALID_TRANSITIONS["failed"] == set()


class TestStateManagerPersistTrace:
    """Test execution trace persistence."""

    def test_persist_trace_returns_id(self, state_manager, mock_conn):
        """persist_trace returns the database-assigned trace ID."""
        cursor = mock_conn.cursor.return_value.__enter__.return_value
        # Reset fetchone for this test
        cursor.fetchone.return_value = (99,)

        trace_id = state_manager.persist_trace(
            state_id=42,
            step="build_context",
            action="read_m3_data",
            result={"regions": 1, "indicators": 5},
        )

        assert trace_id == 99
        mock_conn.commit.assert_called()

    def test_persist_trace_inserts_correct_values(self, state_manager, mock_conn):
        """persist_trace inserts state_id, step, action, result."""
        cursor = mock_conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (99,)

        state_manager.persist_trace(
            state_id=42,
            step="execute_agent",
            action="run_reference",
            result={"conclusion": "test"},
        )

        # Find the INSERT call (skip any SELECT calls from previous tests)
        insert_calls = [
            c for c in cursor.execute.call_args_list
            if "INSERT INTO ai_execution_traces" in str(c)
        ]
        assert len(insert_calls) >= 1
        sql = insert_calls[-1][0][0]
        params = insert_calls[-1][0][1]

        assert "INSERT INTO ai_execution_traces" in sql
        assert params[0] == 42
        assert params[1] == "execute_agent"
        assert params[2] == "run_reference"


class TestStateManagerClose:
    """Test connection cleanup."""

    def test_close_closes_connection(self, state_manager, mock_conn):
        """close() closes the database connection."""
        state_manager.close()

        mock_conn.close.assert_called()
        assert state_manager._conn is None
