"""Unit tests for SMAPValidationService.

Tests structure validation, variable validation, and error handling.
No real HDF5 files — uses mocked h5py and synthetic data.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.geospatial.domain.errors import ValidationError
from src.geospatial.domain.models import ExtractedVariable
from src.geospatial.application.smap_validation_service import SMAPValidationService


class MockHDF5File:
    """Mock HDF5 file that supports 'in' operator properly."""

    def __init__(self, groups: list[str], datasets: dict | None = None, keys: list[str] | None = None):
        self._groups = set(groups)
        self._datasets = datasets or {}
        self._keys = keys or groups

    def __contains__(self, key: str) -> bool:
        return key in self._groups or key in self._datasets

    def __getitem__(self, key: str):
        if key in self._datasets:
            return self._datasets[key]
        raise KeyError(key)

    def keys(self):
        return self._keys

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class TestSMAPValidationServiceStructure:
    """Test validate_structure method."""

    def setup_method(self):
        self.service = SMAPValidationService()
        self.default_config = {
            "required_groups": ["Geophysical_Data"],
            "variables": [
                {
                    "name": "sm_surface",
                    "path": "Geophysical_Data/sm_surface",
                    "expected_dimensions": [1624, 3856],
                }
            ],
        }

    def test_valid_hdf5_structure(self, tmp_path):
        """Test validation passes for a valid HDF5 file."""
        test_file = tmp_path / "valid.h5"
        test_file.touch()

        mock_dataset = MagicMock()
        mock_dataset.shape = (1624, 3856)

        with patch("src.geospatial.application.smap_validation_service.h5py") as mock_h5py:
            mock_h5py.File.return_value = MockHDF5File(
                groups=["Geophysical_Data"],
                datasets={"Geophysical_Data/sm_surface": mock_dataset},
            )

            result = self.service.validate_structure(test_file, self.default_config)
            assert result is True

    def test_missing_file_raises_validation_error(self):
        """Test validation fails when file does not exist."""
        with pytest.raises(ValidationError, match="does not exist"):
            self.service.validate_structure(
                Path("/nonexistent/file.h5"), self.default_config
            )

    def test_not_a_file_raises_validation_error(self, tmp_path):
        """Test validation fails when path is a directory."""
        dir_path = tmp_path / "subdir"
        dir_path.mkdir()

        with pytest.raises(ValidationError, match="Not a regular file"):
            self.service.validate_structure(dir_path, self.default_config)

    def test_wrong_extension_raises_validation_error(self, tmp_path):
        """Test validation fails for non-HDF5 extensions."""
        test_file = tmp_path / "data.txt"
        test_file.touch()

        with pytest.raises(ValidationError, match="Expected HDF5"):
            self.service.validate_structure(test_file, self.default_config)

    @patch("src.geospatial.application.smap_validation_service.h5py")
    def test_missing_required_group_raises_error(self, mock_h5py, tmp_path):
        """Test validation fails when required group is missing."""
        with patch("src.geospatial.application.smap_validation_service.h5py") as mock_h5py:
            mock_h5py.File.return_value = MockHDF5File(groups=["Other_Group"])

            test_file = tmp_path / "test.h5"
            test_file.touch()

            with pytest.raises(ValidationError, match="Required group not found"):
                self.service.validate_structure(test_file, self.default_config)

    @patch("src.geospatial.application.smap_validation_service.h5py")
    def test_missing_variable_path_raises_error(self, mock_h5py, tmp_path):
        """Test validation fails when required variable path is missing."""
        config = {
            "required_groups": ["Geophysical_Data"],
            "variables": [
                {"name": "sm_surface", "path": "Geophysical_Data/missing_var"}
            ],
        }

        with patch("src.geospatial.application.smap_validation_service.h5py") as mock_h5py:
            mock_h5py.File.return_value = MockHDF5File(
                groups=["Geophysical_Data"],  # Group exists
                # But missing_var dataset doesn't
            )

            test_file = tmp_path / "test.h5"
            test_file.touch()

            with pytest.raises(ValidationError, match="Required variable path not found"):
                self.service.validate_structure(test_file, config)

    @patch("src.geospatial.application.smap_validation_service.h5py")
    def test_dimension_mismatch_raises_error(self, mock_h5py, tmp_path):
        """Test validation fails when dimensions don't match expected."""
        config = {
            "required_groups": ["Geophysical_Data"],
            "variables": [
                {
                    "name": "sm_surface",
                    "path": "Geophysical_Data/sm_surface",
                    "expected_dimensions": [100, 200],  # Wrong dimensions
                }
            ],
        }

        mock_dataset = MagicMock()
        mock_dataset.shape = (1624, 3856)  # Actual dimensions

        with patch("src.geospatial.application.smap_validation_service.h5py") as mock_h5py:
            mock_h5py.File.return_value = MockHDF5File(
                groups=["Geophysical_Data"],
                datasets={"Geophysical_Data/sm_surface": mock_dataset},
            )

            test_file = tmp_path / "test.h5"
            test_file.touch()

            with pytest.raises(ValidationError, match="Dimension mismatch"):
                self.service.validate_structure(test_file, config)

    @patch("src.geospatial.application.smap_validation_service.h5py")
    def test_empty_hdf5_raises_error(self, mock_h5py, tmp_path):
        """Test validation fails for empty HDF5 file."""
        with patch("src.geospatial.application.smap_validation_service.h5py") as mock_h5py:
            mock_h5py.File.return_value = MockHDF5File(groups=[], keys=[])

            test_file = tmp_path / "test.h5"
            test_file.touch()

            with pytest.raises(ValidationError, match="empty"):
                self.service.validate_structure(test_file, self.default_config)

    @patch("src.geospatial.application.smap_validation_service.h5py")
    def test_invalid_hdf5_raises_error(self, mock_h5py, tmp_path):
        """Test validation fails for non-HDF5 file."""
        # Create a proper exception class
        class InvalidFileError(Exception):
            pass
        mock_h5py.InvalidFileError = InvalidFileError
        mock_h5py.File.side_effect = InvalidFileError("not HDF5")

        test_file = tmp_path / "test.h5"
        test_file.touch()

        with pytest.raises(ValidationError, match="(?i)not a valid hdf5"):
            self.service.validate_structure(test_file, self.default_config)


