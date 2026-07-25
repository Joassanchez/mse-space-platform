"""FastAPI router for the ingestion pipeline.

Exposes the job status endpoint backed by arq's Redis job store.
"""

import logging

import arq
from arq.connections import RedisSettings
from arq.jobs import Job, JobStatus
from fastapi import APIRouter, HTTPException

from argplant.modules.ingestion.models import JobStatusResponse
from argplant.shared.config import settings

logger = logging.getLogger("argplant.ingestion")

router = APIRouter(tags=["ingestion"])

# Shared arq connection pool for job status lookups.
_arq_pool: arq.ArqRedis | None = None


async def _get_arq() -> arq.ArqRedis:
    """Return a shared arq Redis connection pool."""
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await arq.create_pool(
            RedisSettings().from_dsn(settings.REDIS_URL)
        )
    return _arq_pool


# ---------------------------------------------------------------------------
# Job status endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Return the status and result of an async ingestion job.

    Queries arq's Redis job store for the latest job state. Returns 404
    if the job ID is not found.
    """
    arq_redis = await _get_arq()

    job = Job(job_id, arq_redis)
    status: JobStatus | None = await job.info()

    if status is None:
        raise HTTPException(
            status_code=404, detail=f"Job '{job_id}' not found"
        )

    # Map arq status to a consistent string and extract progress/result.
    status_str = _map_arq_status(status)

    # Try to get result info for completed/failed jobs.
    result_info = await job.result_info()
    result_data: dict | None = None
    progress: int | None = None

    if result_info is not None:
        result_data = result_info.result if result_info.success else None
        if isinstance(result_info.result, dict):
            progress = result_info.result.get("progress")
        if not result_info.success:
            result_data = {
                "error": str(result_info.result) if result_info.result else "unknown"
            }

    return JobStatusResponse(
        job_id=job_id,
        status=status_str,
        progress=progress,
        result=result_data,
        created_at=status.enqueue_time,
        updated_at=status.finish_time or status.start_time,
    )


def _map_arq_status(status: JobStatus) -> str:
    """Translate arq's JobStatus to a simple status string."""
    if status.success:
        return "completed"
    if status.finish_time and not status.success:
        return "failed"
    if status.start_time:
        return "running"
    return "queued"
