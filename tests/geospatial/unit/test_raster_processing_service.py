"""Unit tests for RasterProcessingService.

Tests nodata handling, CRS/transform construction, ROI clipping, and statistics.
Uses synthetic numpy arrays — no real files or disk access.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.geospatial.domain.errors import ReadError
from src.geospatial.domain.models import GeospatialMetadata
from src.geospatial.application.raster_processing_service import RasterProcessingService


def make_metadata(
    crs: str = "EPSG:6933",
    width: int = 100,
    height: int = 50,
    resolution: tuple[float, float] = (9000.0, 9000.0),
) -> GeospatialMetadata:
    """Create a GeospatialMetadata with a mock Affine transform."""
    try:
        from rasterio.transform import Affine
        transform = Affine.translation(-17367530.0, 7314540.0) * Affine.scale(
            resolution[0], -resolution[1]
        )
    except ImportError:
        transform = MagicMock()

    bounds = (
        -17367530.0,
        7314540.0 - height * resolution[1],
        -17367530.0 + width * resolution[0],
        7314540.0,
    )

    return GeospatialMetadata(
        crs=crs,
        transform=transform,
        bounds=bounds,
        resolution=resolution,
        width=width,
        height=height,
    )


class TestRasterProcessingServiceNodata:
    """Test nodata handling."""

    def setup_method(self):
        self.service = RasterProcessingService()
        self.metadata = make_metadata()

    def test_replace_nodata_with_nan(self):
        """Test that nodata values are replaced with NaN."""
        data = np.array([[1.0, -9999.0], [3.0, -9999.0]], dtype=np.float32)

        result = self.service.process(
            data=data,
            metadata=self.metadata,
            nodata_value=-9999.0,
            config={"roi": {"enabled": False}},
            replace_nodata_with_nan=True,
        )

        assert np.isnan(result.data[0, 1])
        assert np.isnan(result.data[1, 1])
        assert result.data[0, 0] == 1.0
        assert result.data[1, 0] == 3.0

    def test_keep_nodata_unchanged(self):
        """Test that nodata values are kept when replace_nodata_with_nan=False."""
        data = np.array([[1.0, -9999.0], [3.0, -9999.0]], dtype=np.float32)

        result = self.service.process(
            data=data,
            metadata=self.metadata,
            nodata_value=-9999.0,
            config={"roi": {"enabled": False}},
            replace_nodata_with_nan=False,
        )

        assert result.data[0, 1] == -9999.0
        assert result.data[1, 1] == -9999.0

    def test_nodata_replacement_preserves_shape(self):
        """Test that nodata replacement preserves array shape."""
        data = np.random.rand(100, 200).astype(np.float32)
        data[50, 100] = -9999.0

        result = self.service.process(
            data=data,
            metadata=self.metadata,
            nodata_value=-9999.0,
            config={"roi": {"enabled": False}},
            replace_nodata_with_nan=True,
        )

        assert result.data.shape == data.shape

    def test_non_float_array_converted_for_nan(self):
        """Test that integer arrays are converted to float for NaN support."""
        data = np.array([[1, -9999], [3, -9999]], dtype=np.int32)

        result = self.service.process(
            data=data,
            metadata=self.metadata,
            nodata_value=-9999.0,
            config={"roi": {"enabled": False}},
            replace_nodata_with_nan=True,
        )

        assert result.data.dtype in (np.float32, np.float64)
        assert np.isnan(result.data[0, 1])


class TestRasterProcessingServiceStatistics:
    """Test statistics calculation."""

    def setup_method(self):
        self.service = RasterProcessingService()
        self.metadata = make_metadata()

    def test_statistics_with_nodata(self):
        """Test statistics exclude nodata values."""
        data = np.array([[1.0, 2.0, -9999.0], [4.0, 5.0, 6.0]], dtype=np.float64)

        result = self.service.process(
            data=data,
            metadata=self.metadata,
            nodata_value=-9999.0,
            config={"roi": {"enabled": False}},
            replace_nodata_with_nan=True,
        )

        stats = result.statistics
        assert stats["min"] == 1.0
        assert stats["max"] == 6.0
        # Valid values: [1.0, 2.0, 4.0, 5.0, 6.0] = 18/5 = 3.6
        assert stats["mean"] == pytest.approx(3.6)
        assert stats["valid_pixel_count"] == 5
        assert stats["nodata_pixel_count"] == 1

    def test_statistics_all_valid(self):
        """Test statistics when all pixels are valid."""
        data = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)

        result = self.service.process(
            data=data,
            metadata=self.metadata,
            nodata_value=-9999.0,
            config={"roi": {"enabled": False}},
            replace_nodata_with_nan=True,
        )

        stats = result.statistics
        assert stats["valid_pixel_count"] == 4
        assert stats["nodata_pixel_count"] == 0

    def test_statistics_all_nodata(self):
        """Test statistics when all pixels are nodata."""
        data = np.array([[-9999.0, -9999.0], [-9999.0, -9999.0]], dtype=np.float64)

        result = self.service.process(
            data=data,
            metadata=self.metadata,
            nodata_value=-9999.0,
            config={"roi": {"enabled": False}},
            replace_nodata_with_nan=True,
        )

        stats = result.statistics
        assert stats["valid_pixel_count"] == 0
        assert stats["nodata_pixel_count"] == 4
        assert stats["min"] is None
        assert stats["max"] is None
        assert stats["mean"] is None


class TestRasterProcessingServiceROI:
    """Test ROI clipping."""

    def setup_method(self):
        self.service = RasterProcessingService()
        self.metadata = make_metadata(width=100, height=50)

    def test_roi_disabled_returns_full_raster(self):
        """Test that ROI disabled returns the full raster unchanged."""
        data = np.random.rand(50, 100).astype(np.float32)

        result = self.service.process(
            data=data,
            metadata=self.metadata,
            nodata_value=-9999.0,
            config={"roi": {"enabled": False}},
            replace_nodata_with_nan=True,
        )

        assert result.data.shape == data.shape
        assert result.metadata.width == 100
        assert result.metadata.height == 50

    def test_roi_enabled_no_path_warns(self):
        """Test that ROI enabled without path adds a warning."""
        data = np.random.rand(50, 100).astype(np.float32)

        result = self.service.process(
            data=data,
            metadata=self.metadata,
            nodata_value=-9999.0,
            config={"roi": {"enabled": True}},  # No path
            replace_nodata_with_nan=True,
        )

        assert len(result.warnings) == 1
        assert "no path configured" in result.warnings[0].lower()
        # Full raster returned
        assert result.data.shape == data.shape

    @patch("src.geospatial.application.raster_processing_service.HAS_SHAPELY", False)
    def test_roi_clipping_without_shapely_raises_error(self, tmp_path):
        """Test that ROI clipping fails gracefully without shapely."""
        roi_file = tmp_path / "roi.geojson"
        roi_file.write_text('{"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}')

        data = np.random.rand(50, 100).astype(np.float32)

        with pytest.raises(ReadError, match="shapely is required"):
            self.service.process(
                data=data,
                metadata=self.metadata,
                nodata_value=-9999.0,
                config={"roi": {"enabled": True, "path": str(roi_file)}},
                replace_nodata_with_nan=True,
            )

    def test_roi_invalid_file_raises_error(self, tmp_path):
        """Test that ROI with invalid file path raises error."""
        data = np.random.rand(50, 100).astype(np.float32)

        with pytest.raises(ReadError, match="ROI file not found"):
            self.service.process(
                data=data,
                metadata=self.metadata,
                nodata_value=-9999.0,
                config={"roi": {"enabled": True, "path": "/nonexistent/roi.geojson"}},
                replace_nodata_with_nan=True,
            )


class TestRasterProcessingServiceCRS:
    """Test CRS and transform handling."""

    def setup_method(self):
        self.service = RasterProcessingService()

    def test_metadata_preserved_after_processing(self):
        """Test that CRS and transform are preserved in the result."""
        metadata = make_metadata(crs="EPSG:6933")
        data = np.random.rand(50, 100).astype(np.float32)

        result = self.service.process(
            data=data,
            metadata=metadata,
            nodata_value=-9999.0,
            config={"roi": {"enabled": False}},
            replace_nodata_with_nan=True,
        )

        assert result.metadata.crs == "EPSG:6933"
        assert result.metadata.width == 100
        assert result.metadata.height == 50

    def test_3d_array_raises_error(self):
        """Test that 3D arrays are rejected."""
        data = np.random.rand(50, 100, 3).astype(np.float32)
        metadata = make_metadata()

        with pytest.raises(ReadError, match="Expected 2D"):
            self.service.process(
                data=data,
                metadata=metadata,
                nodata_value=-9999.0,
                config={"roi": {"enabled": False}},
                replace_nodata_with_nan=True,
            )

    def test_warnings_list_is_empty_when_no_issues(self):
        """Test that warnings list is empty when processing succeeds cleanly."""
        data = np.random.rand(50, 100).astype(np.float32)
        metadata = make_metadata()

        result = self.service.process(
            data=data,
            metadata=metadata,
            nodata_value=-9999.0,
            config={"roi": {"enabled": False}},
            replace_nodata_with_nan=True,
        )

        assert result.warnings == []