class TestSMAPValidationServiceVariable:
    """Test validate_variable method."""

    def setup_method(self):
        self.service = SMAPValidationService()
        self.default_config = {
            "expected_min": 0.0,
            "expected_max": 0.6,
            "required_attributes": ["units"],
        }

    def test_valid_variable_passes(self):
        """Test validation passes for valid variable data."""
        data = np.array([[0.1, 0.2], [0.3, 0.4]])
        variable = ExtractedVariable(
            data=data,
            attributes={"units": "m3 m-3"},
            units="m3 m-3",
            nodata_value=-9999.0,
            acquisition_date="2023-12-31",
        )

        result = self.service.validate_variable(variable, self.default_config)
        assert result is True

    def test_values_out_of_range_raises_error(self):
        """Test validation fails when values exceed expected range."""
        data = np.array([[0.1, 0.8], [0.3, 0.4]])  # 0.8 > 0.6
        variable = ExtractedVariable(
            data=data,
            attributes={"units": "m3 m-3"},
            units="m3 m-3",
            nodata_value=-9999.0,
            acquisition_date="2023-12-31",
        )

        with pytest.raises(ValidationError, match="above expected maximum"):
            self.service.validate_variable(variable, self.default_config)

    def test_values_below_range_raises_error(self):
        """Test validation fails when values are below expected minimum."""
        data = np.array([[-0.1, 0.2], [0.3, 0.4]])  # -0.1 < 0.0
        variable = ExtractedVariable(
            data=data,
            attributes={"units": "m3 m-3"},
            units="m3 m-3",
            nodata_value=-9999.0,
            acquisition_date="2023-12-31",
        )

        with pytest.raises(ValidationError, match="below expected minimum"):
            self.service.validate_variable(variable, self.default_config)

    def test_nodata_values_excluded_from_range_check(self):
        """Test that nodata values are not checked against range."""
        data = np.array([[-9999.0, 0.2], [0.3, -9999.0]])
        variable = ExtractedVariable(
            data=data,
            attributes={"units": "m3 m-3"},
            units="m3 m-3",
            nodata_value=-9999.0,
            acquisition_date="2023-12-31",
        )

        # Should pass because nodata values are excluded
        result = self.service.validate_variable(variable, self.default_config)
        assert result is True

    def test_all_nodata_raises_error(self):
        """Test validation fails when all data is nodata."""
        data = np.array([[-9999.0, -9999.0], [-9999.0, -9999.0]])
        variable = ExtractedVariable(
            data=data,
            attributes={"units": "m3 m-3"},
            units="m3 m-3",
            nodata_value=-9999.0,
            acquisition_date="2023-12-31",
        )

        with pytest.raises(ValidationError, match="All values are nodata"):
            self.service.validate_variable(variable, self.default_config)

    def test_missing_required_attribute_raises_error(self):
        """Test validation fails when required attribute is missing."""
        data = np.array([[0.1, 0.2], [0.3, 0.4]])
        variable = ExtractedVariable(
            data=data,
            attributes={},  # No units attribute
            units="m3 m-3",
            nodata_value=-9999.0,
            acquisition_date="2023-12-31",
        )

        with pytest.raises(ValidationError, match="Required attribute missing"):
            self.service.validate_variable(variable, self.default_config)

    def test_no_units_raises_error(self):
        """Test validation fails when units are empty."""
        data = np.array([[0.1, 0.2], [0.3, 0.4]])
        variable = ExtractedVariable(
            data=data,
            attributes={},
            units="",  # Empty units
            nodata_value=-9999.0,
            acquisition_date="2023-12-31",
        )

        # Use config without required_attributes so we test the units check specifically
        config_no_attrs = {"expected_min": 0.0, "expected_max": 0.6}
        with pytest.raises(ValidationError, match="no units defined"):
            self.service.validate_variable(variable, config_no_attrs)

    def test_no_range_config_skips_range_check(self):
        """Test that range check is skipped when not configured."""
        data = np.array([[0.1, 0.8], [0.3, 0.4]])  # 0.8 would be out of range
        variable = ExtractedVariable(
            data=data,
            attributes={"units": "m3 m-3"},
            units="m3 m-3",
            nodata_value=-9999.0,
            acquisition_date="2023-12-31",
        )

        config_no_range = {"required_attributes": []}
        # Should pass because no range is configured
        result = self.service.validate_variable(variable, config_no_range)
        assert result is True

    def test_boundary_values_pass(self):
        """Test that values exactly at boundaries pass."""
        data = np.array([[0.0, 0.6], [0.3, 0.4]])  # Exactly at min and max
        variable = ExtractedVariable(
            data=data,
            attributes={"units": "m3 m-3"},
            units="m3 m-3",
            nodata_value=-9999.0,
            acquisition_date="2023-12-31",
        )

        result = self.service.validate_variable(variable, self.default_config)
        assert result is True
