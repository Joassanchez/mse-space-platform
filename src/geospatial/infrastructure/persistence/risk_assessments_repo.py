"""Risk assessment repository implementation using PostgreSQL."""

from src.geospatial.domain.interfaces import RiskAssessmentRepository
from src.geospatial.domain.models import RiskAssessment
from src.geospatial.infrastructure.persistence.connection import get_connection

try:
    import psycopg2
    import psycopg2.extras

    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


class RiskAssessmentRepositoryImpl(RiskAssessmentRepository):
    """CRUD and queries for the risk_assessments table."""

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

    def save(self, assessment: RiskAssessment) -> int:
        """Insert a risk assessment record.

        Args:
            assessment: The assessment to persist.

        Returns:
            The database-assigned assessment ID.
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO risk_assessments (
                    region_id, indicator_id, risk_type, risk_level,
                    risk_score, confidence, method, explanation,
                    temporal_start, temporal_end, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    assessment.region_id,
                    assessment.indicator_id,
                    assessment.risk_type,
                    assessment.risk_level,
                    assessment.risk_score,
                    assessment.confidence,
                    assessment.method,
                    assessment.explanation,
                    assessment.temporal_start,
                    assessment.temporal_end,
                    assessment.metadata,
                ),
            )
            row = cur.fetchone()
            self.conn.commit()

        return row["id"]

    def find_by_region_and_date(
        self, region_id: int, date_from: str | None = None, date_to: str | None = None
    ) -> list[RiskAssessment]:
        """Find risk assessments for a region within a date range.

        Args:
            region_id: The regions.id value.
            date_from: Start date filter (inclusive).
            date_to: End date filter (inclusive).

        Returns:
            List of matching RiskAssessment objects.
        """
        query = """
            SELECT id, region_id, indicator_id, risk_type, risk_level,
                   risk_score, confidence, method, explanation,
                   temporal_start, temporal_end, metadata, created_at
            FROM risk_assessments
            WHERE region_id = %s
        """
        params: list = [region_id]

        if date_from:
            query += " AND temporal_start >= %s"
            params.append(date_from)

        if date_to:
            query += " AND temporal_end <= %s"
            params.append(date_to)

        query += " ORDER BY created_at DESC"

        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        return [self._row_to_assessment(row) for row in rows]

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()

    @staticmethod
    def _row_to_assessment(row: dict) -> RiskAssessment:
        """Convert a database row to a RiskAssessment domain model."""
        return RiskAssessment(
            id=row["id"],
            region_id=row["region_id"],
            indicator_id=row["indicator_id"],
            risk_type=row["risk_type"],
            risk_level=row["risk_level"],
            risk_score=float(row["risk_score"]) if row["risk_score"] is not None else None,
            confidence=float(row["confidence"]) if row["confidence"] is not None else None,
            method=row["method"],
            explanation=row["explanation"],
            temporal_start=str(row["temporal_start"]) if row["temporal_start"] else None,
            temporal_end=str(row["temporal_end"]) if row["temporal_end"] else None,
            metadata=row["metadata"] or {},
            created_at=str(row["created_at"]) if row["created_at"] else None,
        )
