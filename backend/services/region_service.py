"""Region service — queries regions table for configured monitoring areas."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Region
from backend.schemas.regions import RegionListItem, RegionDetail


async def get_regions(db: AsyncSession) -> list[RegionListItem]:
    """List all active regions."""
    result = await db.execute(
        select(Region).where(Region.is_active == True).order_by(Region.name)
    )
    regions = result.scalars().all()
    return [
        RegionListItem(
            id=r.id,
            name=r.name,
            region_type=r.region_type,
            country=r.country,
            province=r.province,
            bbox=list(r.bbox) if r.bbox else [],
            is_active=r.is_active,
            created_at=r.created_at,
        )
        for r in regions
    ]


async def get_region(db: AsyncSession, region_id: int) -> RegionDetail | None:
    """Get detail for a single region by its INTEGER id."""
    result = await db.execute(select(Region).where(Region.id == region_id))
    region = result.scalar_one_or_none()
    if not region:
        return None
    return RegionDetail(
        id=region.id,
        name=region.name,
        region_type=region.region_type,
        country=region.country,
        province=region.province,
        bbox=list(region.bbox) if region.bbox else [],
        area_km2=float(region.area_km2) if region.area_km2 else None,
        metadata=region.extra_metadata,
        is_active=region.is_active,
        created_at=region.created_at,
    )


async def get_region_by_name(db: AsyncSession, name: str) -> RegionDetail | None:
    """Get region detail by name (useful for PRD-style string identifiers)."""
    result = await db.execute(select(Region).where(Region.name == name))
    region = result.scalar_one_or_none()
    if not region:
        return None
    return RegionDetail(
        id=region.id,
        name=region.name,
        region_type=region.region_type,
        country=region.country,
        province=region.province,
        bbox=list(region.bbox) if region.bbox else [],
        area_km2=float(region.area_km2) if region.area_km2 else None,
        metadata=region.extra_metadata,
        is_active=region.is_active,
        created_at=region.created_at,
    )
