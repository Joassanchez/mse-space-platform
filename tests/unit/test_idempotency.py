"""Unit tests for idempotency logic.

Tests three scenarios:
1. File exists + checksum match → skip download
2. File exists + no metadata entry (orphan) → register without download
3. File missing → proceed with download
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models.job_models import IngestionJob, RawFile, RawFileStatus
from src.storage.metadata_repository import MetadataRepository


class TestIdempotency:
    """Test idempotency check scenarios."""

    @pytest.fixture
    def metadata_repo(self, tmp_path):
        """Create a MetadataRepository with a temp directory."""
        return MetadataRepository(metadata_dir=tmp_path)

    @pytest.fixture
    def sample_job(self):
        """Create a sample ingestion job."""
        return IngestionJob(
            source="smap",
            start_date="2024-01-01",
            end_date="2024-01-07",
        )

    def test_file_not_registered(self, metadata_repo, sample_job):
        """File not in any metadata → should proceed with download."""
        result = metadata_repo.check_file_registered(
            file_name="new_file.h5",
            size_bytes=1000,
            job_id=sample_job.job_id,
        )
        assert result is None

    def test_file_registered_in_current_job(self, metadata_repo, sample_job):
        """File already registered in current job → return existing record."""
        existing = RawFile(
            granule_id="g1",
            source_product_id="SPL4SMGP.008",
            remote_url="http://example.com/file.h5",
            acquisition_date="2024-01-01",
            file_name="existing_file.h5",
            size_bytes=2000,
            checksum_sha256="abc123def456",
            file_path="/data/raw/smap/2024/01/existing_file.h5",
            status=RawFileStatus.DOWNLOADED,
            ready_for_etl=True,
        )
        sample_job.files.append(existing)
        metadata_repo.save_job(sample_job)

        result = metadata_repo.check_file_registered(
            file_name="existing_file.h5",
            size_bytes=2000,
            job_id=sample_job.job_id,
        )
        assert result is not None
        assert result.checksum_sha256 == "abc123def456"
        assert result.status == RawFileStatus.DOWNLOADED

    def test_file_registered_in_different_job(self, metadata_repo, sample_job):
        """File registered in a different job → still found (composite key)."""
        other_job = IngestionJob(
            source="smap",
            start_date="2023-12-01",
            end_date="2023-12-07",
        )
        existing = RawFile(
            granule_id="g1",
            source_product_id="SPL4SMGP.008",
            remote_url="http://example.com/file.h5",
            acquisition_date="2023-12-01",
            file_name="cross_job_file.h5",
            size_bytes=3000,
            checksum_sha256="cross_job_checksum",
            file_path="/data/raw/smap/2023/12/cross_job_file.h5",
            status=RawFileStatus.DOWNLOADED,
            ready_for_etl=True,
        )
        other_job.files.append(existing)
        metadata_repo.save_job(other_job)

        result = metadata_repo.check_file_registered(
            file_name="cross_job_file.h5",
            size_bytes=3000,
            job_id=sample_job.job_id,
        )
        assert result is not None
        assert result.checksum_sha256 == "cross_job_checksum"

    def test_file_name_match_but_size_mismatch(self, metadata_repo, sample_job):
        """Same file name but different size → not a match."""
        existing = RawFile(
            granule_id="g1",
            source_product_id="SPL4SMGP.008",
            remote_url="http://example.com/file.h5",
            acquisition_date="2024-01-01",
            file_name="same_name.h5",
            size_bytes=2000,
            checksum_sha256="abc123",
            file_path="/data/raw/smap/2024/01/same_name.h5",
            status=RawFileStatus.DOWNLOADED,
            ready_for_etl=True,
        )
        sample_job.files.append(existing)
        metadata_repo.save_job(sample_job)

        result = metadata_repo.check_file_registered(
            file_name="same_name.h5",
            size_bytes=9999,  # Different size
            job_id=sample_job.job_id,
        )
        assert result is None  # Not a match — different size

    def test_orphan_file_scenario(self, metadata_repo, sample_job):
        """Orphan file: exists on disk but not in any metadata.

        The check returns None (not registered), so the caller should
        detect the file on disk and register it without re-downloading.
        """
        # No metadata entry for this file
        result = metadata_repo.check_file_registered(
            file_name="orphan_file.h5",
            size_bytes=5000,
            job_id=sample_job.job_id,
        )
        assert result is None  # Not in metadata — caller should check disk
