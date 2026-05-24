"""Indicator repository implementation using PostgreSQL."""

from src.geospatial.domain.interfaces import IndicatorRepository
from src.geospatial.domain.models import Indicator
from src.geospatial.infrastructure.persistence.postgres_repositories import (
    _get_connection,
)

try:
    import psycopg2
    import psycopg2.extras

    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


class IndicatorRepositoryImpl(IndicatorRepository):
    """CRUD and queries for the indicators table."""

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

    def save(self, indicator: Indicator) -> int:
        """Insert an indicator record.

        Args:
            indicator: The indicator to persist.

        Returns:
            The database-assigned indicator ID.
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO indicators (
                    region_id, processed_layer_id, indicator_code,
                    indicator_name, indicator_type, value, unit,
                    classification, confidence, calculation_method,
                    temporal_start, temporal_end, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    indicator.region_id,
                    indicator.processed_layer_id,
                    indicator.indicator_code,
                    indicator.indicator_name,
                    indicator.indicator_type,
                    indicator.value,
                    indicator.unit,
                    indicator.classification,
                    indicator.confidence,
                    indicator.calculation_method,
                    indicator.temporal_start,
                    indicator.temporal_end,
                    indicator.metadata,
                ),
            )
            row = cur.fetchone()
            self.conn.commit()

        return row["id"]

    def find_by_region(self, region_id: int) -> list[Indicator]:
        """Find all indicators for a given region.

        Args:
            region_id: The regions.id value.

        Returns:
            List of Indicator objects for the region.
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, region_id, processed_layer_id, indicator_code,
                       indicator_name, indicator_type, value, unit,
                       classification, confidence, calculation_method,
                       temporal_start, temporal_end, metadata, created_at
                FROM indicators
                WHERE region_id = %s
                ORDER BY created_at DESC
                """,
                (region_id,),
            )
            rows = cur.fetchall()

        return [self._row_to_indicator(row) for row in rows]

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()

    @staticmethod
    def _row_to_indicator(row: dict) -> Indicator:
        """Convert a database row to an Indicator domain model."""
        return Indicator(
            id=row["id"],
            region_id=row["region_id"],
            processed_layer_id=row["processed_layer_id"],
            indicator_code=row["indicator_code"],
            indicator_name=row["indicator_name"],
            indicator_type=row["indicator_type"],
            value=float(row["value"]) if row["value"] is not None else None,
            unit=row["unit"],
            classification=row["classification"],
            confidence=float(row["confidence"]) if row["confidence"] is not None else None,
            calculation_method=row["calculation_method"],
            temporal_start=str(row["temporal_start"]) if row["temporal_start"] else None,
            temporal_end=str(row["temporal_end"]) if row["temporal_end"] else None,
            metadata=row["metadata"] or {},
            created_at=str(row["created_at"]) if row["created_at"] else None,
        )
