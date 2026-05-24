#!/usr/bin/env python3
"""Migrate metadata from JSON files (Slice 1) to PostgreSQL (Slice 2).

Reads all job metadata JSON files from data/metadata/ and inserts
them into the PostgreSQL tables.

Usage:
    python scripts/migrate_metadata_to_pg.py

Requires:
    - PostgreSQL running (docker compose up -d)
    - psycopg2-binary installed
    - PGDATABASE/PGUSER/PGPASSWORD/PGHOST/PGPORT env vars (or defaults)
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.metadata_repository_pg import PostgreSQLMetadataRepository


def migrate_all():
    """Migrate all JSON metadata files to PostgreSQL."""
    metadata_dir = Path("data/metadata")
    if not metadata_dir.exists():
        print("❌ data/metadata/ not found. No JSON files to migrate.")
        return

    repo = PostgreSQLMetadataRepository()
    json_files = sorted(metadata_dir.glob("*.json"))

    if not json_files:
        print("📂 No JSON metadata files found in data/metadata/.")
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
    print(f"✅ Source 'smap' ready (id={source_id})")

    # Ensure dataset exists
    dataset_id = repo.ensure_dataset(
        source_id=source_id,
        short_name="SPL4SMGP",
        version="008",
        format="HDF5",
        variables=["sm_surface", "sm_rootzone"],
    )
    print(f"✅ Dataset 'SPL4SMGP.008' ready (id={dataset_id})")

    total_files = 0
    for json_path in json_files:
        with open(json_path) as f:
            data = json.load(f)

        job_data = data.get("job", {})
        raw_files = data.get("raw_files", [])

        # Build IngestionJob from JSON
        from src.models.job_models import IngestionJob, JobState

        job = IngestionJob(
            job_id=job_data.get("job_id", json_path.stem),
            source_id=source_id,
            dataset_id=dataset_id,
            region_id=job_data.get("region_id"),
            date_from=job_data.get("date_from", ""),
            date_to=job_data.get("date_to", ""),
            bbox=job_data.get("bbox", [0, 0, 0, 0]),
            state=JobState(job_data.get("state", "pending")),
            ready_for_etl=job_data.get("ready_for_etl", False),
            search_only=job_data.get("search_only", False),
            error_message=job_data.get("error_message"),
            started_at=job_data.get("started_at"),
            finished_at=job_data.get("finished_at"),
        )
        repo.save_job(job)

        for rf_data in raw_files:
            from src.models.job_models import RawFile, RawFileStatus

            raw_file = RawFile(
                granule_id=rf_data.get("granule_id", ""),
                source_product_id=rf_data.get("source_product_id", "SPL4SMGP.008"),
                remote_url=rf_data.get("remote_url", ""),
                acquisition_date=rf_data.get("acquisition_date", ""),
                file_name=rf_data.get("file_name", ""),
                size_bytes=rf_data.get("size_bytes", 0),
                checksum_sha256=rf_data.get("checksum_sha256", ""),
                file_path=rf_data.get("file_path", ""),
                status=RawFileStatus(rf_data.get("status", "downloaded")),
                ready_for_etl=rf_data.get("ready_for_etl", False),
                error_message=rf_data.get("error_message"),
            )
            repo.save_file(raw_file, job.job_id)
            total_files += 1

        print(f"  ✅ {json_path.name}: {len(raw_files)} files migrated")

    repo.close()
    print(f"\n🎉 Migration complete: {len(json_files)} jobs, {total_files} files.")


if __name__ == "__main__":
    migrate_all()
