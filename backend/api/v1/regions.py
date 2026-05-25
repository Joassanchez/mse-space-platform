"""Regions API endpoints — read-only region metadata."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db_session
from backend.schemas.regions import RegionListResponse, RegionDetail
from backend.services.region_service import get_regions, get_region, get_region_by_name

router = APIRouter(tags=["regions"])


@router.get("/regions/", response_model=RegionListResponse)
async def list_regions(
    db: AsyncSession = Depends(get_db_session),
):
    """List all active regions with basic metadata."""
    items = await get_regions(db)
    return RegionListResponse(items=items)


@router.get("/regions/{region_id}", response_model=RegionDetail)
async def get_region_detail(
    region_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Get full detail for a region. Accepts INTEGER id or name lookup."""
    # Try parsing as integer ID first
    try:
        rid = int(region_id)
        region = await get_region(db, rid)
    except ValueError:
        # Fallback: lookup by name (e.g. "cordoba_pilot")
        region = await get_region_by_name(db, region_id)

    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    return region
