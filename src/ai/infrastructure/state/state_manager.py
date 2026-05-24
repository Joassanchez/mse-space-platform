"""State Manager implementation for the AI ecosystem.

Persists AI workflow states and execution traces to PostgreSQL using
separate tables (ai_workflow_states, ai_execution_traces) with no FK
constraints to M3 tables. References are logical (application-level).

Idempotency:
- create_state: if workflow_id already exists, returns existing state_id
  instead of duplicating (safe for retry scenarios).
- update_state: validates state transitions to prevent invalid moves
  (e.g. completed → running).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from src.ai.domain.interfaces import StateManager

logger = logging.getLogger(__name__)

# Valid state transitions for idempotency checks
VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running", "cancelled", "failed"},
    "running": {"completed", "failed", "cancelled"},
    "completed": set(),  # Terminal state
    "failed": set(),  # Terminal state
    "cancelled": set(),  # Terminal state
}


class StateManagerImpl(StateManager):
    """Concrete StateManager that persists to PostgreSQL.

    Uses psycopg2 for database connectivity. Connection parameters
    are read from PG* environment variables (PGHOST, PGDATABASE, etc.)
    or explicit constructor arguments.
    """

    def __init__(
        self,
        host: str | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
        port: int | None = None,
    ):
        """Initialize the State Manager with database connection parameters.

        Falls back to PG* environment variables if not provided.

        Args:
            host: PostgreSQL host (env: PGHOST).
            database: Database name (env: PGDATABASE).
            user: Database user (env: PGUSER).
            password: Database password (env: PGPASSWORD).
            port: Database port (env: PGPORT).
        """
        import os

        self._host = host or os.getenv("PGHOST", "localhost")
        self._database = database or os.getenv("PGDATABASE", "mse_platform")
        self._user = user or os.getenv("PGUSER", "mse_user")
        self._password = password or os.getenv("PGPASSWORD", "mse_pass")
        self._port = port or int(os.getenv("PGPORT", "5432"))
        self._conn: psycopg2.extensions.connection | None = None

    def _get_connection(self) -> psycopg2.extensions.connection:
        """Get or create a database connection."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(
                host=self._host,
                database=self._database,
                user=self._user,
                password=self._password,
                port=self._port,
            )
        return self._conn

    def create_state(self, workflow_id: str, initial_state: dict) -> int:
        """Create initial workflow state.

        Idempotent: if workflow_id already exists, returns the existing
        state_id instead of creating a duplicate.

        Args:
            workflow_id: Unique workflow identifier.
            initial_state: Dict with status, context, and metadata.

        Returns:
            Database-assigned state ID (new or existing).
        """
        conn = self._get_connection()
        with conn.cursor() as cur:
            # Idempotency check: return existing state if workflow_id exists
            cur.execute(
                "SELECT id FROM ai_workflow_states WHERE workflow_id = %s",
                (workflow_id,),
            )
            existing = cur.fetchone()
            if existing:
                logger.info(
                    f"Workflow {workflow_id} already exists (id={existing[0]}) — "
                    f"returning existing state (idempotent)"
                )
                return existing[0]

            cur.execute(
                """
                INSERT INTO ai_workflow_states (workflow_id, status, context, metadata)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (
                    workflow_id,
                    initial_state.get("status", "pending"),
                    json.dumps(initial_state.get("context", {})),
                    json.dumps(initial_state.get("metadata", {})),
                ),
            )
            state_id = cur.fetchone()[0]
            conn.commit()
        return state_id

    def update_state(self, state_id: int, state: dict) -> None:
        """Update workflow state.

        Validates state transitions: terminal states (completed, failed,
        cancelled) cannot be updated to a different status. Idempotent:
        if the state is already the target status, the update is a no-op.

        Args:
            state_id: The ai_workflow_states.id value.
            state: Dict with fields to update (status, context, metadata).
        """
        conn = self._get_connection()

        # Build dynamic update query based on provided fields
        updates = []
        values: list[Any] = []

        if "status" in state:
            new_status = state["status"]

            # Idempotency: check current status
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status FROM ai_workflow_states WHERE id = %s",
                    (state_id,),
                )
                row = cur.fetchone()

            if row:
                current_status = row[0]

                # Idempotent: already in target state
                if current_status == new_status:
                    logger.debug(
                        f"State {state_id} already in status '{new_status}' — "
                        f"skipping update (idempotent)"
                    )
                    # Still allow context/metadata updates
                    if "context" not in state and "metadata" not in state:
                        return

                # Validate transition
                allowed = VALID_TRANSITIONS.get(current_status, set())
                if new_status not in allowed and current_status != new_status:
                    logger.warning(
                        f"Invalid state transition for state {state_id}: "
                        f"'{current_status}' → '{new_status}' — skipping"
                    )
                    # Remove status from updates, allow other fields
                    state_copy = {k: v for k, v in state.items() if k != "status"}
                    if not state_copy:
                        return
                    return self._update_fields(conn, state_id, state_copy)

            updates.append("status = %s")
            values.append(new_status)

        if "context" in state:
            updates.append("context = %s")
            values.append(json.dumps(state["context"]))
        if "metadata" in state:
            updates.append("metadata = %s")
            values.append(json.dumps(state["metadata"]))

        if not updates:
            return

        updates.append("updated_at = NOW()")
        values.append(state_id)

        query = f"UPDATE ai_workflow_states SET {', '.join(updates)} WHERE id = %s"

        with conn.cursor() as cur:
            cur.execute(query, values)
            conn.commit()

    def _update_fields(
        self, conn: psycopg2.extensions.connection, state_id: int, state: dict
    ) -> None:
        """Update non-status fields on a workflow state.

        Args:
            conn: Database connection.
            state_id: The ai_workflow_states.id value.
            state: Dict with fields to update (context, metadata).
        """
        updates = []
        values: list[Any] = []

        if "context" in state:
            updates.append("context = %s")
            values.append(json.dumps(state["context"]))
        if "metadata" in state:
            updates.append("metadata = %s")
            values.append(json.dumps(state["metadata"]))

        if not updates:
            return

        updates.append("updated_at = NOW()")
        values.append(state_id)

        query = f"UPDATE ai_workflow_states SET {', '.join(updates)} WHERE id = %s"

        with conn.cursor() as cur:
            cur.execute(query, values)
            conn.commit()

    def persist_trace(self, state_id: int, step: str, action: str, result: Any) -> int:
        """Persist an execution trace entry.

        Args:
            state_id: Logical reference to ai_workflow_states.id.
            step: Step identifier (e.g. "build_context", "execute_agent").
            action: Action performed in this step.
            result: Step result (JSON-serializable).

        Returns:
            Database-assigned trace ID.
        """
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ai_execution_traces (state_id, step, action, result)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (state_id, step, action, json.dumps(result)),
            )
            trace_id = cur.fetchone()[0]
            conn.commit()
        return trace_id

    def persist_agent_execution(
        self,
        agent_code: str,
        orchestrator_area: str,
        workflow_id: str,
        context_payload: Optional[dict] = None,
        structured_output: Optional[dict] = None,
        natural_language_output: Optional[str] = None,
        confidence_score: float = 0.0,
        data_completeness: float = 0.0,
        llm_model_used: Optional[str] = None,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
        error_message: Optional[str] = None,
        status: str = "pending",
    ) -> str:
        """Persist an agent execution record to the agent_executions table.

        Used by area orchestrators to record individual agent runs with
        their outputs, confidence, and data completeness for analytics
        and audit trails. Returns UUID string per PRD §11.

        Args:
            agent_code: Agent identifier (e.g. "AGENT-HYD-SM-001").
            orchestrator_area: Area that orchestrated this execution.
            workflow_id: Parent workflow run ID.
            context_payload: JSON context passed to the agent.
            structured_output: JSON structured output from the agent.
            natural_language_output: Template-based NL summary.
            confidence_score: Execution confidence (0.0-1.0).
            data_completeness: Data completeness fraction (0.0-1.0).
            llm_model_used: LiteLLM model identifier (if LLM was used).
            started_at: ISO timestamp when execution started.
            finished_at: ISO timestamp when execution finished.
            error_message: Error text if execution failed.
            status: Lifecycle status (pending, running, completed, failed).

        Returns:
            UUID string of the persisted execution record.
        """
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_executions (
                    agent_code, orchestrator_area, workflow_id,
                    context_payload, structured_output, natural_language_output,
                    confidence_score, data_completeness, llm_model_used,
                    started_at, finished_at, error_message, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    agent_code,
                    orchestrator_area,
                    workflow_id,
                    json.dumps(context_payload) if context_payload else None,
                    json.dumps(structured_output) if structured_output else None,
                    natural_language_output,
                    confidence_score,
                    data_completeness,
                    llm_model_used,
                    started_at,
                    finished_at,
                    error_message,
                    status,
                ),
            )
            raw_id = cur.fetchone()[0]
            conn.commit()
        execution_id = str(raw_id)
        logger.debug(
            f"Agent execution persisted: id={execution_id}, "
            f"agent={agent_code}, area={orchestrator_area}"
        )
        return execution_id

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None
