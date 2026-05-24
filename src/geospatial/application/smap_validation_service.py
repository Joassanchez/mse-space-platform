"""SMAP validation service implementation.

Implements the GeospatialValidator port for SMAP HDF5 files.
Validates file structure, variable ranges, and metadata completeness.
"""

from pathlib import Path
from typing import Any

import numpy as np

from src.geospatial.domain.errors import ValidationError
from src.geospatial.domain.interfaces import GeospatialValidator
from src.geospatial.domain.models import ExtractedVariable

try:
    import h5py
except ImportError:
    h5py = None  # type: ignore[misc]


class SMAPValidationService(GeospatialValidator):
    """Validates SMAP HDF5 files and extracted variables.

    Implements GeospatialValidator for SMAP SPL4SMGP products.
    """

    def validate_structure(self, file_path: Path, config: dict[str, Any]) -> bool:
        """Validate that an HDF5 file meets minimum expected structure.

        Checks:
        - File exists and is readable
        - File is valid HDF5
        - Required groups exist (e.g. Geophysical_Data)
        - Required variable paths exist
        - Dimensions match config (if specified)

        Args:
            file_path: Path to the HDF5 file.
            config: Source-specific configuration with expected structure.

        Returns:
            True if structure is valid.

        Raises:
            ValidationError: If structural requirements are not met.
        """
        # Check file exists
        if not file_path.exists():
            raise ValidationError(
                f"File does not exist: {file_path}"
            )

        if not file_path.is_file():
            raise ValidationError(
                f"Not a regular file: {file_path}"
            )

        # Check file extension
        suffix = file_path.suffix.lower()
        if suffix not in (".h5", ".hdf5", ""):
            raise ValidationError(
                f"Expected HDF5 file (.h5 or .hdf5), got: {file_path}"
            )

        if h5py is None:
            raise ValidationError("h5py is not installed — cannot validate HDF5 structure")

        try:
            with h5py.File(str(file_path), "r") as f:
                # Check required groups from config
                required_groups = config.get("required_groups", ["Geophysical_Data"])
                for group_path in required_groups:
                    if group_path not in f:
                        raise ValidationError(
                            f"Required group not found: '{group_path}' in {file_path}"
                        )

                # Check required variable paths from config
                variables = config.get("variables", [])
                for var_config in variables:
                    var_path = var_config.get("path", "")
                    if var_path and var_path not in f:
                        raise ValidationError(
                            f"Required variable path not found: '{var_path}' in {file_path}"
                        )

                    # Validate dimensions if expected dimensions are configured
                    expected_dims = var_config.get("expected_dimensions")
                    if expected_dims:
                        try:
                            dataset = f[var_path]
                            actual_shape = tuple(dataset.shape)
                            expected_shape = tuple(expected_dims)
                            if actual_shape != expected_shape:
                                raise ValidationError(
                                    f"Dimension mismatch for '{var_path}': "
                                    f"expected {expected_shape}, got {actual_shape}"
                                )
                        except KeyError:
                            pass  # Already raised above for missing path

                # Check file is readable (basic sanity)
                if len(f.keys()) == 0:
                    raise ValidationError(
                        f"HDF5 file is empty (no root groups): {file_path}"
                    )

        except ValidationError:
            raise
        except h5py.InvalidFileError as e:
            raise ValidationError(
                f"Not a valid HDF5 file: {file_path} — {e}"
            ) from e
        except OSError as e:
            raise ValidationError(
                f"Cannot read HDF5 file: {file_path} — {e}"
            ) from e
        except Exception as e:
            raise ValidationError(
                f"Unexpected error validating structure of {file_path}: {e}"
            ) from e

        return True

    def validate_variable(self, variable: ExtractedVariable, config: dict[str, Any]) -> bool:
        """Validate an extracted variable's data range and metadata.

        Checks:
        - Values within expected_min/expected_max (excluding nodata)
        - Required attributes present
        - Data is not entirely nodata

        Args:
            variable: The extracted variable to validate.
            config: Source-specific configuration with expected ranges.

        Returns:
            True if variable is valid.

        Raises:
            ValidationError: If variable data or metadata is invalid.
        """
        data = variable.data
        nodata = variable.nodata_value

        # Ensure data is a numpy array
        if not isinstance(data, np.ndarray):
            data = np.array(data)

        # Create mask for valid (non-nodata) values
        valid_mask = data != nodata
        valid_data = data[valid_mask]

        # Check if all data is nodata
        if len(valid_data) == 0:
            raise ValidationError(
                f"All values are nodata ({nodata}) — no valid data to validate"
            )

        # Get expected range from config
        expected_min = config.get("expected_min")
        expected_max = config.get("expected_max")

        if expected_min is not None:
            below_min = np.any(valid_data < expected_min)
            if below_min:
                below_count = int(np.sum(valid_data < expected_min))
                raise ValidationError(
                    f"Values below expected minimum: {expected_min}. "
                    f"{below_count} values below range. "
                    f"Actual min: {float(np.min(valid_data))}"
                )

        if expected_max is not None:
            above_max = np.any(valid_data > expected_max)
            if above_max:
                above_count = int(np.sum(valid_data > expected_max))
                raise ValidationError(
                    f"Values above expected maximum: {expected_max}. "
                    f"{above_count} values above range. "
                    f"Actual max: {float(np.max(valid_data))}"
                )

        # Check required attributes from config
        required_attrs = config.get("required_attributes", [])
        for attr_name in required_attrs:
            if attr_name not in variable.attributes:
                raise ValidationError(
                    f"Required attribute missing: '{attr_name}'. "
                    f"Available attributes: {list(variable.attributes.keys())}"
                )

        # Check units are present
        if not variable.units:
            raise ValidationError(
                "Variable has no units defined"
            )

        return True
