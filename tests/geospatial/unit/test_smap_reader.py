"""Unit tests for SMAPHDF5Reader with mocked h5py.

No real HDF5 files or disk access — all h5py interactions are mocked.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.geospatial.domain.errors import ReadError
from src.geospatial.infrastructure.hdf5.smap_reader import SMAPHDF5Reader


class MockHDF5File:
    """Mock HDF5 file that supports proper attribute access and __getitem__."""

    def __init__(
        self,
        attrs: dict | None = None,
        datasets: dict | None = None,
        groups: dict | None = None,
    ):
        self.attrs = attrs or {}
        self._datasets = datasets or {}
        self._groups = groups or {}

    def __contains__(self, key: str) -> bool:
        return key in self._datasets or key in self._groups

    def __getitem__(self, key: str):
        if key in self._datasets:
            return self._datasets[key]
        raise KeyError(key)

    def get(self, key: str, default=None):
        if key in self._groups:
            return self._groups[key]
        return default

    def keys(self):
        return list(self._datasets.keys()) + list(self._groups.keys())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def close(self):
        pass


class TestSMAPHDF5ReaderOpen:
    """Test file opening behavior."""

    def test_open_nonexistent_file_raises_read_error(self):
        reader = SMAPHDF5Reader()
        with pytest.raises(ReadError, match="File not found"):
            reader.open(Path("/nonexistent/file.h5"))

    def test_open_not_a_file_raises_read_error(self, tmp_path):
        reader = SMAPHDF5Reader()
        dir_path = tmp_path / "subdir"
        dir_path.mkdir()
        with pytest.raises(ReadError, match="Not a file"):
            reader.open(dir_path)

    @patch("src.geospatial.infrastructure.hdf5.smap_reader.h5py")
    def test_open_success(self, mock_h5py, tmp_path):
        mock_hdf5_file = MockHDF5File()
        mock_h5py.File.return_value = mock_hdf5_file

        test_file = tmp_path / "test.h5"
        test_file.touch()

        reader = SMAPHDF5Reader()
        reader.open(test_file)

        mock_h5py.File.assert_called_once_with(str(test_file), "r")
        assert reader._file is mock_hdf5_file

    @patch("src.geospatial.infrastructure.hdf5.smap_reader.h5py")
    def test_open_oserror_raises_read_error(self, mock_h5py, tmp_path):
        mock_h5py.File.side_effect = OSError("corrupted file")

        test_file = tmp_path / "test.h5"
        test_file.touch()

        reader = SMAPHDF5Reader()
        with pytest.raises(ReadError, match="Failed to open"):
            reader.open(test_file)


class TestSMAPHDF5ReaderExtractVariable:
    """Test variable extraction with mocked h5py."""

    @patch("src.geospatial.infrastructure.hdf5.smap_reader.h5py")
    def test_extract_variable_without_open_raises_error(self, mock_h5py):
        reader = SMAPHDF5Reader()
        with pytest.raises(ReadError, match="No file is open"):
            reader.extract_variable("Geophysical_Data/sm_surface")

    @patch("src.geospatial.infrastructure.hdf5.smap_reader.h5py")
    def test_extract_variable_success(self, mock_h5py, tmp_path):
        # Setup mock dataset
        mock_dataset = MagicMock()
        mock_dataset.__getitem__.return_value = np.array([[1.0, 2.0], [3.0, 4.0]])
        mock_dataset.attrs = {"units": "m3 m-3"}
        mock_dataset.fillvalue = None  # Explicitly set to None so fallback to -9999.0

        mock_hdf5_file = MockHDF5File(
            attrs={"StartDateTime": "2023-12-31T22:30:00"},
            datasets={"Geophysical_Data/sm_surface": mock_dataset},
        )
        mock_h5py.File.return_value = mock_hdf5_file

        test_file = tmp_path / "test.h5"
        test_file.touch()

        reader = SMAPHDF5Reader()
        reader.open(test_file)

        result = reader.extract_variable("Geophysical_Data/sm_surface")

        assert isinstance(result.data, np.ndarray)
        assert result.data.shape == (2, 2)
        assert result.units == "m3 m-3"
        assert result.nodata_value == -9999.0  # SMAP default
        assert result.acquisition_date == "2023-12-31T22:30:00"

    @patch("src.geospatial.infrastructure.hdf5.smap_reader.h5py")
    def test_extract_variable_missing_raises_read_error(self, mock_h5py, tmp_path):
        mock_hdf5_file = MockHDF5File(attrs={})
        mock_h5py.File.return_value = mock_hdf5_file

        test_file = tmp_path / "test.h5"
        test_file.touch()

        reader = SMAPHDF5Reader()
        reader.open(test_file)

        with pytest.raises(ReadError, match="not found"):
            reader.extract_variable("Geophysical_Data/missing_var")

    @patch("src.geospatial.infrastructure.hdf5.smap_reader.h5py")
    def test_extract_variable_with_fillvalue(self, mock_h5py, tmp_path):
        mock_dataset = MagicMock()
        mock_dataset.__getitem__.return_value = np.array([[1.0, 2.0]])
        mock_dataset.attrs = {"units": "K", "_FillValue": -9999.0}
        mock_dataset.fillvalue = -9999.0

        mock_hdf5_file = MockHDF5File(
            attrs={},
            datasets={"Geophysical_Data/sm_surface": mock_dataset},
        )
        mock_h5py.File.return_value = mock_hdf5_file

        test_file = tmp_path / "test.h5"
        test_file.touch()

        reader = SMAPHDF5Reader()
        reader.open(test_file)

        result = reader.extract_variable("Geophysical_Data/sm_surface")
        assert result.nodata_value == -9999.0

    @patch("src.geospatial.infrastructure.hdf5.smap_reader.h5py")
    def test_extract_variable_acquisition_date_from_filename(self, mock_h5py, tmp_path):
        mock_dataset = MagicMock()
        mock_dataset.__getitem__.return_value = np.array([[1.0]])
        mock_dataset.attrs = {"units": ""}

        mock_hdf5_file = MockHDF5File(
            attrs={},  # No date attributes
            datasets={"Geophysical_Data/sm_surface": mock_dataset},
        )
        mock_h5py.File.return_value = mock_hdf5_file

        # Filename with timestamp
        test_file = tmp_path / "SMAP_L4_SM_gph_20231231T223000_Vv8010_001.h5"
        test_file.touch()

        reader = SMAPHDF5Reader()
        reader.open(test_file)

        result = reader.extract_variable("Geophysical_Data/sm_surface")
        assert "20231231T223000" in result.acquisition_date


class TestSMAPHDF5ReaderGetMetadata:
    """Test metadata derivation with mocked h5py."""

    @patch("src.geospatial.infrastructure.hdf5.smap_reader.h5py")
    def test_get_metadata_without_open_raises_error(self, mock_h5py):
        reader = SMAPHDF5Reader()
        with pytest.raises(ReadError, match="No file is open"):
            reader.get_metadata()

    @patch("src.geospatial.infrastructure.hdf5.smap_reader.h5py")
    def test_get_metadata_fallback_crs(self, mock_h5py, tmp_path):
        """Test CRS fallback to EPSG:6933 when no projection group found."""
        mock_hdf5_file = MockHDF5File(attrs={}, groups={})
        mock_h5py.File.return_value = mock_hdf5_file

        test_file = tmp_path / "test.h5"
        test_file.touch()

        reader = SMAPHDF5Reader()
        reader.open(test_file)

        # Mock _build_transform_from_fallback to avoid rasterio dependency
        mock_transform = MagicMock()
        with patch.object(reader, "_build_transform_from_fallback") as mock_fallback:
            mock_fallback.return_value = (
                mock_transform,
                (-17367530.0, -7314540.0, 17367530.0, 7314540.0),
                (9000.0, 9000.0),
                3856,
                1624,
            )
            metadata = reader.get_metadata()

        assert metadata.crs == "EPSG:6933"
        assert metadata.width == 3856  # Fallback grid width
        assert metadata.height == 1624  # Fallback grid height

    @patch("src.geospatial.infrastructure.hdf5.smap_reader.h5py")
    def test_get_metadata_caches_result(self, mock_h5py, tmp_path):
        """Test that metadata is cached after first call."""
        mock_hdf5_file = MockHDF5File(attrs={}, groups={})
        mock_h5py.File.return_value = mock_hdf5_file

        test_file = tmp_path / "test.h5"
        test_file.touch()

        reader = SMAPHDF5Reader()
        reader.open(test_file)

        mock_transform = MagicMock()
        with patch.object(reader, "_build_transform_from_fallback") as mock_fallback:
            mock_fallback.return_value = (
                mock_transform,
                (-17367530.0, -7314540.0, 17367530.0, 7314540.0),
                (9000.0, 9000.0),
                3856,
                1624,
            )
            # First call
            metadata1 = reader.get_metadata()
            # Second call should return cached result
            metadata2 = reader.get_metadata()

        assert metadata1 is metadata2

    @patch("src.geospatial.infrastructure.hdf5.smap_reader.h5py")
    def test_get_metadata_crs_from_projection_group(self, mock_h5py, tmp_path):
        """Test CRS derivation from EASE2_global_projection group."""
        mock_proj_group = MagicMock()
        mock_proj_group.attrs = {"grid_mapping_name": "lambert_cylindrical_equal_area"}

        mock_hdf5_file = MockHDF5File(
            attrs={},
            groups={"EASE2_global_projection": mock_proj_group},
        )
        mock_h5py.File.return_value = mock_hdf5_file

        test_file = tmp_path / "test.h5"
        test_file.touch()

        reader = SMAPHDF5Reader()
        reader.open(test_file)

        mock_transform = MagicMock()
        with patch.object(reader, "_build_transform_from_fallback") as mock_fallback:
            mock_fallback.return_value = (
                mock_transform,
                (-17367530.0, -7314540.0, 17367530.0, 7314540.0),
                (9000.0, 9000.0),
                3856,
                1624,
            )
            metadata = reader.get_metadata()

        assert metadata.crs == "EPSG:6933"

    @patch("src.geospatial.infrastructure.hdf5.smap_reader.h5py")
    def test_get_metadata_output_shape(self, mock_h5py, tmp_path):
        """Test that metadata has correct shape from fallback."""
        mock_hdf5_file = MockHDF5File(attrs={}, groups={})
        mock_h5py.File.return_value = mock_hdf5_file

        test_file = tmp_path / "test.h5"
        test_file.touch()

        reader = SMAPHDF5Reader()
        reader.open(test_file)

        mock_transform = MagicMock()
        with patch.object(reader, "_build_transform_from_fallback") as mock_fallback:
            mock_fallback.return_value = (
                mock_transform,
                (-17367530.0, -7314540.0, 17367530.0, 7314540.0),
                (9000.0, 9000.0),
                3856,
                1624,
            )
            metadata = reader.get_metadata()

        assert metadata.width > 0
        assert metadata.height > 0
        assert metadata.resolution[0] > 0
        assert metadata.resolution[1] > 0
        assert len(metadata.bounds) == 4
        assert metadata.transform is not None


class TestSMAPHDF5ReaderContextManager:
    """Test context manager support."""

    @patch("src.geospatial.infrastructure.hdf5.smap_reader.h5py")
    def test_context_manager_closes_file(self, mock_h5py, tmp_path):
        mock_file = MagicMock()
        mock_h5py.File.return_value = mock_file

        test_file = tmp_path / "test.h5"
        test_file.touch()

        with SMAPHDF5Reader() as reader:
            reader.open(test_file)
            assert reader._file is not None

        mock_file.close.assert_called_once()

    @patch("src.geospatial.infrastructure.hdf5.smap_reader.h5py")
    def test_close_resets_state(self, mock_h5py, tmp_path):
        mock_file = MagicMock()
        mock_h5py.File.return_value = mock_file

        test_file = tmp_path / "test.h5"
        test_file.touch()

        reader = SMAPHDF5Reader()
        reader.open(test_file)
        reader.close()

        assert reader._file is None
        assert reader._file_path is None
        assert reader._metadata_cache is None
