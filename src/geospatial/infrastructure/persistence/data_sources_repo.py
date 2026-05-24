"""Data source repository implementation using PostgreSQL."""

from typing import Any

from src.geospatial.domain.interfaces import DataSourceRepository
from src.geospatial.infrastructure.persistence.postgres_repositories import (
    _get_connection,
)

try:
    import psycopg2
    import psycopg2.extras

    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


class DataSourceRepositoryImpl(DataSourceRepository):
    """Queries for the data_sources table."""

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

    def get_by_code(self, code: str) -> dict[str, Any] | None:
        """Retrieve a data source by its unique code.

        Args:
            code: The data_sources.code value.

        Returns:
            Dict of data source fields or None if not found.
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, code, name, provider, source_type,
                       access_method, requires_auth, config,
                       is_active, created_at, updated_at
                FROM data_sources
                WHERE code = %s
                """,
                (code,),
            )
            row = cur.fetchone()

        return dict(row) if row else None

    def get_by_id(self, source_id: int) -> dict[str, Any] | None:
        """Retrieve a data source by its database ID.

        Args:
            source_id: The data_sources.id value.

        Returns:
            Dict of data source fields or None if not found.
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, code, name, provider, source_type,
                       access_method, requires_auth, config,
                       is_active, created_at, updated_at
                FROM data_sources
                WHERE id = %s
                """,
                (source_id,),
            )
            row = cur.fetchone()

        return dict(row) if row else None

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
