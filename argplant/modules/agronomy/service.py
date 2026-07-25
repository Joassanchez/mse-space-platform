"""Service layer for the agronomy catalog.

Reads from the in-memory seed data dictionaries loaded at startup.
"""

from argplant.modules.agronomy.models import CropInfo, GrowthStage
from argplant.modules.agronomy.seed_data import get_crops, get_stages


class CropCatalogService:
    """Provides read-only access to the crop catalog and growth stages."""

    @staticmethod
    def list_crops() -> list[CropInfo]:
        """Return all supported crops."""
        crops = get_crops()
        return [
            CropInfo(
                id=crop_id,
                name=crop["name"],
                scientific_name=crop["scientific_name"],
            )
            for crop_id, crop in crops.items()
        ]

    @staticmethod
    def get_stages(crop_id: str) -> list[GrowthStage] | None:
        """Return BBCH growth stages for a crop, or None if unknown."""
        stages_all = get_stages()
        stage_list = stages_all.get(crop_id)
        if stage_list is None:
            return None

        return [GrowthStage(**s) for s in stage_list]
