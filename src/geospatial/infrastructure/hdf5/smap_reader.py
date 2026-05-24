"""SMAP HDF5 reader implementation.

Implements the GeospatialReader port for SMAP HDF5 files using h5py.
Handles EASE-Grid 2.0 CRS derivation (EPSG:6933) and spatial metadata extraction.
"""

from pathlib import Path
from typing import Any

import h5py
import numpy as np

from src.geospatial.domain.errors import ReadError
from src.geospatial.domain.interfaces import GeospatialReader
from src.geospatial.domain.models import ExtractedVariable, GeospatialMetadata

try:
    from rasterio.transform import Affine
except ImportError:
    Affine = None  # type: ignore[misc]


# EASE-Grid 2.0 Global projection parameters (EPSG:6933)
# These are used as fallback/confirmation values when deriving from HDF5 metadata.
_EASE2_CRS_WKT = (
    'PROJCS["WGS 84 / NSIDC EASE-Grid 2.0 Global",'
    'GEOGCS["WGS 84",'
    'DATUM["WGS_1984",'
    'SPHEROID["WGS 84",6378137,298.257223563,'
    'AUTHORITY["EPSG","7030"]],'
    'AUTHORITY["EPSG","6326"]],'
    'PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],'
    'UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],'
    'AUTHORITY["EPSG","4326"]],'
    'PROJECTION["Lambert_Cylindrical_Equal_Area"],'
    'PARAMETER["latitude_of_origin",0],'
    'PARAMETER["central_meridian",0],'
    'PARAMETER["false_easting",0],'
    'PARAMETER["false_northing",0],'
    'UNIT["metre",1,AUTHORITY["EPSG","9001"]],'
    'AXIS["Easting",EAST],'
    'AXIS["Northing",NORTH],'
    'AUTHORITY["EPSG","6933"]]'
)

_EPSG_6933 = "EPSG:6933"


