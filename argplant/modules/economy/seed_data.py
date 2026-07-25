"""Startup seed loader for economy product/port mappings.

Reads products.yaml and ports.yaml from data/economy/ and populates
module-level dictionaries. Called from FastAPI lifespan at startup.
"""

import logging
from pathlib import Path

import yaml

logger = logging.getLogger("argplant.economy")

# Module-level caches populated at startup
_product_map: dict[int, str] = {}  # product_id → product_name
_product_ids: set[int] = set()
_port_map: dict[int, str] = {}  # puerto_id → port_name
_port_ids: set[int] = set()

FIXTURE_DIR = Path("data/economy")


def load_economy_seeds() -> None:
    """Load product and port ID mappings into in-memory dictionaries.

    Raises FileNotFoundError if fixtures are missing.
    Raises yaml.YAMLError if fixtures are malformed.
    """
    global _product_map, _product_ids, _port_map, _port_ids

    products_file = FIXTURE_DIR / "products.yaml"
    ports_file = FIXTURE_DIR / "ports.yaml"

    if not products_file.exists():
        msg = f"Economy fixture not found: {products_file}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    if not ports_file.exists():
        msg = f"Economy fixture not found: {ports_file}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    with products_file.open(encoding="utf-8") as fh:
        products_data = yaml.safe_load(fh)

    with ports_file.open(encoding="utf-8") as fh:
        ports_data = yaml.safe_load(fh)

    _product_map = {p["product_id"]: p["name"] for p in products_data.get("products", [])}
    _product_ids = set(_product_map.keys())
    logger.info("Loaded %d products from %s", len(_product_map), products_file)

    _port_map = {p["puerto_id"]: p["name"] for p in ports_data.get("ports", [])}
    _port_ids = set(_port_map.keys())
    logger.info("Loaded %d ports from %s", len(_port_map), ports_file)


def get_product_map() -> dict[int, str]:
    """Return the in-memory product ID → name mapping."""
    return _product_map


def get_port_map() -> dict[int, str]:
    """Return the in-memory port ID → name mapping."""
    return _port_map


def is_valid_product(product_id: int) -> bool:
    """Check whether a product ID is recognised."""
    return product_id in _product_ids


def is_valid_port(port_id: int) -> bool:
    """Check whether a port ID is recognised."""
    return port_id in _port_ids


def valid_product_ids() -> list[int]:
    """Return sorted list of valid product IDs."""
    return sorted(_product_ids)
