"""PostgreSQL repositories for geospatial persistence.

Implements RawFileDiscoveryRepository, GeospatialProcessingJobRepository,
and ProcessedLayerRepository using psycopg2.

Follows the existing connection pattern from metadata_repository_pg.py.
"""

import os
from datetime import datetime
from typing import Any

from src.geospatial.domain.interfaces import (
    GeospatialProcessingJobRepository,
    ProcessedLayerRepository,
    RawFileDiscoveryRepository,
)
from src.geospatial.domain.models import GeospatialProcessingJob, ProcessedLayer

try:
    import psycopg2
    import psycopg2.extras

    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

from src.geospatial.infrastructure.persistence.connection import get_connection as _get_connection


class RawFileDiscoveryRepositoryImpl(RawFileDiscoveryRepository):
    """Discovers raw files pending geospatial processing.

    Queries raw_files table for completed files with ready_for_etl=TRUE.
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

    def find_completed(
        self, source: str, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Find raw files with completed status pending geospatial processing.

        Args:
            source: Source code filter (e.g. "SMAP").
            limit: Maximum number of files to return (None for all).

        Returns:
            List of raw file dicts with id, file_path, source_product_id, etc.
        """
        query = """
            SELECT rf.*
            FROM raw_files rf
            JOIN ingestion_jobs ij ON rf.ingestion_job_id = ij.id
            JOIN data_sources ds ON rf.source_id = ds.id
            WHERE rf.ready_for_etl = TRUE
              AND ds.code = %s
            ORDER BY rf.created_at ASC
        """

        params: list[Any] = [source]

        if limit is not None:
            query += " LIMIT %s"
            params.append(limit)

        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        return [dict(row) for row in rows]

    def find_by_id(self, raw_file_id: int) -> dict[str, Any] | None:
        """Find a specific raw file by its database ID.

        Args:
            raw_file_id: The raw_files.id value.

        Returns:
            Raw file dict or None if not found.
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT rf.*
                FROM raw_files rf
                WHERE rf.id = %s
                  AND rf.ready_for_etl = TRUE
                """,
                (raw_file_id,),
            )
            row = cur.fetchone()

        return dict(row) if row else None

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()


class GeospatialProcessingJobRepositoryImpl(GeospatialProcessingJobRepository):
    """CRUD for geospatial_processing_jobs table."""

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

    def create(self, job: GeospatialProcessingJob) -> None:
        """Insert a new processing job record.

        Args:
            job: The job to create (must have id set).
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO geospatial_processing_jobs (
                    id, raw_file_id, source_code, status,
                    started_at, finished_at, error_message, warnings, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    job.id,
                    job.raw_file_id,
                    job.source_code,
                    job.status,
                    job.started_at,
                    job.finished_at,
                    job.error_message,
                    job.warnings,
                    job.created_at or datetime.now().isoformat(),
                ),
            )
            self.conn.commit()

    def update_status(
        self,
        job_id: str,
        status: str,
        error: str | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        """Update the status of an existing job.

        Args:
            job_id: The job identifier.
            status: New status value.
            error: Error message (if status is failed).
            warnings: List of non-fatal warnings.
        """
        now = datetime.now().isoformat()

        with self.conn.cursor() as cur:
            if status in ("completed", "completed_with_warnings", "failed"):
                cur.execute(
                    """
                    UPDATE geospatial_processing_jobs
                    SET status = %s,
                        error_message = %s,
                        warnings = %s,
                        finished_at = %s
                    WHERE id = %s
                    """,
                    (status, error, warnings, now, job_id),
                )
            elif status == "running":
                cur.execute(
                    """
                    UPDATE geospatial_processing_jobs
                    SET status = %s,
                        started_at = %s
                    WHERE id = %s
                    """,
                    (status, now, job_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE geospatial_processing_jobs
                    SET status = %s
                    WHERE id = %s
                    """,
                    (status, job_id),
                )
            self.conn.commit()

    def exists_by_raw_file_variable(
        self, raw_file_id: int, variable: str, version: str
    ) -> bool:
        """Check if a layer already exists for the given combination.

        Used for idempotency: if True, skip processing.

        Args:
            raw_file_id: The raw file database ID.
            variable: Variable name (e.g. "sm_surface").
            version: Processing version string (e.g. "v1").

        Returns:
            True if a matching layer already exists.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM processed_geospatial_layers
                WHERE raw_file_id = %s
                  AND variable_name = %s
                  AND processing_version = %s
                LIMIT 1
                """,
                (raw_file_id, variable, version),
            )
            return cur.fetchone() is not None

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()