class SMAPHDF5Reader(GeospatialReader):
    """Reads SMAP HDF5 files and extracts variables with geospatial metadata.

    Implements GeospatialReader for SMAP SPL4SMGP products.
    Handles EASE-Grid 2.0 CRS derivation from HDF5 metadata.
    """

    def __init__(self) -> None:
        self._file: h5py.File | None = None
        self._file_path: Path | None = None
        self._metadata_cache: GeospatialMetadata | None = None

    def open(self, file_path: Path) -> None:
        """Open an HDF5 file and validate it is readable.

        Args:
            file_path: Path to the SMAP HDF5 file.

        Raises:
            ReadError: If the file does not exist, is not HDF5, or cannot be opened.
        """
        if not file_path.exists():
            raise ReadError(f"File not found: {file_path}")

        if not file_path.is_file():
            raise ReadError(f"Not a file: {file_path}")

        try:
            self._file = h5py.File(str(file_path), "r")
            self._file_path = file_path
            self._metadata_cache = None  # Reset cache on new file
        except OSError as e:
            raise ReadError(
                f"Failed to open HDF5 file {file_path}: {e}"
            ) from e
        except Exception as e:
            raise ReadError(
                f"Unexpected error opening {file_path}: {e}"
            ) from e

    def extract_variable(self, variable_name: str) -> ExtractedVariable:
        """Extract a specific variable from the opened HDF5 file.

        Args:
            variable_name: HDF5 dataset path (e.g. "Geophysical_Data/sm_surface").

        Returns:
            ExtractedVariable with data, attributes, units, nodata_value, acquisition_date.

        Raises:
            ReadError: If the file is not open or the variable is not found.
        """
        if self._file is None:
            raise ReadError("No file is open. Call open() first.")

        try:
            dataset = self._file[variable_name]
        except KeyError:
            raise ReadError(
                f"Variable '{variable_name}' not found in {self._file_path}"
            ) from None

        try:
            data = dataset[...]  # Read entire dataset into memory
        except Exception as e:
            raise ReadError(
                f"Failed to read variable '{variable_name}': {e}"
            ) from e

        if not isinstance(data, np.ndarray):
            data = np.array(data)

        # Extract attributes
        attributes: dict[str, Any] = {}
        for key, value in dataset.attrs.items():
            # Decode byte strings to regular strings
            if isinstance(value, bytes):
                attributes[key] = value.decode("utf-8", errors="replace")
            else:
                attributes[key] = value

        # Extract units from attributes
        units = attributes.get("units", "")
        if isinstance(units, bytes):
            units = units.decode("utf-8", errors="replace")

        # Extract nodata value (common SMAP fill value is -9999.0)
        nodata_value = self._extract_nodata_value(attributes, dataset)

        # Extract acquisition date from file-level or group-level attributes
        acquisition_date = self._extract_acquisition_date()

        return ExtractedVariable(
            data=data,
            attributes=attributes,
            units=str(units),
            nodata_value=nodata_value,
            acquisition_date=acquisition_date,
        )

    def get_metadata(self) -> GeospatialMetadata:
        """Derive spatial metadata from the opened HDF5 file.

        Derives CRS from EASE2_global_projection group attributes or falls back
        to EPSG:6933. Builds rasterio Affine transform from x/y coordinate arrays.

        Returns:
            GeospatialMetadata with CRS, transform, bounds, resolution, width, height.

        Raises:
            ReadError: If metadata cannot be derived.
        """
        if self._file is None:
            raise ReadError("No file is open. Call open() first.")

        if self._metadata_cache is not None:
            return self._metadata_cache

        try:
            crs = self._derive_crs()
            transform, bounds, resolution, width, height = self._derive_transform()

            self._metadata_cache = GeospatialMetadata(
                crs=crs,
                transform=transform,
                bounds=bounds,
                resolution=resolution,
                width=width,
                height=height,
            )
            return self._metadata_cache

        except ReadError:
            raise
        except Exception as e:
            raise ReadError(
                f"Failed to derive geospatial metadata: {e}"
            ) from e

    def close(self) -> None:
        """Close the HDF5 file if open."""
        if self._file is not None:
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None
            self._file_path = None
            self._metadata_cache = None

    def __enter__(self) -> "SMAPHDF5Reader":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ---- Private helpers ----

    def _extract_nodata_value(
        self, attributes: dict[str, Any], dataset: h5py.Dataset
    ) -> float:
        """Extract nodata/fill value from attributes or use SMAP default."""
        # Check common attribute names for fill/nodata value
        for key in ("_FillValue", "missing_value", "nodata_value"):
            if key in attributes:
                val = attributes[key]
                try:
                    return float(val)
                except (ValueError, TypeError):
                    continue

        # Check dataset dtype for fill value
        if hasattr(dataset, "fillvalue") and dataset.fillvalue is not None:
            try:
                return float(dataset.fillvalue)
            except (ValueError, TypeError):
                pass

        # SMAP default fill value
        return -9999.0

    def _extract_acquisition_date(self) -> str:
        """Extract acquisition date from HDF5 file attributes or filename."""
        if self._file is None:
            return ""

        # Try file-level attributes
        for key in ("StartDateTime", "StartTime", "ProductionDateTime", "Date"):
            if key in self._file.attrs:
                val = self._file.attrs[key]
                if isinstance(val, bytes):
                    val = val.decode("utf-8", errors="replace")
                if val:
                    return str(val)[:19]  # Truncate to ISO-like format

        # Try Geophysical_Data group attributes
        try:
            geo_group = self._file.get("Geophysical_Data")
            if geo_group is not None:
                for key in ("StartTime", "StartDateTime"):
                    if key in geo_group.attrs:
                        val = geo_group.attrs[key]
                        if isinstance(val, bytes):
                            val = val.decode("utf-8", errors="replace")
                        if val:
                            return str(val)[:19]
        except Exception:
            pass

        # Fallback: extract from filename
        if self._file_path:
            name = self._file_path.stem
            # SMAP filenames contain timestamps like 20231231T223000
            import re
            match = re.search(r"(\d{8}T\d{6})", name)
            if match:
                return match.group(1)

        return ""

    def _derive_crs(self) -> str:
        """Derive CRS from HDF5 metadata or fall back to EPSG:6933."""
        if self._file is None:
            raise ReadError("No file is open.")

        # Try to find CRS info in EASE2_global_projection or similar groups
        projection_groups = [
            "EASE2_global_projection",
            "Projection",
            "Grid",
            "SpatialReference",
        ]

        for group_name in projection_groups:
            try:
                group = self._file.get(group_name)
                if group is not None:
                    crs_info = self._extract_crs_from_group(group)
                    if crs_info:
                        return crs_info
            except Exception:
                continue

        # Fallback to known SMAP EASE-Grid 2.0 CRS
        return _EPSG_6933

    def _extract_crs_from_group(self, group: h5py.Group) -> str | None:
        """Try to extract CRS info from a projection group's attributes."""
        attrs = dict(group.attrs)

        # Check for grid_mapping_name or similar
        grid_mapping = attrs.get("grid_mapping_name", "")
        if isinstance(grid_mapping, bytes):
            grid_mapping = grid_mapping.decode("utf-8", errors="replace")

        if "lambert_cylindrical" in grid_mapping.lower() or "ease" in grid_mapping.lower():
            return _EPSG_6933

        # Check for longitude_of_central_meridian (EASE-Grid 2.0 uses 0)
        lon_meridian = attrs.get("longitude_of_central_meridian", None)
        standard_parallel = attrs.get("standard_parallel", None)

        if lon_meridian is not None:
            # This looks like a Lambert Cylindrical projection
            return _EPSG_6933

        return None

    def _derive_transform(self) -> tuple[Any, tuple[float, float, float, float], tuple[float, float], int, int]:
        """Derive Affine transform, bounds, resolution, and dimensions from HDF5.

        Returns:
            Tuple of (transform, bounds, resolution, width, height).
        """
        if self._file is None:
            raise ReadError("No file is open.")

        # Try to find x/y coordinate arrays
        x_coords = self._find_coordinate_array("x")
        y_coords = self._find_coordinate_array("y")

        if x_coords is not None and y_coords is not None:
            return self._build_transform_from_coords(x_coords, y_coords)

        # Fallback: try to derive from a data variable's shape and known grid
        return self._build_transform_from_fallback()

    def _find_coordinate_array(self, coord_name: str) -> np.ndarray | None:
        """Find a coordinate array in the HDF5 file."""
        # Common paths for coordinate arrays
        search_paths = [
            f"Cell_Grid_{coord_name.upper()}",
            f"x_{coord_name}",
            f"y_{coord_name}",
            f"{coord_name}",
            f"Geophysical_Data/{coord_name}",
            f"EASE2_global_projection/{coord_name}",
        ]

        for path in search_paths:
            try:
                ds = self._file[path]  # type: ignore[index]
                data = ds[...]
                if isinstance(data, np.ndarray):
                    return data
            except (KeyError, Exception):
                continue

        return None

    def _build_transform_from_coords(
        self, x_coords: np.ndarray, y_coords: np.ndarray
    ) -> tuple[Any, tuple[float, float, float, float], tuple[float, float], int, int]:
        """Build Affine transform from x and y coordinate arrays."""
        if Affine is None:
            raise ReadError("rasterio is required for transform derivation.")

        # x_coords and y_coords can be 1D or 2D arrays
        if x_coords.ndim == 2:
            x_1d = x_coords[0, :]  # First row
        else:
            x_1d = x_coords

        if y_coords.ndim == 2:
            y_1d = y_coords[:, 0]  # First column
        else:
            y_coords = y_coords
            y_1d = y_coords

        # Ensure arrays are sorted (ascending for x, descending for y in raster convention)
        x_sorted = np.sort(x_1d)
        y_sorted = np.sort(y_1d)

        # Calculate resolution
        if len(x_sorted) >= 2:
            x_res = float(x_sorted[1] - x_sorted[0])
        else:
            x_res = 9000.0  # EASE-Grid 2.0 default ~9km

        if len(y_sorted) >= 2:
            y_res = float(y_sorted[1] - y_sorted[0])
        else:
            y_res = 9000.0

        # Bounds
        minx = float(x_sorted[0]) - x_res / 2
        maxx = float(x_sorted[-1]) + x_res / 2
        miny = float(y_sorted[0]) - abs(y_res) / 2
        maxy = float(y_sorted[-1]) + abs(y_res) / 2

        # Width and height
        width = len(x_sorted)
        height = len(y_sorted)

        # Affine transform: (c, a, b, f, d, e)
        # x = c + a*col + b*row
        # y = f + d*col + e*row
        transform = Affine.translation(minx, maxy) * Affine.scale(x_res, -abs(y_res))

        bounds = (minx, miny, maxx, maxy)
        resolution = (abs(x_res), abs(y_res))

        return transform, bounds, resolution, width, height

    def _build_transform_from_fallback(
        self,
    ) -> tuple[Any, tuple[float, float, float, float], tuple[float, float], int, int]:
        """Build transform from known SMAP grid parameters (fallback)."""
        if Affine is None:
            raise ReadError("rasterio is required for transform derivation.")

        # SMAP L4 grid: 1624 rows x 3856 cols, ~9km resolution
        # EASE-Grid 2.0 global bounds
        height = 1624
        width = 3856
        resolution = 9000.0  # ~9km in meters

        # EASE-Grid 2.0 global extent (approximate)
        minx = -17367530.0
        maxy = 7314540.0

        transform = Affine.translation(minx, maxy) * Affine.scale(resolution, -resolution)

        maxx = minx + width * resolution
        miny = maxy - height * resolution

        bounds = (minx, miny, maxx, maxy)
        resolution_tuple = (resolution, resolution)

        return transform, bounds, resolution_tuple, width, height
