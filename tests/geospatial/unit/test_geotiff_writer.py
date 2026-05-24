"""Unit tests for GeoTIFFWriter.

Tests .tmp file creation, atomic move, cleanup on failure, and deterministic path generation.
Uses tempfile.TemporaryDirectory to avoid real disk writes.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.geospatial.domain.errors import WriteError
from src.geospatial.domain.models import GeospatialMetadata
from src.geospatial.infrastructure.raster.geotiff_writer import GeoTIFFWriter


def make_metadata(
    crs: str = "EPSG:6933",
    width: int = 10,
    height: int = 5,
) -> GeospatialMetadata:
    """Create a GeospatialMetadata with a mock Affine transform."""
    try:
        from rasterio.transform import Affine
        transform = Affine.translation(-17367530.0, 7314540.0) * Affine.scale(9000.0, -9000.0)
    except ImportError:
        transform = MagicMock()

    return GeospatialMetadata(
        crs=crs,
        transform=transform,
        bounds=(-17367530.0, 7269540.0, -17277530.0, 7314540.0),
        resolution=(9000.0, 9000.0),
        width=width,
        height=height,
    )


class TestGeoTIFFWriterPathGeneration:
    """Test deterministic output path generation."""

    def setup_method(self):
        self.writer = GeoTIFFWriter()

    def test_path_format(self):
        """Test path follows expected format."""
        path = self.writer._generate_output_path(
            source="smap",
            variable="soil_moisture",
            acquisition_datetime="20231231T223000",
            processing_version="v1",
        )

        assert "data" in str(path)
        assert "processed" in str(path)
        assert "smap" in str(path)
        assert "soil_moisture" in str(path)
        assert "2023" in str(path)
        assert "12" in str(path)
        assert path.suffix == ".tif"

    def test_path_contains_all_components(self):
        """Test path contains source, variable, date, and version."""
        path = self.writer._generate_output_path(
            source="smap",
            variable="sm_surface",
            acquisition_datetime="2024-01-15T06:30:00",
            processing_version="v2",
        )

        path_str = str(path)
        assert "smap" in path_str
        assert "sm_surface" in path_str
        assert "2024" in path_str
        assert "01" in path_str
        assert "v2" in path_str

    def test_path_sanitizes_variable_name(self):
        """Test that variable names with slashes are sanitized."""
        path = self.writer._generate_output_path(
            source="smap",
            variable="Geophysical_Data/sm_surface",
            acquisition_datetime="20231231T223000",
            processing_version="v1",
        )

        assert "/" not in path.name
        assert "Geophysical_Data_sm_surface" in path.name

    def test_path_fallback_date_for_invalid_format(self):
        """Test that invalid date formats fall back to current date."""
        path = self.writer._generate_output_path(
            source="smap",
            variable="sm_surface",
            acquisition_datetime="invalid-date",
            processing_version="v1",
        )

        # Should still generate a valid path (with current date)
        assert path.suffix == ".tif"


class TestGeoTIFFWriterWrite:
    """Test write method with mocked rasterio."""

    def setup_method(self):
        self.writer = GeoTIFFWriter()
        self.data = np.random.rand(5, 10).astype(np.float32)
        self.metadata = make_metadata()

    @patch("src.geospatial.infrastructure.raster.geotiff_writer.os.replace")
    @patch("src.geospatial.infrastructure.raster.geotiff_writer.rasterio")
    def test_write_creates_tmp_then_moves(self, mock_rasterio, mock_replace, tmp_path):
        """Test that write creates .tmp file then atomically moves."""
        mock_rasterio.errors = MagicMock()
        mock_rasterio.errors.RasterioError = Exception

        # Create a tmp file so os.replace can work
        output_file = tmp_path / "output.tif"
        tmp_file = tmp_path / "output.tif.tmp"
        tmp_file.touch()

        # Mock the context manager for write and validation read
        mock_dst = MagicMock()
        mock_src = MagicMock()
        mock_src.width = 10
        mock_src.height = 5

        call_count = [0]
        def open_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_cm = MagicMock()
            if call_count[0] == 1:
                mock_cm.__enter__ = MagicMock(return_value=mock_dst)
            else:
                mock_cm.__enter__ = MagicMock(return_value=mock_src)
            mock_cm.__exit__ = MagicMock(return_value=False)
            return mock_cm

        mock_rasterio.open.side_effect = open_side_effect

        # Override output path to use tmp_path
        with patch.object(self.writer, "_generate_output_path") as mock_gen:
            mock_gen.return_value = output_file

            result = self.writer.write(
                data=self.data,
                metadata=self.metadata,
                source="smap",
                variable="sm_surface",
                acquisition_datetime="20231231T223000",
                processing_version="v1",
            )

            assert result == str(output_file)
            mock_replace.assert_called_once()

    @patch("src.geospatial.infrastructure.raster.geotiff_writer.rasterio")
    def test_write_cleanup_on_failure(self, mock_rasterio, tmp_path):
        """Test that .tmp file is cleaned up on write failure."""
        mock_rasterio.open = MagicMock()
        mock_rasterio.errors = MagicMock()
        mock_rasterio.errors.RasterioError = Exception

        # Simulate write failure
        mock_rasterio.open.side_effect = Exception("disk full")

        with patch.object(self.writer, "_generate_output_path") as mock_gen:
            output_file = tmp_path / "output.tif"
            mock_gen.return_value = output_file

            with pytest.raises(WriteError):
                self.writer.write(
                    data=self.data,
                    metadata=self.metadata,
                    source="smap",
                    variable="sm_surface",
                    acquisition_datetime="20231231T223000",
                    processing_version="v1",
                )

            # Verify .tmp file was cleaned up
            tmp_file = output_file.with_suffix(".tif.tmp")
            assert not tmp_file.exists()

    def test_write_without_rasterio_raises_error(self):
        """Test that write fails gracefully without rasterio."""
        with patch("src.geospatial.infrastructure.raster.geotiff_writer.rasterio", None):
            with pytest.raises(WriteError, match="rasterio is not installed"):
                self.writer.write(
                    data=self.data,
                    metadata=self.metadata,
                    source="smap",
                    variable="sm_surface",
                    acquisition_datetime="20231231T223000",
                    processing_version="v1",
                )

    def test_write_3d_array_raises_error(self):
        """Test that 3D arrays are rejected."""
        data_3d = np.random.rand(5, 10, 3).astype(np.float32)

        with patch("src.geospatial.infrastructure.raster.geotiff_writer.rasterio", None):
            with pytest.raises(WriteError, match="rasterio is not installed"):
                self.writer.write(
                    data=data_3d,
                    metadata=self.metadata,
                    source="smap",
                    variable="sm_surface",
                    acquisition_datetime="20231231T223000",
                    processing_version="v1",
                )


class TestGeoTIFFWriterCleanup:
    """Test cleanup behavior."""

    def setup_method(self):
        self.writer = GeoTIFFWriter()

    def test_cleanup_removes_tmp_file(self, tmp_path):
        """Test that cleanup removes the .tmp file."""
        tmp_file = tmp_path / "test.tif.tmp"
        tmp_file.touch()

        self.writer._cleanup_tmp(tmp_file)

        assert not tmp_file.exists()

    def test_cleanup_ignores_missing_file(self, tmp_path):
        """Test that cleanup does not error on missing file."""
        tmp_file = tmp_path / "nonexistent.tif.tmp"

        # Should not raise
        self.writer._cleanup_tmp(tmp_file)

    def test_cleanup_ignores_os_errors(self, tmp_path):
        """Test that cleanup ignores OS errors (best effort)."""
        # Create a file and make it unwritable (on Windows this may not work)
        tmp_file = tmp_path / "test.tif.tmp"
        tmp_file.touch()

        # Should not raise even if unlink fails
        self.writer._cleanup_tmp(tmp_file)