def _parse_date(date_str: str | None) -> str | None:
    """Parse various date formats into YYYY-MM-DD for PostgreSQL."""
    if not date_str:
        return None
    from datetime import datetime
    for fmt in ("%Y%m%dT%H%M%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(str(date_str)[:19], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return str(date_str)[:10]


class ProcessedLayerRepositoryImpl(ProcessedLayerRepository):
    """CRUD for processed_geospatial_layers table."""

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

    def insert(self, layer: ProcessedLayer) -> int:
        """Insert a new processed layer record.

        Args:
            layer: The layer to insert.

        Returns:
            The database-assigned layer ID.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO processed_geospatial_layers (
                    processing_job_id, raw_file_id, source_code,
                    variable_name, display_name, file_path, file_format,
                    crs, bbox, resolution_x, resolution_y,
                    width, height, nodata_value,
                    min_value, max_value, mean_value,
                    valid_pixel_count, nodata_pixel_count,
                    acquisition_date, processing_version,
                    data_source_id, footprint_geometry
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, ST_GeomFromText(%s, 4326)
                )
                RETURNING id
                """,
                (
                    layer.processing_job_id,
                    layer.raw_file_id,
                    layer.source_code,
                    layer.variable_name,
                    layer.variable_name.replace("_", " ").title(),
                    layer.file_path,
                    "GeoTIFF",
                    layer.crs,
                    layer.bbox,
                    layer.resolution_x,
                    layer.resolution_y,
                    layer.width,
                    layer.height,
                    layer.nodata_value,
                    layer.min_value,
                    layer.max_value,
                    layer.mean_value,
                    layer.valid_pixel_count,
                    layer.nodata_pixel_count,
                    _parse_date(layer.acquisition_date),
                    layer.processing_version,
                    layer.data_source_id,
                    layer.footprint_geometry.wkt if layer.footprint_geometry else None,
                ),
            )
            layer_id = cur.fetchone()[0]
            self.conn.commit()

        return layer_id

    def get_by_raw_file_and_variable(
        self, raw_file_id: int, var: str, version: str
    ) -> ProcessedLayer | None:
        """Retrieve an existing layer by raw file, variable, and version.

        Args:
            raw_file_id: The raw file database ID.
            var: Variable name.
            version: Processing version string.

        Returns:
            ProcessedLayer if found, None otherwise.
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM processed_geospatial_layers
                WHERE raw_file_id = %s
                  AND variable_name = %s
                  AND processing_version = %s
                """,
                (raw_file_id, var, version),
            )
            row = cur.fetchone()

        if row is None:
            return None

        return ProcessedLayer(
            id=row["id"],
            raw_file_id=row["raw_file_id"],
            processing_job_id=row["processing_job_id"],
            source_code=row["source_code"],
            variable_name=row["variable_name"],
            file_path=row["file_path"],
            crs=row["crs"] or "",
            bbox=list(row["bbox"]) if row["bbox"] else [],
            resolution_x=float(row["resolution_x"]) if row["resolution_x"] else 0.0,
            resolution_y=float(row["resolution_y"]) if row["resolution_y"] else 0.0,
            width=row["width"],
            height=row["height"],
            nodata_value=float(row["nodata_value"]) if row["nodata_value"] else -9999.0,
            min_value=float(row["min_value"]) if row["min_value"] else 0.0,
            max_value=float(row["max_value"]) if row["max_value"] else 0.0,
            mean_value=float(row["mean_value"]) if row["mean_value"] else 0.0,
            valid_pixel_count=row["valid_pixel_count"],
            nodata_pixel_count=row["nodata_pixel_count"],
            acquisition_date=str(row["acquisition_date"]) if row["acquisition_date"] else "",
            processing_version=row["processing_version"],
            created_at=str(row["created_at"]) if row["created_at"] else None,
            data_source_id=row.get("data_source_id"),
            footprint_geometry=row.get("footprint_geometry"),
        )

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
