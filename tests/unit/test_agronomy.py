"""Unit tests for the agronomy module — seed loader and crop catalog service."""

import tempfile
from pathlib import Path

import pytest
import yaml

from argplant.modules.agronomy import seed_data as sd
from argplant.modules.agronomy.service import CropCatalogService


# ---------------------------------------------------------------------------
# Fixture: valid YAML content
# ---------------------------------------------------------------------------

VALID_CROPS_YAML = {
    "crops": [
        {"id": "soy", "name": "Soja", "scientific_name": "Glycine max", "growing_season_days": 120},
        {"id": "corn", "name": "Maíz", "scientific_name": "Zea mays", "growing_season_days": 130},
    ]
}

VALID_BBCH_YAML = {
    "stages": {
        "soy": [
            {
                "bbch_code": "00",
                "name": "Semilla seca",
                "description": "Dry seed",
                "kc": 0.0,
                "water_stress_sensitivity": "low",
                "temp_sensitivity": "low",
            },
            {
                "bbch_code": "60",
                "name": "Inicio de floración",
                "description": "First flowers open",
                "kc": 1.15,
                "water_stress_sensitivity": "high",
                "temp_sensitivity": "high",
            },
            {
                "bbch_code": "79",
                "name": "Fin formación de vainas",
                "description": "End of pod formation",
                "kc": 0.9,
                "water_stress_sensitivity": "medium",
                "temp_sensitivity": "medium",
            },
        ],
        "corn": [
            {
                "bbch_code": "60",
                "name": "Inicio de floración masculina",
                "description": "First anthers visible",
                "kc": 1.2,
                "water_stress_sensitivity": "high",
                "temp_sensitivity": "high",
            },
        ],
    }
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(tmp: Path, filename: str, data: dict) -> Path:
    filepath = tmp / filename
    with open(filepath, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh)
    return filepath


# ---------------------------------------------------------------------------
# Seed loading tests
# ---------------------------------------------------------------------------


class TestLoadAgronomySeeds:
    """Tests for load_agronomy_seeds() with valid and invalid fixtures."""

    def test_valid_fixtures_load(self, monkeypatch):
        """GIVEN valid crops.yaml and bbch_stages.yaml
        WHEN load_agronomy_seeds is called
        THEN crops and stages are populated correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _write_yaml(tmp_path, "crops.yaml", VALID_CROPS_YAML)
            _write_yaml(tmp_path, "bbch_stages.yaml", VALID_BBCH_YAML)

            monkeypatch.setattr(sd, "FIXTURE_DIR", tmp_path)
            monkeypatch.setattr(sd, "_crops", {})
            monkeypatch.setattr(sd, "_stages", {})

            sd.load_agronomy_seeds()

            crops = sd.get_crops()
            assert len(crops) == 2
            assert crops["soy"]["name"] == "Soja"
            assert crops["corn"]["scientific_name"] == "Zea mays"

            stages = sd.get_stages()
            assert len(stages["soy"]) == 3
            assert len(stages["corn"]) == 1

    def test_missing_crops_file_raises(self, monkeypatch):
        """GIVEN crops.yaml does not exist
        WHEN load_agronomy_seeds is called
        THEN FileNotFoundError is raised."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _write_yaml(tmp_path, "bbch_stages.yaml", VALID_BBCH_YAML)

            monkeypatch.setattr(sd, "FIXTURE_DIR", tmp_path)
            with pytest.raises(FileNotFoundError):
                sd.load_agronomy_seeds()

    def test_missing_stages_file_raises(self, monkeypatch):
        """GIVEN bbch_stages.yaml does not exist
        WHEN load_agronomy_seeds is called
        THEN FileNotFoundError is raised."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _write_yaml(tmp_path, "crops.yaml", VALID_CROPS_YAML)

            monkeypatch.setattr(sd, "FIXTURE_DIR", tmp_path)
            with pytest.raises(FileNotFoundError):
                sd.load_agronomy_seeds()


# ---------------------------------------------------------------------------
# CropCatalogService tests
# ---------------------------------------------------------------------------


class TestCropCatalogService:
    """Tests for CropCatalogService using pre-loaded seed data."""

    def test_list_crops(self, monkeypatch):
        """GIVEN seed data is loaded
        WHEN list_crops() is called
        THEN returns soy and corn CropInfo objects."""
        monkeypatch.setattr(sd, "_crops", {
            c["id"]: c for c in VALID_CROPS_YAML["crops"]
        })

        crops = CropCatalogService.list_crops()
        assert len(crops) == 2
        ids = {c.id for c in crops}
        assert ids == {"soy", "corn"}
        soy = next(c for c in crops if c.id == "soy")
        assert soy.scientific_name == "Glycine max"

    def test_get_stages_soy(self, monkeypatch):
        """GIVEN seed data with soy stages loaded
        WHEN get_stages('soy') is called
        THEN returns BBCH stages including 60 (flowering) and 79 (pod formation)."""
        monkeypatch.setattr(sd, "_stages", VALID_BBCH_YAML["stages"])

        stages = CropCatalogService.get_stages("soy")
        assert stages is not None
        assert len(stages) == 3
        codes = {s.bbch_code for s in stages}
        assert "60" in codes  # flowering
        assert "79" in codes  # end of pod formation
        # Verify BBCH 60 name
        flowering = next(s for s in stages if s.bbch_code == "60")
        assert flowering.kc == 1.15
        assert flowering.water_stress_sensitivity == "high"

    def test_get_stages_corn(self, monkeypatch):
        """GIVEN seed data with corn stages loaded
        WHEN get_stages('corn') is called
        THEN returns corn BBCH stages."""
        monkeypatch.setattr(sd, "_stages", VALID_BBCH_YAML["stages"])

        stages = CropCatalogService.get_stages("corn")
        assert stages is not None
        assert len(stages) == 1
        assert stages[0].bbch_code == "60"

    def test_unknown_crop_returns_none(self, monkeypatch):
        """GIVEN seed data loaded
        WHEN get_stages('unknown_crop') is called
        THEN returns None."""
        monkeypatch.setattr(sd, "_stages", VALID_BBCH_YAML["stages"])

        result = CropCatalogService.get_stages("unknown_crop")
        assert result is None
