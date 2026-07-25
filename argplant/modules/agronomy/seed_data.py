"""Startup seed loader for agronomy data.

Reads crops.yaml and bbch_stages.yaml from data/agronomy/ and populates
module-level dictionaries. Called from FastAPI lifespan at startup.
"""

import logging
from pathlib import Path

import yaml

logger = logging.getLogger("argplant.agronomy")

# Module-level cache populated at startup
_crops: dict[str, dict] = {}
_stages: dict[str, list[dict]] = {}

FIXTURE_DIR = Path("data/agronomy")


def load_agronomy_seeds() -> None:
    """Load crop and BBCH stage fixtures into in-memory dictionaries.

    Raises FileNotFoundError if fixtures are missing.
    Raises yaml.YAMLError if fixtures are malformed.
    """
    global _crops, _stages

    crops_file = FIXTURE_DIR / "crops.yaml"
    stages_file = FIXTURE_DIR / "bbch_stages.yaml"

    if not crops_file.exists():
        msg = f"Agronomy fixture not found: {crops_file}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    if not stages_file.exists():
        msg = f"Agronomy fixture not found: {stages_file}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    with crops_file.open(encoding="utf-8") as fh:
        crops_data = yaml.safe_load(fh)

    with stages_file.open(encoding="utf-8") as fh:
        stages_data = yaml.safe_load(fh)

    # Build crops lookup: {id: crop_dict}
    _crops = {c["id"]: c for c in crops_data.get("crops", [])}
    logger.info("Loaded %d crops from %s", len(_crops), crops_file)

    # Build stages lookup: {crop_id: [stage_dict, ...]}
    _stages = stages_data.get("stages", {})
    for crop_id, stage_list in _stages.items():
        logger.info("Loaded %d BBCH stages for crop '%s' from %s", len(stage_list), crop_id, stages_file)


def get_crops() -> dict[str, dict]:
    """Return the in-memory crop catalog (id → crop dict)."""
    return _crops


def get_stages() -> dict[str, list[dict]]:
    """Return the in-memory BBCH stage catalog (crop_id → [stage_dict])."""
    return _stages
