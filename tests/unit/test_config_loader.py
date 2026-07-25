"""Unit tests for config loader."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from src.config.config_loader import (
    SmapSourceConfig,
    SourceConfig,
    get_max_days_range,
    load_sources_config,
)


VALID_SMAP_CONFIG = {
    "sources": {
        "smap": {
            "product_id": "SPL4SMGP.008",
            "short_name": "SPL4SMGP",
            "version": "008",
            "bbox": [-58.5, -35.0, -58.0, -34.5],
            "max_days_range": 7,
            "description": "SMAP Level 4",
            "format": "HDF5",
            "provider": "NASA Earthdata",
        }
    }
}


def _write_config(tmp_path: Path, config: dict) -> Path:
    """Write a config dict to a temporary YAML file."""
    config_file = tmp_path / "sources.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    return config_file


class TestSmapSourceConfig:
    """Tests for SmapSourceConfig Pydantic model."""

    def test_valid_config(self):
        config = SmapSourceConfig(**VALID_SMAP_CONFIG["sources"]["smap"])
        assert config.product_id == "SPL4SMGP.008"
        assert config.short_name == "SPL4SMGP"
        assert config.version == "008"
        assert config.bbox == [-58.5, -35.0, -58.0, -34.5]
        assert config.max_days_range == 7

    def test_default_max_days_range(self):
        data = VALID_SMAP_CONFIG["sources"]["smap"].copy()
        del data["max_days_range"]
        config = SmapSourceConfig(**data)
        assert config.max_days_range == 7

    def test_invalid_bbox_too_few_values(self):
        data = VALID_SMAP_CONFIG["sources"]["smap"].copy()
        data["bbox"] = [-58.5, -35.0]
        with pytest.raises(ValueError, match="4"):
            SmapSourceConfig(**data)

    def test_invalid_bbox_lon_out_of_range(self):
        data = VALID_SMAP_CONFIG["sources"]["smap"].copy()
        data["bbox"] = [-200.0, -35.0, -58.0, -34.5]
        with pytest.raises(ValueError, match="min_lon"):
            SmapSourceConfig(**data)

    def test_invalid_bbox_lat_out_of_range(self):
        data = VALID_SMAP_CONFIG["sources"]["smap"].copy()
        data["bbox"] = [-58.5, -100.0, -58.0, -34.5]
        with pytest.raises(ValueError, match="min_lat"):
            SmapSourceConfig(**data)

    def test_invalid_bbox_min_greater_than_max(self):
        data = VALID_SMAP_CONFIG["sources"]["smap"].copy()
        data["bbox"] = [-58.0, -35.0, -58.5, -34.5]  # min_lon > max_lon
        with pytest.raises(ValueError, match="min_lon"):
            SmapSourceConfig(**data)

    def test_valid_bbox_full_range(self):
        config = SmapSourceConfig(
            product_id="TEST.001",
            short_name="TEST",
            version="001",
            bbox=[-180.0, -90.0, 180.0, 90.0],
        )
        assert config.bbox == [-180.0, -90.0, 180.0, 90.0]


class TestSourceConfig:
    """Tests for SourceConfig container."""

    def test_get_smap_config(self):
        config = SourceConfig(**VALID_SMAP_CONFIG)
        smap = config.get_smap_config()
        assert smap.product_id == "SPL4SMGP.008"

    def test_missing_smap_source(self):
        config = SourceConfig(sources={"other": {}})
        with pytest.raises(ValueError, match="No 'smap' source"):
            config.get_smap_config()


class TestLoadSourcesConfig:
    """Tests for load_sources_config function."""

    def test_load_valid_config(self, tmp_path):
        config_file = _write_config(tmp_path, VALID_SMAP_CONFIG)
        config = load_sources_config(config_file)
        assert isinstance(config, SourceConfig)
        smap = config.get_smap_config()
        assert smap.product_id == "SPL4SMGP.008"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_sources_config("/nonexistent/path/sources.yaml")

    def test_missing_sources_key(self, tmp_path):
        config_file = _write_config(tmp_path, {"no_sources": True})
        with pytest.raises(ValueError, match="sources"):
            load_sources_config(config_file)


class TestGetMaxDaysRange:
    """Tests for MAX_DAYS_RANGE environment variable."""

    def test_default_value(self):
        # Ensure env var is not set
        old = os.environ.pop("MAX_DAYS_RANGE", None)
        try:
            assert get_max_days_range() == 7
        finally:
            if old is not None:
                os.environ["MAX_DAYS_RANGE"] = old

    def test_env_override(self):
        old = os.environ.get("MAX_DAYS_RANGE")
        try:
            os.environ["MAX_DAYS_RANGE"] = "14"
            assert get_max_days_range() == 14
        finally:
            if old is not None:
                os.environ["MAX_DAYS_RANGE"] = old
            else:
                os.environ.pop("MAX_DAYS_RANGE", None)

    def test_invalid_env_value(self):
        old = os.environ.get("MAX_DAYS_RANGE")
        try:
            os.environ["MAX_DAYS_RANGE"] = "not_a_number"
            with pytest.raises(ValueError, match="integer"):
                get_max_days_range()
        finally:
            if old is not None:
                os.environ["MAX_DAYS_RANGE"] = old
            else:
                os.environ.pop("MAX_DAYS_RANGE", None)
