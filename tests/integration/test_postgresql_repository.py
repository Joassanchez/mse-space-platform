"""Integration tests for PostgreSQL metadata repository (Slice 2).

These tests require:
- Docker running with PostgreSQL (docker compose up -d)
- psycopg2-binary installed
- PG* env vars (or defaults matching docker-compose.yml)

Run with: pytest -m integration tests/integration/test_postgresql_repository.py
"""

import pytest

from src.models.job_models import IngestionJob, JobState, RawFile, RawFileStatus
from src.storage.metadata_repository_pg import PostgreSQLMetadataRepository


def pg_available() -> bool:
    """Check if PostgreSQL is reachable before running tests."""
    try:
        repo = PostgreSQLMetadataRepository()
        ok = repo.is_available()
        repo.close()
        return ok
    except Exception:
        return False


@pytest.mark.integration
class TestPostgreSQLRepository:
    """Test PostgreSQL metadata repository operations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure PostgreSQL is available and seed SMAP source."""
        if not pg_available():
            pytest.skip("PostgreSQL not available — is docker compose up?")

        self.repo = PostgreSQLMetadataRepository()
        self.source_id = self.repo.ensure_source(
            code="smap",
            name="SMAP Soil Moisture Active Passive",
            provider="NASA_NSIDC",
        )
        # Clean up test data from previous runs
        test_job_ids = ["test_job_001", "test_job_transitions", "test_job_files", "test_idemp_job1"]
        with self.repo.conn.cursor() as cur:
            for jid in test_job_ids:
                cur.execute("DELETE FROM raw_files WHERE ingestion_job_id = %s", (jid,))
                cur.execute("DELETE FROM ingestion_jobs WHERE id = %s", (jid,))
        self.repo.conn.commit()
        yield
        self.repo.close()

    def test_source_created(self):
        """Verify SMAP source exists after setup."""
        sid = self.repo.get_source_id("smap")
        assert sid == self.source_id

    def test_save_and_get_job(self):
        """Save an ingestion job and retrieve it."""
        job = IngestionJob(
            job_id="test_job_001",
            source="smap",
            start_date="2024-01-01",
            end_date="2024-01-07",
            bbox=[-65.0, -35.0, -62.0, -30.0],
            state=JobState.COMPLETED,
            ready_for_etl=True,
        )
        self.repo.save_job(job)

        retrieved = self.repo.get_job("test_job_001")
        assert retrieved is not None
        assert retrieved.job_id == "test_job_001"
        assert retrieved.state == JobState.COMPLETED
        assert retrieved.ready_for_etl is True

    def test_job_state_transitions(self):
        """Test job state transitions in DB."""
        job = IngestionJob(
            job_id="test_job_transitions",
            source="smap",
            start_date="2024-01-01",
            end_date="2024-01-07",
            bbox=[-65.0, -35.0, -62.0, -30.0],
            state=JobState.PENDING,
        )
        self.repo.save_job(job)

        # Transition to running
        job.state = JobState.RUNNING
        self.repo.save_job(job)
        retrieved = self.repo.get_job("test_job_transitions")
        assert retrieved.state == JobState.RUNNING

        # Transition to completed_with_warnings
        job.state = JobState.COMPLETED_WITH_WARNINGS
        job.ready_for_etl = True
        self.repo.save_job(job)
        retrieved = self.repo.get_job("test_job_transitions")
        assert retrieved.state == JobState.COMPLETED_WITH_WARNINGS
        assert retrieved.ready_for_etl is True

    def test_save_and_get_raw_file(self):
        """Save a raw file record and verify retrieval."""
        job = IngestionJob(
            job_id="test_job_files",
            source="smap",
            start_date="2024-01-01",
            end_date="2024-01-07",
            bbox=[-65.0, -35.0, -62.0, -30.0],
            state=JobState.COMPLETED,
            ready_for_etl=True,
        )
        self.repo.save_job(job)

        raw_file = RawFile(
            granule_id="SMAP_L4_SM_gp_20240101T000000",
            source_product_id="SPL4SMGP.008",
            remote_url="https://example.com/file.h5",
            acquisition_date="2024-01-01",
            file_name="SMAP_L4_SM_gp_20240101T000000.h5",
            size_bytes=123456789,
            checksum_sha256="a" * 64,
            file_path="data/raw/smap/2024/01/SMAP_L4_SM_gp_20240101T000000.h5",
            status=RawFileStatus.DOWNLOADED,
            ready_for_etl=True,
        )
        self.repo.save_file(raw_file, job.job_id)

        files = self.repo.get_files_by_job("test_job_files")
        assert len(files) == 1
        assert files[0].file_name == raw_file.file_name
        assert files[0].checksum_sha256 == "a" * 64
        assert files[0].ready_for_etl is True

    def test_check_file_registered(self):
        """Verify idempotency check across jobs."""
        # Job 1: save a file
        job1 = IngestionJob(
            job_id="test_idemp_job1",
            source="smap",
            start_date="2024-01-01",
            end_date="2024-01-07",
            bbox=[-65.0, -35.0, -62.0, -30.0],
            state=JobState.COMPLETED,
            ready_for_etl=True,
        )
        self.repo.save_job(job1)

        rf = RawFile(
            granule_id="GRANULE_001",
            source_product_id="SPL4SMGP.008",
            remote_url="https://example.com/f1.h5",
            acquisition_date="2024-01-01",
            file_name="product_001.h5",
            size_bytes=1000,
            checksum_sha256="b" * 64,
            file_path="data/raw/smap/2024/01/product_001.h5",
            status=RawFileStatus.DOWNLOADED,
            ready_for_etl=True,
        )
        self.repo.save_file(rf, job1.job_id)

        # Job 2: check that file is recognized as already downloaded
        existing = self.repo.check_file_registered(
            file_name="product_001.h5",
            size_bytes=1000,
            job_id="test_idemp_job2",
        )
        assert existing is not None
        assert existing.status == RawFileStatus.ALREADY_DOWNLOADED

        # Different size should NOT match
        not_found = self.repo.check_file_registered(
            file_name="product_001.h5",
            size_bytes=999,
            job_id="test_idemp_job2",
        )
        assert not_found is None

    def test_is_available(self):
        """Health check returns True when PostgreSQL is reachable."""
        assert self.repo.is_available() is True
