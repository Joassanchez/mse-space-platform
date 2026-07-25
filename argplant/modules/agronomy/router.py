"""FastAPI router for the agronomy module.

Exposes crop catalog and growth stage endpoints. All data is served from
in-memory seed dictionaries loaded at startup.
"""

from fastapi import APIRouter, HTTPException

from argplant.modules.agronomy.models import CropListResponse, GrowthStagesResponse
from argplant.modules.agronomy.service import CropCatalogService

router = APIRouter(tags=["agronomy"])


@router.get("/crops")
async def list_crops() -> CropListResponse:
    """Return all supported crops with their scientific names."""
    crops = CropCatalogService.list_crops()
    return CropListResponse(crops=crops)


@router.get("/crops/{crop_id}/stages")
async def get_crop_stages(crop_id: str) -> GrowthStagesResponse:
    """Return BBCH growth stages for a specific crop."""
    stages = CropCatalogService.get_stages(crop_id)
    if stages is None:
        raise HTTPException(
            status_code=404,
            detail=f"Crop '{crop_id}' not found. Supported crops: soy, corn",
        )
    return GrowthStagesResponse(crop_id=crop_id, stages=stages)
