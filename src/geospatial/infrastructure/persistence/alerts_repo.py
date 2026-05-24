"""Alert repository implementation using PostgreSQL."""

from src.geospatial.domain.interfaces import AlertRepository
from src.geospatial.domain.models import Alert
from src.geospatial.infrastructure.persistence.postgres_repositories import (
    _get_connection,
)

try:
    import psycopg2
    import psycopg2.extras

    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


class AlertRepositoryImpl(AlertRepository):
    """CRUD and queries for the alerts table."""

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
            self._conn = _get_connection()
        return self._conn

    def save(self, alert: Alert) -> int:
        """Insert an alert record.

        Args:
            alert: The alert to persist.

        Returns:
            The database-assigned alert ID.
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO alerts (
                    region_id, risk_assessment_id, alert_type, severity,
                    title, message, status, issued_at, resolved_at, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    alert.region_id,
                    alert.risk_assessment_id,
                    alert.alert_type,
                    alert.severity,
                    alert.title,
                    alert.message,
                    alert.status,
                    alert.issued_at,
                    alert.resolved_at,
                    alert.metadata,
                ),
            )
            row = cur.fetchone()
            self.conn.commit()

        return row["id"]

    def find_active_by_region(self, region_id: int) -> list[Alert]:
        """Find active alerts for a given region.

        Args:
            region_id: The regions.id value.

        Returns:
            List of active Alert objects.
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, region_id, risk_assessment_id, alert_type, severity,
                       title, message, status, issued_at, resolved_at,
                       metadata, created_at
                FROM alerts
                WHERE region_id = %s AND status = 'active'
                ORDER BY issued_at DESC
                """,
                (region_id,),
            )
            rows = cur.fetchall()

        return [self._row_to_alert(row) for row in rows]

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()

    @staticmethod
    def _row_to_alert(row: dict) -> Alert:
        """Convert a database row to an Alert domain model."""
        return Alert(
            id=row["id"],
            region_id=row["region_id"],
            risk_assessment_id=row["risk_assessment_id"],
            alert_type=row["alert_type"],
            severity=row["severity"],
            title=row["title"],
            message=row["message"],
            status=row["status"],
            issued_at=str(row["issued_at"]) if row["issued_at"] else None,
            resolved_at=str(row["resolved_at"]) if row["resolved_at"] else None,
            metadata=row["metadata"] or {},
            created_at=str(row["created_at"]) if row["created_at"] else None,
        )
