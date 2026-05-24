"""Raster processing service.

Source-agnostic service for raster processing: nodata handling,
CRS/transform building, ROI clipping, and statistics calculation.
"""

from pathlib import Path
from typing import Any

import numpy as np

from src.geospatial.domain.errors import ReadError
from src.geospatial.domain.models import GeospatialMetadata, RasterProcessingResult

try:
    from rasterio.transform import Affine
    import rasterio
    from rasterio.warp import transform_bounds
except ImportError:
    rasterio = None  # type: ignore[misc]
    Affine = None  # type: ignore[misc]

try:
    from shapely.geometry import shape, box
    from shapely.ops import transform as shapely_transform
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False


class RasterProcessingService:
    """Processes raster data with nodata handling, ROI clipping, and statistics.

    Source-agnostic: works with any numpy array and GeospatialMetadata.
    """

    def process(
        self,
        data: np.ndarray,
        metadata: GeospatialMetadata,
        nodata_value: float,
        config: dict[str, Any],
        replace_nodata_with_nan: bool = True,
    ) -> RasterProcessingResult:
        """Process a raster array with nodata handling and optional ROI clipping.

        Args:
            data: 2D numpy array to process.
            metadata: GeospatialMetadata with CRS, transform, etc.
            nodata_value: The nodata sentinel value.
            config: Processing configuration (ROI settings, etc.).
            replace_nodata_with_nan: Whether to replace nodata with NaN.

        Returns:
            RasterProcessingResult with processed data, metadata, and statistics.

        Raises:
            ReadError: If ROI path is invalid or processing fails.
        """
        warnings: list[str] = []

        # Ensure 2D array
        if data.ndim != 2:
            raise ReadError(
                f"Expected 2D array, got {data.ndim}D with shape {data.shape}"
            )

        # Step 1: Handle nodata
        processed_data = self._handle_nodata(data, nodata_value, replace_nodata_with_nan)

        # Step 2: ROI clipping (if enabled)
        roi_config = config.get("roi", {})
        roi_enabled = roi_config.get("enabled", False)

        if roi_enabled:
            roi_path = roi_config.get("path")
            if roi_path:
                try:
                    processed_data, metadata = self._apply_roi_clip(
                        processed_data, metadata, Path(roi_path), nodata_value
                    )
                except ReadError:
                    raise
                except Exception as e:
                    raise ReadError(
                        f"Failed to apply ROI clipping from {roi_path}: {e}"
                    ) from e
            else:
                warnings.append("ROI enabled but no path configured — processing full raster")

        # Step 3: Calculate statistics
        statistics = self._calculate_statistics(processed_data, nodata_value)

        return RasterProcessingResult(
            data=processed_data,
            metadata=metadata,
            statistics=statistics,
            warnings=warnings,
        )

    def _handle_nodata(
        self,
        data: np.ndarray,
        nodata_value: float,
        replace_with_nan: bool,
    ) -> np.ndarray:
        """Handle nodata values in the raster array.

        Args:
            data: Input array.
            nodata_value: The nodata sentinel value.
            replace_with_nan: Whether to replace nodata with NaN.

        Returns:
            Processed array with nodata handled.
        """
        if not replace_with_nan:
            return data.copy()

        # Convert to float if needed (for NaN support)
        if data.dtype == np.float32 or data.dtype == np.float64:
            result = data.copy()
        else:
            result = data.astype(np.float64)

        # Replace nodata with NaN
        result[result == nodata_value] = np.nan

        return result

    def _apply_roi_clip(
        self,
        data: np.ndarray,
        metadata: GeospatialMetadata,
        roi_path: Path,
        nodata_value: float,
    ) -> tuple[np.ndarray, GeospatialMetadata]:
        """Apply ROI clipping to the raster.

        Reprojects ROI geometry from EPSG:4326 to raster CRS, then clips.

        Args:
            data: Input raster array.
            metadata: GeospatialMetadata for the raster.
            roi_path: Path to ROI GeoJSON file.
            nodata_value: Value to use outside ROI.

        Returns:
            Tuple of (clipped_data, updated_metadata).

        Raises:
            ReadError: If ROI file is invalid or clipping fails.
        """
        if not roi_path.exists():
            raise ReadError(f"ROI file not found: {roi_path}")

        if not HAS_SHAPELY:
            raise ReadError(
                "shapely is required for ROI clipping. Install with: pip install shapely"
            )

        if rasterio is None:
            raise ReadError("rasterio is required for ROI clipping")

        # Load ROI geometry from GeoJSON
        roi_geometry = self._load_roi_geometry(roi_path)

        # Get raster CRS
        raster_crs = None
        try:
            raster_crs = rasterio.crs.CRS.from_string(metadata.crs)
        except Exception:
            try:
                raster_crs = rasterio.crs.CRS.from_epsg(
                    int(metadata.crs.split(":")[-1])
                )
            except Exception:
                raise ReadError(
                    f"Cannot parse raster CRS: {metadata.crs}"
                )

        # Reproject ROI from EPSG:4326 to raster CRS
        roi_raster_crs = self._reproject_geometry(roi_geometry, "EPSG:4326", raster_crs)

        # Calculate clip bounds in raster CRS
        clip_bounds = roi_raster_crs.bounds

        # Convert bounds to pixel coordinates
        transform = metadata.transform
        if transform is None:
            raise ReadError("Cannot clip: no affine transform in metadata")

        # Calculate row/col ranges for the clip
        col_min, row_max = ~transform * (clip_bounds.minx, clip_bounds.miny)
        col_max, row_min = ~transform * (clip_bounds.maxx, clip_bounds.maxy)

        # Convert to integer indices and clamp to array bounds
        height, width = data.shape
        r_start = max(0, int(row_min))
        r_end = min(height, int(row_max) + 1)
        c_start = max(0, int(col_min))
        c_end = min(width, int(col_max) + 1)

        if r_start >= r_end or c_start >= c_end:
            raise ReadError(
                f"ROI does not overlap with raster bounds. "
                f"Raster: {width}x{height}, ROI bounds: {clip_bounds}"
            )

        # Clip the data
        clipped_data = data[r_start:r_end, c_start:c_end].copy()

        # Update metadata for clipped raster
        new_transform = transform * Affine.translation(c_start, r_start)
        new_height, new_width = clipped_data.shape
        new_bounds = (
            new_transform.c,
            new_transform.f + new_transform.e * new_height,
            new_transform.c + new_transform.a * new_width,
            new_transform.f,
        )

        new_metadata = GeospatialMetadata(
            crs=metadata.crs,
            transform=new_transform,
            bounds=new_bounds,
            resolution=metadata.resolution,
            width=new_width,
            height=new_height,
        )

        return clipped_data, new_metadata

    def _load_roi_geometry(self, roi_path: Path) -> Any:
        """Load ROI geometry from a GeoJSON file."""
        try:
            import json
            with open(roi_path, "r") as f:
                geojson = json.load(f)
        except json.JSONDecodeError as e:
            raise ReadError(f"Invalid GeoJSON in {roi_path}: {e}") from e
        except OSError as e:
            raise ReadError(f"Cannot read ROI file {roi_path}: {e}") from e

        # Extract geometry from GeoJSON
        if geojson.get("type") == "FeatureCollection":
            # Use the first feature's geometry
            features = geojson.get("features", [])
            if not features:
                raise ReadError(f"GeoJSON FeatureCollection is empty: {roi_path}")
            geometry = features[0].get("geometry")
        elif geojson.get("type") == "Feature":
            geometry = geojson.get("geometry")
        elif geojson.get("type") in ("Polygon", "MultiPolygon"):
            geometry = geojson
        else:
            raise ReadError(
                f"Unsupported GeoJSON type in {roi_path}: {geojson.get('type')}"
            )

        if geometry is None:
            raise ReadError(f"No geometry found in {roi_path}")

        return shape(geometry)

    def _reproject_geometry(
        self,
        geometry: Any,
        src_crs: str,
        dst_crs: Any,
    ) -> Any:
        """Reproject a shapely geometry from src_crs to dst_crs."""
        from pyproj import Transformer

        # Get dst CRS as string
        if hasattr(dst_crs, "to_string"):
            dst_crs_str = dst_crs.to_string()
        elif hasattr(dst_crs, "to_epsg") and dst_crs.to_epsg():
            dst_crs_str = f"EPSG:{dst_crs.to_epsg()}"
        else:
            dst_crs_str = str(dst_crs)

        transformer = Transformer.from_crs(src_crs, dst_crs_str, always_xy=True)

        def project(x: float, y: float) -> tuple[float, float]:
            return transformer.transform(x, y)

        return shapely_transform(project, geometry)

    def _calculate_statistics(
        self, data: np.ndarray, nodata_value: float
    ) -> dict[str, Any]:
        """Calculate raster statistics.

        Returns:
            Dict with min, max, mean, valid_pixel_count, nodata_pixel_count.
        """
        total_pixels = data.size

        if data.dtype == np.float32 or data.dtype == np.float64:
            # NaN-based counting
            valid_mask = ~np.isnan(data)
            valid_data = data[valid_mask]
            valid_count = int(np.sum(valid_mask))
            nodata_count = total_pixels - valid_count
        else:
            # Sentinel-based counting
            valid_mask = data != nodata_value
            valid_data = data[valid_mask].astype(np.float64)
            valid_count = int(np.sum(valid_mask))
            nodata_count = total_pixels - valid_count

        if valid_count == 0:
            return {
                "min": None,
                "max": None,
                "mean": None,
                "valid_pixel_count": 0,
                "nodata_pixel_count": nodata_count,
            }

        return {
            "min": float(np.min(valid_data)),
            "max": float(np.max(valid_data)),
            "mean": float(np.mean(valid_data)),
            "valid_pixel_count": valid_count,
            "nodata_pixel_count": nodata_count,
        }
