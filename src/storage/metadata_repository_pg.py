"""PostgreSQL metadata repository for Slice 2.

Provides persistent storage for ingestion jobs and raw file metadata
using PostgreSQL (plain, no PostGIS). Replaces the JSON-based
MetadataRepository from Slice 1.
"""

import json
import os
from datetime import datetime
from typing import Optional

from src.models.job_models import IngestionJob, JobState, RawFile, RawFileStatus

try:
    import psycopg2
    import psycopg2.extras

    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


def _get_connection():
    """Get a PostgreSQL connection from environment config.

    Returns:
        psycopg2 connection.

    Raises:
        RuntimeError: If psycopg2 is not installed.
        psycopg2.OperationalError: If connection fails.
    """
    if not HAS_PSYCOPG2:
        raise RuntimeError(
            "psycopg2 is required for PostgreSQL metadata repository. "
            "Install with: pip install psycopg2-binary"
        )
    return psycopg2.connect(
        dbname=os.getenv("PGDATABASE", "mse_platform"),
        user=os.getenv("PGUSER", "mse_user"),
        password=os.getenv("PGPASSWORD", "mse_pass"),
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
    )


class PostgreSQLMetadataRepository:
    """PostgreSQL-backed metadata repository for ingestion metadata.

    Mirrors the interface of MetadataRepository (JSON-based from Slice 1)
    so both can coexist during migration.
    """

    def __init__(self, connection=None):
        """Initialize repository.

        Args:
            connection: Optional existing psycopg2 connection.
                        If None, creates a new one from env config.
        """
        self._conn = connection

    @property
    def conn(self):
        if self._conn is None or self._conn.closed:
            self._conn = _get_connection()
        return self._conn

    # ---- Data Sources ----

    def ensure_source(
        self,
        code: str,
        name: str,
        provider: str,
        source_type: str = "satellite",
        access_method: str = "earthaccess",
        requires_auth: bool = True,
        config: Optional[dict] = None,
    ) -> int:
        """Create or retrieve a data source by code.

        Returns:
            The source id.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO data_sources (code, name, provider, source_type, access_method, requires_auth, config)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                """,
                (code, name, provider, source_type, access_method, requires_auth, json.dumps(config) if config else None),
            )
            self.conn.commit()
            return cur.fetchone()[0]

    def get_source_id(self, code: str) -> Optional[int]:
        """Get source id by code."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT id FROM data_sources WHERE code = %s", (code,))
            row = cur.fetchone()
            return row[0] if row else None

    # ---- Datasets ----

    def ensure_dataset(
        self,
        source_id: int,
        short_name: str,
        version: str,
        format: str = "HDF5",
        variables: Optional[list[str]] = None,
    ) -> int:
        """Create or retrieve a dataset."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO datasets (source_id, short_name, version, format, variables)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (source_id, short_name, version) DO UPDATE
                    SET format = EXCLUDED.format
                RETURNING id
                """,
                (source_id, short_name, version, format, variables),
            )
            self.conn.commit()
            return cur.fetchone()[0]

    # ---- Ingestion Jobs ----

    def _resolve_source_id(self, source_code: str) -> int | None:
        """Resolve a source code to its database ID, creating it if needed."""
        existing = self.get_source_id(source_code)
        if existing is not None:
            return existing
        # Auto-create source with minimal info for tests/dev
        return self.ensure_source(
            code=source_code,
            name=source_code.upper(),
            provider="auto",
        )

    def save_job(self, job: IngestionJob) -> None:
        """Save or update an ingestion job.

        Maps the IngestionJob model fields to the ingestion_jobs table schema.
        Resolves ``source`` (string code) to ``source_id`` (FK) automatically.
        """
        source_id = self._resolve_source_id(job.source)
        error_msg = job.errors[0] if job.errors else None

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingestion_jobs (
                    id, source_id, date_from, date_to,
                    bbox, status, ready_for_etl, search_only, error_message
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    ready_for_etl = EXCLUDED.ready_for_etl,
                    error_message = EXCLUDED.error_message
                """,
                (
                    job.job_id,
                    source_id,
                    job.start_date,
                    job.end_date,
                    job.bbox,
                    job.state.value if hasattr(job.state, 'value') else job.state,
                    job.ready_for_etl,
                    job.search_only,
                    error_msg,
                ),
            )
            self.conn.commit()

    def get_job(self, job_id: str) -> Optional[IngestionJob]:
        """Retrieve an ingestion job by id.

        Returns:
            IngestionJob with fields mapped from the DB schema to the model.
            ``source`` is resolved from ``data_sources`` via the stored FK.
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT j.*, ds.code AS source_code
                FROM ingestion_jobs j
                LEFT JOIN data_sources ds ON j.source_id = ds.id
                WHERE j.id = %s
                """,
                (job_id,),
            )
            row = cur.fetchone()
            if not row:
                return None

            errors: list[str] = []
            if row.get("error_message"):
                errors.append(row["error_message"])

            return IngestionJob(
                job_id=row["id"],
                source=row.get("source_code", "unknown"),
                start_date=str(row["date_from"]),
                end_date=str(row["date_to"]),
                bbox=list(row["bbox"]) if row["bbox"] else [],
                state=JobState(row["status"]),
                ready_for_etl=row["ready_for_etl"],
                search_only=row["search_only"],
                errors=errors,
            )

    # ---- Raw Files ----

    def save_file(self, raw_file: RawFile, job_id: str) -> None:
        """Register a raw file in PostgreSQL.

        Resolves ``source_id`` by looking up the ingestion_job's source FK.
        The columns not present in the RawFile model (dataset_id, metadata_json)
        are set to NULL (nullable in the DB schema).
        """
        with self.conn.cursor() as cur:
            # Resolve source_id from the job
            cur.execute("SELECT source_id FROM ingestion_jobs WHERE id = %s", (job_id,))
            job_row = cur.fetchone()
            source_id = job_row[0] if job_row else None

            cur.execute(
                """
                INSERT INTO raw_files (
                    ingestion_job_id, source_id, granule_id,
                    source_product_id, remote_url, acquisition_date,
                    file_path, file_name, file_format, size_bytes,
                    checksum_sha256, status, error_message, ready_for_etl
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    job_id,
                    source_id,
                    raw_file.granule_id,
                    raw_file.source_product_id,
                    raw_file.remote_url,
                    raw_file.acquisition_date,
                    raw_file.file_path,
                    raw_file.file_name,
                    "HDF5",
                    raw_file.size_bytes,
                    raw_file.checksum_sha256,
                    raw_file.status.value if hasattr(raw_file.status, 'value') else raw_file.status,
                    raw_file.error_message,
                    raw_file.ready_for_etl,
                ),
            )
            self.conn.commit()

    def check_file_registered(
        self, file_name: str, size_bytes: int, job_id: str
    ) -> Optional[RawFile]:
        """Check if a file is already registered by composite key.

        Args:
            file_name: Name of the file.
            size_bytes: Size in bytes.
            job_id: Current job id (to allow re-registration in same job).

        Returns:
            RawFile if found, None otherwise.
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM raw_files
                WHERE file_name = %s
                  AND size_bytes = %s
                  AND ingestion_job_id != %s
                  AND ready_for_etl = TRUE
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (file_name, size_bytes, job_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return RawFile(
                granule_id=row["granule_id"],
                source_product_id=row["source_product_id"],
                remote_url=row["remote_url"],
                acquisition_date=str(row["acquisition_date"]) if row["acquisition_date"] else "",
                file_name=row["file_name"],
                size_bytes=row["size_bytes"],
                checksum_sha256=row["checksum_sha256"],
                file_path=row["file_path"],
                status=RawFileStatus.ALREADY_DOWNLOADED,
                ready_for_etl=True,
            )

    def get_files_by_job(self, job_id: str) -> list[RawFile]:
        """Get all raw files for a given job."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM raw_files WHERE ingestion_job_id = %s ORDER BY created_at",
                (job_id,),
            )
            rows = cur.fetchall()
            return [
                RawFile(
                    granule_id=r["granule_id"],
                    source_product_id=r["source_product_id"],
                    remote_url=r["remote_url"],
                    acquisition_date=str(r["acquisition_date"]) if r["acquisition_date"] else "",
                    file_name=r["file_name"],
                    size_bytes=r["size_bytes"],
                    checksum_sha256=r["checksum_sha256"],
                    file_path=r["file_path"],
                    status=RawFileStatus(r["status"]),
                    ready_for_etl=r["ready_for_etl"],
                    error_message=r["error_message"],
                )
                for r in rows
            ]

    # ---- Health ----

    def is_available(self) -> bool:
        """Check if PostgreSQL is reachable.

        Returns:
            True if connection succeeds, False otherwise.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
                return True
        except Exception:
            return False

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
