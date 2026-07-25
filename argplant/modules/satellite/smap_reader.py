"""SMAP HDF5 reader — extracts soil moisture values for a given lat/lon.

SMAP L3 Radiometer Global Daily 36 km EASE-Grid 2.0
- Grid: 406 rows × 964 columns
- Resolution: ~36 km (0.36° at equator)
- Projection: EASE-Grid 2.0 (simplified to regular lat/lon for Pergamino area)

Datasets inside the HDF5:
  Soil_Moisture_Retrieval_Data/soil_moisture          — m³/m³, fill = -9999.0
  Soil_Moisture_Retrieval_Data/retrieval_qual_flag    — 0 = recommended, 1 = not
  Soil_Moisture_Retrieval_Data/surface_temperature     — Kelvin
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger("argplant.satellite.smap_reader")

# EASE-Grid 2.0 constants for the 36 km SMAP L3 product
_EASE_NROWS = 406
_EASE_NCOLS = 964
_EASE_UL_LAT = 90.0  # upper-left latitude (north pole)
_EASE_UL_LON = -180.0  # upper-left longitude
_EASE_CELL_DEG = 0.36  # approximate degrees per cell at equator

# Fill value and valid range for soil_moisture
_SM_FILL = -9999.0
_SM_MIN = 0.02  # m³/m³ — below this is essentially no moisture
_SM_MAX = 0.60  # m³/m³ — saturation

# Quality flag: 0 = recommended for use
_QUALITY_GOOD = 0


@dataclass
class SmapPixel:
    """Soil moisture value extracted from a single SMAP grid cell."""

    scene_id: str
    acquisition_date: str
    lat: float
    lon: float
    soil_moisture: float | None  # m³/m³, None if pixel is bad/missing
    surface_temperature_k: float | None
    quality_flag: int | None
    unit: str = "m3/m3"

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "acquisition_date": self.acquisition_date,
            "lat": self.lat,
            "lon": self.lon,
            "soil_moisture": self.soil_moisture,
            "soil_moisture_pct": round(self.soil_moisture * 100, 1)
            if self.soil_moisture is not None
            else None,
            "surface_temperature_k": self.surface_temperature_k,
            "quality_flag": self.quality_flag,
            "unit": self.unit,
        }


def _latlon_to_ease_grid(lat: float, lon: float) -> tuple[int, int]:
    """Convert WGS84 lat/lon to EASE-Grid 2.0 row/col indices.

    Uses a simplified linear mapping that is accurate enough for mid-latitudes
    (including Argentina's Pampa Húmeda). For production-grade precision,
    use pyproj with the EASE-Grid 2.0 CRS definition.
    """
    row = int((_EASE_UL_LAT - lat) / _EASE_CELL_DEG)
    col = int((lon - _EASE_UL_LON) / _EASE_CELL_DEG)

    # Clamp to valid grid bounds
    row = max(0, min(row, _EASE_NROWS - 1))
    col = max(0, min(col, _EASE_NCOLS - 1))

    return row, col


def read_smap_pixel(
    filepath: str | Path,
    lat: float,
    lon: float,
    scene_id: str = "",
    acquisition_date: str = "",
) -> SmapPixel:
    """Open an SMAP L3 HDF5 file and extract the soil moisture value
    for the grid cell covering the given coordinates.

    Args:
        filepath: Path to the .h5 file (local or mounted).
        lat: Target latitude (WGS84).
        lon: Target longitude (WGS84).
        scene_id: Granule identifier for provenance.
        acquisition_date: ISO date string for provenance.

    Returns:
        SmapPixel with the extracted values. soil_moisture is None
        when the pixel is fill or flagged as bad quality.
    """
    import h5py

    filepath = Path(filepath)

    sm = None
    temp = None
    quality = None

    try:
        with h5py.File(str(filepath), "r") as h5:
            # Navigate to the retrieval data group
            group = h5["Soil_Moisture_Retrieval_Data"]

            soil_moisture_arr: np.ndarray = group["soil_moisture"][:]
            quality_arr: np.ndarray = group["retrieval_qual_flag"][:]
            temp_arr: np.ndarray | None = None

            if "surface_temperature" in group:
                temp_arr = group["surface_temperature"][:]

            # Convert coordinates to grid indices
            row, col = _latlon_to_ease_grid(lat, lon)

            raw_sm = float(soil_moisture_arr[row, col])
            raw_quality = int(quality_arr[row, col])
            raw_temp = float(temp_arr[row, col]) if temp_arr is not None else None

            # Validate
            if raw_sm > _SM_FILL and _SM_MIN <= raw_sm <= _SM_MAX and raw_quality == _QUALITY_GOOD:
                sm = round(raw_sm, 4)
                quality = raw_quality
                temp = round(raw_temp - 273.15, 1) if raw_temp is not None and raw_temp > 0 else None
            else:
                sm = None
                quality = raw_quality
                logger.debug(
                    "SMAP pixel rejected: sm=%.4f quality=%d row=%d col=%d file=%s",
                    raw_sm, raw_quality, row, col, filepath.name,
                )
    except (OSError, KeyError, ValueError) as exc:
        logger.warning("Failed to read SMAP HDF5 %s: %s", filepath.name, exc)

    return SmapPixel(
        scene_id=scene_id,
        acquisition_date=acquisition_date,
        lat=lat,
        lon=lon,
        soil_moisture=sm,
        surface_temperature_k=temp,
        quality_flag=quality,
    )
