"""Configuration loader for ingestion sources.

Validates YAML source configurations using Pydantic models.
"""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

load_dotenv()


class SmapSourceConfig(BaseModel):
    """Configuration for a SMAP data source."""

    product_id: str = Field(..., description="NASA Earthdata product identifier")
    short_name: str = Field(..., description="Short name for the product")
    version: str = Field(..., description="Product version string")
    bbox: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Bounding box [min_lon, min_lat, max_lon, max_lat]",
    )
    max_days_range: int = Field(
        default=7, ge=1, le=365, description="Maximum date range in days"
    )
    description: str = Field(default="", description="Human-readable description")
    format: str = Field(default="HDF5", description="File format")
    provider: str = Field(default="", description="Data provider")

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v: list[float]) -> list[float]:
        min_lon, min_lat, max_lon, max_lat = v
        if not (-180 <= min_lon <= 180):
            raise ValueError(f"min_lon must be between -180 and 180, got {min_lon}")
        if not (-180 <= max_lon <= 180):
            raise ValueError(f"max_lon must be between -180 and 180, got {max_lon}")
        if not (-90 <= min_lat <= 90):
            raise ValueError(f"min_lat must be between -90 and 90, got {min_lat}")
        if not (-90 <= max_lat <= 90):
            raise ValueError(f"max_lat must be between -90 and 90, got {max_lat}")
        if min_lon >= max_lon:
            raise ValueError(f"min_lon ({min_lon}) must be less than max_lon ({max_lon})")
        if min_lat >= max_lat:
            raise ValueError(f"min_lat ({min_lat}) must be less than max_lat ({max_lat})")
        return v


class SourceConfig(BaseModel):
    """Top-level source configuration container."""

    sources: dict[str, Any]

    def get_smap_config(self) -> SmapSourceConfig:
        """Extract and validate SMAP configuration."""
        smap_data = self.sources.get("smap")
        if not smap_data:
            raise ValueError("No 'smap' source configured in sources.yaml")
        return SmapSourceConfig(**smap_data)


def get_max_days_range() -> int:
    """Get the maximum days range from environment or config default.

    Priority: MAX_DAYS_RANGE env var > config file default (7).
    """
    env_value = os.getenv("MAX_DAYS_RANGE")
    if env_value:
        try:
            return int(env_value)
        except ValueError:
            raise ValueError(f"MAX_DAYS_RANGE must be an integer, got '{env_value}'")
    return 7


def load_sources_config(config_path: str | Path | None = None) -> SourceConfig:
    """Load and validate the sources.yaml configuration file.

    Args:
        config_path: Path to sources.yaml. Defaults to src/config/sources.yaml
                     relative to the project root.

    Returns:
        Validated SourceConfig instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the config is invalid.
    """
    if config_path is None:
        # Default path relative to this module
        config_path = Path(__file__).parent / "sources.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    if not raw_config or "sources" not in raw_config:
        raise ValueError("Configuration must contain a 'sources' key")

    return SourceConfig(**raw_config)


def load_geospatial_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load the geospatial-sources.yaml configuration file.

    Args:
        config_path: Path to geospatial-sources.yaml. Defaults to
                     src/config/geospatial-sources.yaml relative to this module.

    Returns:
        Dict with geospatial configuration (variables, roi, nodata_value, etc.).

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    if config_path is None:
        config_path = Path(__file__).parent / "geospatial-sources.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Geospatial configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    return raw_config or {}
