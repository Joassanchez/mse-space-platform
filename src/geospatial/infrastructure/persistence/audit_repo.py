"""Audit log repository implementation using PostgreSQL.

This repository propagates exceptions — error handling is the caller's
responsibility (typically the orchestrator wraps calls in try/except).
"""

from datetime import datetime

from src.geospatial.domain.interfaces import AuditRepository
from src.geospatial.domain.models import AuditLog
from src.geospatial.infrastructure.persistence.connection import get_connection

try:
    import psycopg2
    import psycopg2.extras

    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


class AuditRepositoryImpl(AuditRepository):
    """Append-only audit log repository.

    Propagates exceptions on failure — the orchestrator or caller must
    wrap calls in try/except to make audit non-fatal.
    """

    def __init__(self, connection=None) -> None:
        """Initialize repository.

        Args:
            connection: Optional existing psycopg2 connection.
        """
        self._conn = connection

    @property
    def conn(self):
        """Lazy connection property."""
        if self._conn is None or self._conn.closed:
            self._conn = get_connection()
        return self._conn

    def log_event(self, audit_log: AuditLog) -> int:
        """Insert an audit log entry.

        Args:
            audit_log: The audit log entry to persist.

        Returns:
            The database-assigned audit log ID.

        Raises:
            psycopg2.Error: On database failure (propagated, not caught).
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO audit_logs (
                    entity_type, entity_id, action, actor_type,
                    actor_id, message, metadata, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    audit_log.entity_type,
                    audit_log.entity_id,
                    audit_log.action,
                    audit_log.actor_type,
                    audit_log.actor_id,
                    audit_log.message,
                    audit_log.metadata,
                    audit_log.created_at or datetime.now().isoformat(),
                ),
            )
            row = cur.fetchone()
            self.conn.commit()

        return row["id"]

    @staticmethod
    def create_log(
        entity_type: str,
        action: str,
        entity_id: str | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
        message: str | None = None,
        metadata: dict | None = None,
    ) -> AuditLog:
        """Helper to create an AuditLog without constructing the dataclass manually.

        Args:
            entity_type: Type of entity being audited.
            action: Action performed.
            entity_id: ID of the entity.
            actor_type: Type of actor (default: "system").
            actor_id: ID of the actor.
            message: Human-readable description.
            metadata: Additional JSONB metadata.

        Returns:
            AuditLog dataclass instance.
        """
        return AuditLog(
            entity_type=entity_type,
            action=action,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_id=actor_id,
            message=message,
            metadata=metadata or {},
        )

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
