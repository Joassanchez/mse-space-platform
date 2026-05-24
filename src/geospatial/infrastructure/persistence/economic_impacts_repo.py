"""Economic impact repository implementation using PostgreSQL."""

from src.geospatial.domain.interfaces import EconomicImpactRepository
from src.geospatial.domain.models import EconomicImpact
from src.geospatial.infrastructure.persistence.postgres_repositories import (
    _get_connection,
)

try:
    import psycopg2
    import psycopg2.extras

    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


class EconomicImpactRepositoryImpl(EconomicImpactRepository):
    """CRUD and queries for the economic_impacts table."""

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

    def save(self, impact: EconomicImpact) -> int:
        """Insert an economic impact record.

        Args:
            impact: The impact to persist.

        Returns:
            The database-assigned impact ID.
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO economic_impacts (
                    region_id, risk_assessment_id, impact_type,
                    estimated_loss_usd, affected_area_ha, crop_type,
                    yield_loss_pct, method, assumptions, confidence, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    impact.region_id,
                    impact.risk_assessment_id,
                    impact.impact_type,
                    impact.estimated_loss_usd,
                    impact.affected_area_ha,
                    impact.crop_type,
                    impact.yield_loss_percentage,
                    impact.method,
                    impact.assumptions,
                    impact.confidence,
                    impact.metadata,
                ),
            )
            row = cur.fetchone()
            self.conn.commit()

        return row["id"]

    def find_by_indicator(self, indicator_id: int) -> list[EconomicImpact]:
        """Find economic impacts associated with an indicator.

        Note: economic_impacts links to risk_assessments, which link to indicators.
        This query joins through risk_assessments to find impacts by indicator.

        Args:
            indicator_id: The indicators.id value.

        Returns:
            List of EconomicImpact objects.
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT ei.id, ei.region_id, ei.risk_assessment_id, ei.impact_type,
                       ei.estimated_loss_usd, ei.affected_area_ha, ei.crop_type,
                       ei.yield_loss_pct, ei.method, ei.assumptions,
                       ei.confidence, ei.metadata, ei.created_at
                FROM economic_impacts ei
                JOIN risk_assessments ra ON ei.risk_assessment_id = ra.id
                WHERE ra.indicator_id = %s
                ORDER BY ei.created_at DESC
                """,
                (indicator_id,),
            )
            rows = cur.fetchall()

        return [self._row_to_impact(row) for row in rows]

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()

    @staticmethod
    def _row_to_impact(row: dict) -> EconomicImpact:
        """Convert a database row to an EconomicImpact domain model."""
        return EconomicImpact(
            id=row["id"],
            region_id=row["region_id"],
            risk_assessment_id=row["risk_assessment_id"],
            impact_type=row["impact_type"],
            estimated_loss_usd=float(row["estimated_loss_usd"]) if row["estimated_loss_usd"] is not None else None,
            affected_area_ha=float(row["affected_area_ha"]) if row["affected_area_ha"] is not None else None,
            crop_type=row["crop_type"],
            yield_loss_percentage=float(row["yield_loss_pct"]) if row["yield_loss_pct"] is not None else None,
            method=row["method"],
            assumptions=row["assumptions"],
            confidence=float(row["confidence"]) if row["confidence"] is not None else None,
            metadata=row["metadata"] or {},
            created_at=str(row["created_at"]) if row["created_at"] else None,
        )
