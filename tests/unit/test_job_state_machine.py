"""Unit tests for job state machine transitions."""

import pytest

from src.models.job_models import IngestionJob, JobState, RawFile, RawFileStatus


def _create_job(**kwargs) -> IngestionJob:
    """Create a test job with defaults."""
    defaults = {
        "source": "smap",
        "start_date": "2024-01-01",
        "end_date": "2024-01-07",
    }
    defaults.update(kwargs)
    return IngestionJob(**defaults)


class TestInitialState:
    """Test initial job state."""

    def test_new_job_is_pending(self):
        job = _create_job()
        assert job.state == JobState.PENDING
        assert job.ready_for_etl is False

    def test_new_job_has_no_files(self):
        job = _create_job()
        assert job.files == []
        assert job.errors == []


class TestStateTransitions:
    """Test all valid state transitions."""

    def test_pending_to_running(self):
        job = _create_job()
        job.mark_running()
        assert job.state == JobState.RUNNING

    def test_running_to_completed_with_files(self):
        job = _create_job()
        job.mark_running()
        job.files.append(
            RawFile(
                granule_id="g1",
                source_product_id="SPL4SMGP.008",
                remote_url="http://example.com/file.h5",
                acquisition_date="2024-01-01",
                file_name="file.h5",
                size_bytes=1000,
                checksum_sha256="abc123",
                file_path="/data/raw/smap/2024/01/file.h5",
                status=RawFileStatus.DOWNLOADED,
                ready_for_etl=True,
            )
        )
        job.mark_completed()
        assert job.state == JobState.COMPLETED
        assert job.ready_for_etl is True

    def test_running_to_completed_no_files(self):
        """Zero results is valid — completed but not ready for ETL."""
        job = _create_job()
        job.mark_running()
        job.mark_completed()
        assert job.state == JobState.COMPLETED
        assert job.ready_for_etl is False

    def test_running_to_completed_with_warnings(self):
        job = _create_job()
        job.mark_running()
        job.files.append(
            RawFile(
                granule_id="g1",
                source_product_id="SPL4SMGP.008",
                remote_url="http://example.com/file1.h5",
                acquisition_date="2024-01-01",
                file_name="file1.h5",
                size_bytes=1000,
                checksum_sha256="abc123",
                file_path="/data/raw/smap/2024/01/file1.h5",
                status=RawFileStatus.DOWNLOADED,
                ready_for_etl=True,
            )
        )
        job.files.append(
            RawFile(
                granule_id="g2",
                source_product_id="SPL4SMGP.008",
                remote_url="http://example.com/file2.h5",
                acquisition_date="2024-01-02",
                file_name="file2.h5",
                size_bytes=0,
                checksum_sha256="",
                file_path="",
                status=RawFileStatus.ERROR,
                ready_for_etl=False,
                error_message="Download failed",
            )
        )
        job.mark_completed_with_warnings()
        assert job.state == JobState.COMPLETED_WITH_WARNINGS
        assert job.ready_for_etl is True  # At least 1 file OK

    def test_completed_with_warnings_no_good_files(self):
        """If all files failed, ready_for_etl stays False."""
        job = _create_job()
        job.mark_running()
        job.files.append(
            RawFile(
                granule_id="g1",
                source_product_id="SPL4SMGP.008",
                remote_url="http://example.com/file.h5",
                acquisition_date="2024-01-01",
                file_name="file.h5",
                size_bytes=0,
                checksum_sha256="",
                file_path="",
                status=RawFileStatus.ERROR,
                ready_for_etl=False,
                error_message="All retries exhausted",
            )
        )
        job.mark_completed_with_warnings()
        assert job.state == JobState.COMPLETED_WITH_WARNINGS
        assert job.ready_for_etl is False

    def test_running_to_failed(self):
        job = _create_job()
        job.mark_running()
        job.mark_failed("Authentication error")
        assert job.state == JobState.FAILED
        assert job.ready_for_etl is False
        assert "Authentication error" in job.errors

    def test_failed_appends_errors(self):
        job = _create_job()
        job.mark_failed("Error 1")
        job.mark_failed("Error 2")
        assert len(job.errors) == 2


class TestSearchOnlyMode:
    """Test search-only mode behavior."""

    def test_search_only_completed_not_ready_for_etl(self):
        job = _create_job(search_only=True)
        job.mark_running()
        job.files.append(
            RawFile(
                granule_id="g1",
                source_product_id="SPL4SMGP.008",
                remote_url="http://example.com/file.h5",
                acquisition_date="2024-01-01",
                file_name="file.h5",
                size_bytes=1000,
                checksum_sha256="abc123",
                file_path="",
                status=RawFileStatus.ALREADY_DOWNLOADED,
                ready_for_etl=False,
            )
        )
        job.mark_completed()
        assert job.state == JobState.COMPLETED
        assert job.ready_for_etl is False  # search-only never sets ready_for_etl

    def test_search_only_completed_with_warnings_not_ready(self):
        job = _create_job(search_only=True)
        job.mark_running()
        job.files.append(
            RawFile(
                granule_id="g1",
                source_product_id="SPL4SMGP.008",
                remote_url="http://example.com/file.h5",
                acquisition_date="2024-01-01",
                file_name="file.h5",
                size_bytes=1000,
                checksum_sha256="abc123",
                file_path="",
                status=RawFileStatus.ALREADY_DOWNLOADED,
                ready_for_etl=False,
            )
        )
        job.mark_completed_with_warnings()
        assert job.ready_for_etl is False


class TestTouchUpdatesTimestamp:
    """Test that state transitions update updated_at."""

    def test_mark_running_updates_timestamp(self):
        job = _create_job()
        old_ts = job.updated_at
        import time
        time.sleep(0.01)
        job.mark_running()
        assert job.updated_at > old_ts
