"""Unit tests for PostgreSQL repositories with mocked psycopg2.

No real PostgreSQL connection — all database interactions are mocked.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.geospatial.domain.models import GeospatialProcessingJob, ProcessedLayer
from src.geospatial.infrastructure.persistence.postgres_repositories import (
    GeospatialProcessingJobRepositoryImpl,
    ProcessedLayerRepositoryImpl,
    RawFileDiscoveryRepositoryImpl,
)


class TestRawFileDiscoveryRepository:
    """Test RawFileDiscoveryRepositoryImpl."""

    def test_find_completed_with_limit(self):
        """Test find_completed passes limit to query."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Mock fetchall to return empty list
        mock_cursor.fetchall.return_value = []

        repo = RawFileDiscoveryRepositoryImpl(connection=mock_conn)
        repo.find_completed(source="SMAP", limit=5)

        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        assert "LIMIT" in call_args[0][0]
        assert call_args[0][1] == ["SMAP", 5]

    def test_find_completed_without_limit(self):
        """Test find_completed without limit omits LIMIT clause."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = []

        repo = RawFileDiscoveryRepositoryImpl(connection=mock_conn)
        repo.find_completed(source="SMAP")

        call_args = mock_cursor.execute.call_args
        assert "LIMIT" not in call_args[0][0]
        assert call_args[0][1] == ["SMAP"]

    def test_find_completed_returns_dicts(self):
        """Test find_completed returns list of dicts."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_row = {"id": 1, "file_path": "/test.h5"}
        mock_cursor.fetchall.return_value = [mock_row]

        repo = RawFileDiscoveryRepositoryImpl(connection=mock_conn)
        result = repo.find_completed(source="SMAP")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == 1

    def test_find_by_id_returns_none_when_not_found(self):
        """Test find_by_id returns None when no row found."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = None

        repo = RawFileDiscoveryRepositoryImpl(connection=mock_conn)
        result = repo.find_by_id(999)

        assert result is None

    def test_find_by_id_returns_dict_when_found(self):
        """Test find_by_id returns dict when row found."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_cursor.fetchone.return_value = {"id": 42}

        repo = RawFileDiscoveryRepositoryImpl(connection=mock_conn)
        result = repo.find_by_id(42)

        assert result is not None
        assert result["id"] == 42

    def test_close_connection(self):
        """Test close closes the connection."""
        mock_conn = MagicMock()
        mock_conn.closed = False

        repo = RawFileDiscoveryRepositoryImpl(connection=mock_conn)
        repo.close()

        mock_conn.close.assert_called_once()


class TestGeospatialProcessingJobRepository:
    """Test GeospatialProcessingJobRepositoryImpl."""

    def setup_method(self):
        self.mock_conn = MagicMock()
        self.mock_conn.closed = False
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=self.mock_cursor)
        self.mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        self.repo = GeospatialProcessingJobRepositoryImpl(connection=self.mock_conn)

    def test_create_inserts_job(self):
        """Test create inserts a job record."""
        job = GeospatialProcessingJob(
            id="test-job-id",
            raw_file_id=1,
            source_code="SMAP",
            status="pending",
        )

        self.repo.create(job)

        self.mock_cursor.execute.assert_called_once()
        self.mock_conn.commit.assert_called_once()

        call_args = self.mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "INSERT INTO geospatial_processing_jobs" in sql
        params = call_args[0][1]
        assert params[0] == "test-job-id"
        assert params[1] == 1
        assert params[2] == "SMAP"

    def test_update_status_to_completed(self):
        """Test update_status sets finished_at for completed status."""
        self.repo.update_status("job-123", "completed")

        call_args = self.mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "finished_at" in sql
        self.mock_conn.commit.assert_called_once()

    def test_update_status_to_running(self):
        """Test update_status sets started_at for running status."""
        self.repo.update_status("job-123", "running")

        call_args = self.mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "started_at" in sql
        assert "finished_at" not in sql

    def test_update_status_to_failed_with_error(self):
        """Test update_status includes error message for failed status."""
        self.repo.update_status("job-123", "failed", error="Disk full")

        call_args = self.mock_cursor.execute.call_args
        params = call_args[0][1]
        assert params[1] == "Disk full"

    def test_update_status_with_warnings(self):
        """Test update_status includes warnings."""
        warnings = ["Low data quality", "Missing metadata"]
        self.repo.update_status("job-123", "completed_with_warnings", warnings=warnings)

        call_args = self.mock_cursor.execute.call_args
        params = call_args[0][1]
        assert params[2] == warnings

    def test_exists_by_raw_file_variable_returns_true(self):
        """Test exists returns True when row found."""
        self.mock_cursor.fetchone.return_value = (1,)

        result = self.repo.exists_by_raw_file_variable(1, "sm_surface", "v1")

        assert result is True
        call_args = self.mock_cursor.execute.call_args
        assert "processed_geospatial_layers" in call_args[0][0]
        params = call_args[0][1]
        assert params == (1, "sm_surface", "v1")

    def test_exists_by_raw_file_variable_returns_false(self):
        """Test exists returns False when no row found."""
        self.mock_cursor.fetchone.return_value = None

        result = self.repo.exists_by_raw_file_variable(1, "sm_surface", "v1")

        assert result is False

    def test_close_connection(self):
        """Test close closes the connection."""
        self.mock_conn.closed = False

        self.repo.close()

        self.mock_conn.close.assert_called_once()


