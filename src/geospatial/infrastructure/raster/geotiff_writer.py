"""GeoTIFF writer implementation.

Source-agnostic GeoTIFF writer with safe write strategy (.tmp → atomic move).
Uses rasterio for writing georeferenced raster files.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from src.geospatial.domain.errors import WriteError
from src.geospatial.domain.models import GeospatialMetadata

try:
    import rasterio
    from rasterio.transform import Affine
except ImportError:
    rasterio = None  # type: ignore[misc]
    Affine = None  # type: ignore[misc]


class GeoTIFFWriter:
    """Writes processed raster arrays to GeoTIFF files.

    Source-agnostic: accepts any raster array and geospatial metadata.
    Uses safe write strategy: writes to .tmp, then atomic move to final path.
    """

    def write(
        self,
        data: np.ndarray,
        metadata: GeospatialMetadata,
        source: str,
        variable: str,
        acquisition_datetime: str,
        processing_version: str,
        nodata_value: float | None = None,
        driver: str = "GTiff",
        compress: str = "deflate",
        dtype: str | None = None,
    ) -> str:
        """Write a raster array to a GeoTIFF file with atomic move.

        Args:
            data: 2D numpy array to write.
            metadata: GeospatialMetadata with CRS, transform, bounds, etc.
            source: Source code (e.g. "smap").
            variable: Variable name (e.g. "soil_moisture").
            acquisition_datetime: ISO datetime string for the acquisition.
            processing_version: Processing version string (e.g. "v1").
            nodata_value: Nodata value to embed in the GeoTIFF.
            driver: Rasterio driver (default: GTiff).
            compress: Compression method (default: deflate).
            dtype: Output dtype (default: inferred from data).

        Returns:
            Absolute path to the written GeoTIFF file.

        Raises:
            WriteError: If the file cannot be written.
        """
        if rasterio is None:
            raise WriteError("rasterio is not installed — cannot write GeoTIFF")

        # Generate deterministic output path
        output_path = self._generate_output_path(
            source, variable, acquisition_datetime, processing_version
        )

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create temp file path in the same directory (for atomic move)
        tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")

        try:
            self._write_to_tmp(
                data, metadata, tmp_path, nodata_value, driver, compress, dtype
            )
            # Atomic move to final path
            os.replace(str(tmp_path), str(output_path))
        except WriteError:
            # Clean up temp file on failure
            self._cleanup_tmp(tmp_path)
            raise
        except Exception as e:
            self._cleanup_tmp(tmp_path)
            raise WriteError(
                f"Failed to write GeoTIFF to {output_path}: {e}"
            ) from e

        return str(output_path)

    def _generate_output_path(
        self,
        source: str,
        variable: str,
        acquisition_datetime: str,
        processing_version: str,
    ) -> Path:
        """Generate deterministic output path from metadata.

        Format: data/processed/{source}/{variable}/{YYYY}/{MM}/{source}_{variable}_{datetime}_{version}.tif
        """
        # Parse year and month from acquisition datetime
        # Expected formats: "20231231T223000", "2023-12-31T22:30:00", etc.
        try:
            # Try ISO format first
            dt = datetime.fromisoformat(acquisition_datetime.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            # Try compact format (e.g. "20231231T223000")
            try:
                dt = datetime.strptime(acquisition_datetime[:15], "%Y%m%dT%H%M%S")
            except (ValueError, AttributeError):
                # Fallback: use current date
                dt = datetime.now()

        year = dt.strftime("%Y")
        month = dt.strftime("%m")

        # Sanitize variable name for filesystem
        safe_variable = variable.replace("/", "_").replace("\\", "_")

        filename = f"{source}_{safe_variable}_{acquisition_datetime}_{processing_version}.tif"

        return Path("data") / "processed" / source / safe_variable / year / month / filename

    def _write_to_tmp(
        self,
        data: np.ndarray,
        metadata: GeospatialMetadata,
        tmp_path: Path,
        nodata_value: float | None,
        driver: str,
        compress: str,
        dtype: str | None,
    ) -> None:
        """Write raster data to the temporary file."""
        # Ensure data is 2D
        if data.ndim != 2:
            raise WriteError(
                f"Expected 2D array, got {data.ndim}D with shape {data.shape}"
            )

        # Determine output dtype
        if dtype is None:
            if data.dtype == np.float64:
                out_dtype = "float32"
            else:
                out_dtype = str(data.dtype)
        else:
            out_dtype = dtype

        # Convert data to output dtype
        out_data = data.astype(out_dtype)

        # Determine nodata
        effective_nodata = nodata_value

        # Build rasterio profile
        height, width = out_data.shape

        # CRS handling
        crs = None
        if metadata.crs:
            try:
                crs = rasterio.crs.CRS.from_string(metadata.crs)
            except Exception:
                # Try as EPSG code
                try:
                    crs = rasterio.crs.CRS.from_epsg(int(metadata.crs.split(":")[-1]))
                except Exception:
                    crs = None

        transform = metadata.transform
        if transform is None:
            transform = Affine.identity()

        profile = {
            "driver": driver,
            "dtype": out_dtype,
            "width": width,
            "height": height,
            "count": 1,
            "crs": crs,
            "transform": transform,
            "compress": compress,
        }

        if effective_nodata is not None:
            profile["nodata"] = effective_nodata

        try:
            with rasterio.open(str(tmp_path), "w", **profile) as dst:
                dst.write(out_data, 1)

            # Basic validation: reopen and check
            with rasterio.open(str(tmp_path), "r") as src:
                if src.width != width or src.height != height:
                    raise WriteError(
                        f"Written file dimensions mismatch: expected {width}x{height}, "
                        f"got {src.width}x{src.height}"
                    )
        except WriteError:
            raise
        except rasterio.errors.RasterioError as e:
            raise WriteError(f"Rasterio error writing {tmp_path}: {e}") from e
        except Exception as e:
            raise WriteError(f"Error writing {tmp_path}: {e}") from e

    def _cleanup_tmp(self, tmp_path: Path) -> None:
        """Remove temporary file if it exists."""
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass  # Best effort cleanup
