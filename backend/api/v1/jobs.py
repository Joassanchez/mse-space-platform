"""Jobs API endpoints — job management.

WebSocket endpoint registered in main.py at /ws/jobs/{job_id}.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db_session
from backend.schemas.jobs import (
    JobListResponse,
    JobDetailResponse,
    JobTriggerRequest,
    JobTriggerResponse,
)
from backend.services.job_service import (
    get_jobs,
    get_job_detail,
    trigger_job,
    get_job_logs,
)

logger = logging.getLogger("backend.jobs")
router = APIRouter(tags=["jobs"])


@router.get("/jobs/", response_model=JobListResponse)
async def list_jobs(
    status: str | None = Query(None, description="Filter by status"),
    region_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
):
    """List ingestion jobs with optional filters."""
    return await get_jobs(db, status=status, region_id=region_id, page=page, limit=limit)


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
async def job_detail(
    job_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Get full detail for a single ingestion job."""
    result = await get_job_detail(db, job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")
    return result


@router.post("/jobs/trigger/", response_model=JobTriggerResponse, status_code=201)
async def job_trigger(
    body: JobTriggerRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Trigger a new on-demand ingestion job."""
    return await trigger_job(db, body)


@router.get("/jobs/{job_id}/logs/")
async def job_logs(
    job_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Get execution logs for a job."""
    return await get_job_logs(db, job_id)