class TestProcessedLayerRepository:
    """Test ProcessedLayerRepositoryImpl."""

    def setup_method(self):
        self.mock_conn = MagicMock()
        self.mock_conn.closed = False
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=self.mock_cursor)
        self.mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        self.repo = ProcessedLayerRepositoryImpl(connection=self.mock_conn)

    def test_insert_returns_layer_id(self):
        """Test insert returns the database-assigned layer ID."""
        self.mock_cursor.fetchone.return_value = (42,)

        layer = ProcessedLayer(
            raw_file_id=1,
            processing_job_id="job-123",
            source_code="SMAP",
            variable_name="sm_surface",
            file_path="/data/processed/smap/sm_surface/2023/12/test.tif",
            crs="EPSG:6933",
            bbox=[-17367530.0, 7269540.0, -17277530.0, 7314540.0],
            resolution_x=9000.0,
            resolution_y=9000.0,
            width=10,
            height=5,
            nodata_value=-9999.0,
            min_value=0.0,
            max_value=0.6,
            mean_value=0.3,
            valid_pixel_count=48,
            nodata_pixel_count=2,
            acquisition_date="2023-12-31",
            processing_version="v1",
        )

        result = self.repo.insert(layer)

        assert result == 42
        self.mock_conn.commit.assert_called_once()

        call_args = self.mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "INSERT INTO processed_geospatial_layers" in sql

    def test_get_by_raw_file_and_variable_returns_layer(self):
        """Test get returns ProcessedLayer when found."""
        mock_row = {
            "id": 42,
            "raw_file_id": 1,
            "processing_job_id": "job-123",
            "source_code": "SMAP",
            "variable_name": "sm_surface",
            "file_path": "/data/processed/test.tif",
            "crs": "EPSG:6933",
            "bbox": [-17367530.0, 7269540.0, -17277530.0, 7314540.0],
            "resolution_x": 9000.0,
            "resolution_y": 9000.0,
            "width": 10,
            "height": 5,
            "nodata_value": -9999.0,
            "min_value": 0.0,
            "max_value": 0.6,
            "mean_value": 0.3,
            "valid_pixel_count": 48,
            "nodata_pixel_count": 2,
            "acquisition_date": "2023-12-31",
            "processing_version": "v1",
            "created_at": "2023-12-31T22:30:00",
        }
        self.mock_cursor.fetchone.return_value = mock_row

        result = self.repo.get_by_raw_file_and_variable(1, "sm_surface", "v1")

        assert result is not None
        assert isinstance(result, ProcessedLayer)
        assert result.id == 42
        assert result.variable_name == "sm_surface"

    def test_get_by_raw_file_and_variable_returns_none(self):
        """Test get returns None when not found."""
        self.mock_cursor.fetchone.return_value = None

        result = self.repo.get_by_raw_file_and_variable(999, "sm_surface", "v1")

        assert result is None

    def test_close_connection(self):
        """Test close closes the connection."""
        self.mock_conn.closed = False

        self.repo.close()

        self.mock_conn.close.assert_called_once()
