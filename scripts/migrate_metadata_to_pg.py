#!/usr/bin/env python3
"""Migrate metadata from JSON files (Slice 1) to PostgreSQL (Slice 2).

Reads all job metadata JSON files from data/metadata/ and inserts
them into the PostgreSQL tables using direct SQL.

Usage:
    python scripts/migrate_metadata_to_pg.py

Requires:
    - PostgreSQL running (docker compose up -d)
    - psycopg2-binary installed
    - PGDATABASE/PGUSER/PGPASSWORD/PGHOST/PGPORT env vars (or defaults)
"""

import json
from datetime import datetime
from pathlib import Path

# Add project root to path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.metadata_repository_pg import PostgreSQLMetadataRepository


def migrate_all():
    """Migrate all JSON metadata files to PostgreSQL."""
    metadata_dir = Path("data/metadata")
    if not metadata_dir.exists():
        print("[SKIP] data/metadata/ not found. No JSON files to migrate.")
        return

    repo = PostgreSQLMetadataRepository()
    json_files = sorted(metadata_dir.glob("*.json"))

    if not json_files:
        print("[SKIP] No JSON metadata files found in data/metadata/.")
        return

    # Ensure SMAP source exists
    source_id = repo.ensure_source(
        code="smap",
        name="SMAP Soil Moisture Active Passive",
        provider="NASA_NSIDC",
        source_type="satellite",
        access_method="earthaccess",
        requires_auth=True,
        config={
            "short_name": "SPL4SMGP",
            "version": "008",
            "format": "HDF5",
            "variables": ["sm_surface", "sm_rootzone"],
        },
    )
    print(f"[OK] Source 'smap' ready (id={source_id})")

    # Ensure dataset exists
    dataset_id = repo.ensure_dataset(
        source_id=source_id,
        short_name="SPL4SMGP",
        version="008",
        format="HDF5",
        variables=["sm_surface", "sm_rootzone"],
    )
    print(f"[OK] Dataset 'SPL4SMGP.008' ready (id={dataset_id})")

    total_files = 0
    conn = repo.conn

    for json_path in json_files:
        with open(json_path) as f:
            data = json.load(f)

        now = datetime.now()

        # Insert ingestion job directly (IngestionJob model uses source str, not source_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingestion_jobs (
                    id, source_id, dataset_id, date_from, date_to,
                    bbox, status, ready_for_etl, search_only, error_message,
                    created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    ready_for_etl = EXCLUDED.ready_for_etl
                """,
                (
                    data.get("job_id", json_path.stem),
                    source_id,
                    dataset_id,
                    data.get("start_date"),
                    data.get("end_date"),
                    data.get("bbox", [0, 0, 0, 0]),
                    data.get("state", "pending"),
                    data.get("ready_for_etl", False),
                    data.get("search_only", False),
                    data.get("error_message"),
                    now,
                ),
            )

        # Insert raw files
        job_files = 0
        for rf_data in data.get("files", []):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO raw_files (
                        ingestion_job_id, source_id, dataset_id, granule_id,
                        source_product_id, remote_url, acquisition_date,
                        file_path, file_name, file_format, size_bytes,
                        checksum_sha256, status, error_message, ready_for_etl
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        data.get("job_id", json_path.stem),
                        source_id,
                        dataset_id,
                        rf_data.get("granule_id", ""),
                        rf_data.get("source_product_id", "SPL4SMGP.008"),
                        rf_data.get("remote_url", ""),
                        rf_data.get("acquisition_date"),
                        rf_data.get("file_path", ""),
                        rf_data.get("file_name", ""),
                        "HDF5",
                        rf_data.get("size_bytes", 0),
                        rf_data.get("checksum_sha256", ""),
                        rf_data.get("status", "downloaded"),
                        rf_data.get("error_message"),
                        rf_data.get("ready_for_etl", False),
                    ),
                )
            job_files += 1
            total_files += 1

        conn.commit()
        print(f"  [OK] {json_path.name}: {job_files} file(s) migrated")

    repo.close()
    print(f"\n[DONE] Migration complete: {len(json_files)} jobs, {total_files} files.")


if __name__ == "__main__":
    migrate_all()
