"""Region repository implementation using PostgreSQL + PostGIS.

Implements RegionRepository with spatial queries via PostGIS ST_Intersects.
"""

from typing import Any

from src.geospatial.domain.interfaces import RegionRepository
from src.geospatial.domain.models import Region
from src.geospatial.infrastructure.persistence.postgres_repositories import (
    _get_connection,
)

try:
    import psycopg2
    import psycopg2.extras
    import shapely.wkt

    HAS_POSTGIS_DEPS = True
except ImportError:
    HAS_POSTGIS_DEPS = False


class RegionRepositoryImpl(RegionRepository):
    """CRUD and spatial queries for the regions table.

    Uses PostGIS for geometry storage (WKT) and spatial queries (ST_Intersects).
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
            self._conn = _get_connection()
        return self._conn

    def save(self, region: Region) -> int:
        """Insert a region record.

        Args:
            region: The region to persist (geometry as Shapely MultiPolygon).

        Returns:
            The database-assigned region ID.
        """
        geom_wkt = shapely.wkt.dumps(region.geometry) if region.geometry else None

        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO regions (
                    name, geometry, region_type, country, province,
                    bbox, area_km2, metadata, is_active
                ) VALUES (
                    %s, ST_GeomFromText(%s, 4326), %s, %s, %s,
                    %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    region.name,
                    geom_wkt,
                    region.region_type,
                    region.country,
                    region.province,
                    region.bbox,
                    region.area_km2,
                    psycopg2.extras.Json(region.metadata) if region.metadata else None,
                    region.is_active,
                ),
            )
            row = cur.fetchone()
            self.conn.commit()

        return row["id"]

    def get_by_id(self, region_id: int) -> Region | None:
        """Retrieve a region by its database ID.

        Args:
            region_id: The regions.id value.

        Returns:
            Region if found, None otherwise.
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, name, ST_AsText(geometry) AS geometry_wkt,
                       region_type, country, province, bbox, area_km2,
                       metadata, is_active, created_at, updated_at
                FROM regions
                WHERE id = %s
                """,
                (region_id,),
            )
            row = cur.fetchone()

        if row is None:
            return None

        return self._row_to_region(row)

    def find_intersecting_geometry(self, wkt: str) -> list[Region]:
        """Find regions whose geometry intersects the given WKT polygon.

        Uses PostGIS ST_Intersects for spatial query.

        Args:
            wkt: WKT string of the query geometry (EPSG:4326).

        Returns:
            List of intersecting Region objects.
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, name, ST_AsText(geometry) AS geometry_wkt,
                       region_type, country, province, bbox, area_km2,
                       metadata, is_active, created_at, updated_at
                FROM regions
                WHERE ST_Intersects(geometry, ST_GeomFromText(%s, 4326))
                  AND is_active = TRUE
                """,
                (wkt,),
            )
            rows = cur.fetchall()

        return [self._row_to_region(row) for row in rows]

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()

    @staticmethod
    def _row_to_region(row: dict[str, Any]) -> Region:
        """Convert a database row to a Region domain model.

        Args:
            row: Dict from RealDictCursor.

        Returns:
            Region dataclass instance.
        """
        geometry = None
        if row.get("geometry_wkt") and HAS_POSTGIS_DEPS:
            geometry = shapely.wkt.loads(row["geometry_wkt"])

        return Region(
            id=row["id"],
            name=row["name"],
            geometry=geometry,
            region_type=row["region_type"],
            country=row["country"],
            province=row["province"],
            bbox=list(row["bbox"]) if row["bbox"] else None,
            area_km2=float(row["area_km2"]) if row["area_km2"] else None,
            metadata=row["metadata"] or {},
            is_active=row["is_active"],
            created_at=str(row["created_at"]) if row["created_at"] else None,
            updated_at=str(row["updated_at"]) if row["updated_at"] else None,
        )
