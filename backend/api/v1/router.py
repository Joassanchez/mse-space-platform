"""Aggregates all v1 API routers under /api/v1 prefix with auth."""

from fastapi import APIRouter, Depends

from backend.core.auth import verify_api_key
from backend.api.v1.regions import router as regions_router
from backend.api.v1.analysis import router as analysis_router
from backend.api.v1.geo import router as geo_router
from backend.api.v1.alerts import router as alerts_router
from backend.api.v1.jobs import router as jobs_router

v1_router = APIRouter(prefix="/api/v1", dependencies=[Depends(verify_api_key)])
v1_router.include_router(regions_router)
v1_router.include_router(analysis_router)
v1_router.include_router(geo_router)
v1_router.include_router(alerts_router)
v1_router.include_router(jobs_router)
