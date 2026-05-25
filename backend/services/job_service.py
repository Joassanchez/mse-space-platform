"""Job service — queries ingestion_jobs table.

Aligned with actual DB schema from migrations/001_create_tables.sql.
"""

from datetime import datetime, timezone

from sqlalchemy import func, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.schemas.jobs import (
    JobItem,
    JobListResponse,
    JobDetailResponse,
    JobTriggerRequest,
    JobTriggerResponse,
)


async def get_jobs(
    db: AsyncSession,
    status: str | None = None,
    region_id: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> JobListResponse:
    """List ingestion jobs with optional filters."""
    conditions = ["1=1"]
    params: dict = {}

    if status:
        conditions.append("ij.status = :status")
        params["status"] = status
    if region_id:
        conditions.append("ij.region_id = :region_id")
        params["region_id"] = region_id

    where = " AND ".join(conditions)
    offset = (page - 1) * limit

    # Count
    count_sql = f"SELECT COUNT(*) FROM ingestion_jobs ij WHERE {where}"
    count_result = await db.execute(text(count_sql), params)
    total = count_result.scalar() or 0

    # Data
    data_sql = f"""
        SELECT ij.id, ij.status, ij.region_id, ij.source_id,
               ij.date_from::text, ij.date_to::text,
               ij.started_at, ij.finished_at, ij.created_at
        FROM ingestion_jobs ij
        WHERE {where}
        ORDER BY ij.created_at DESC
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = limit
    params["offset"] = offset
    result = await db.execute(text(data_sql), params)
    rows = result.fetchall()

    items = [
        JobItem(
            id=row[0],
            status=row[1],
            region_id=row[2],
            source_id=row[3],
            date_from=row[4],
            date_to=row[5],
            started_at=row[6],
            finished_at=row[7],
            created_at=row[8],
        )
        for row in rows
    ]

    return JobListResponse(items=items, total=total)


async def get_job_detail(
    db: AsyncSession,
    job_id: str,
) -> JobDetailResponse | None:
    """Get full detail for a single ingestion job."""
    sql = """
        SELECT ij.id, ij.status, ij.region_id, ij.source_id,
               ij.date_from::text, ij.date_to::text,
               ij.started_at, ij.finished_at, ij.created_at,
               ij.error_message, ij.ready_for_etl, ij.search_only
        FROM ingestion_jobs ij
        WHERE ij.id = :job_id
    """
    result = await db.execute(text(sql), {"job_id": job_id})
    row = result.fetchone()
    if not row:
        return None

    return JobDetailResponse(
        id=row[0],
        status=row[1],
        region_id=row[2],
        source_id=row[3],
        date_from=row[4],
        date_to=row[5],
        started_at=row[6],
        finished_at=row[7],
        created_at=row[8],
        error_message=row[9],
        ready_for_etl=row[10],
        search_only=row[11],
    )


async def trigger_job(
    db: AsyncSession,
    request: JobTriggerRequest,
) -> JobTriggerResponse:
    """Create a new on-demand ingestion job."""
    from uuid import uuid4

    from sqlalchemy import text as sql_text

    job_id = f"on-demand-{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    from datetime import date as date_type
    await db.execute(
        sql_text("""
            INSERT INTO ingestion_jobs
                (id, source_id, region_id, date_from, date_to, bbox, status,
                 ready_for_etl, search_only, created_at)
            VALUES
                (:id, 1, :region_id, :date_from, :date_to,
                 :bbox, 'pending',
                 false, false, :created_at)
        """),
        {
            "id": job_id,
            "region_id": request.region_id,
            "date_from": date_type.fromisoformat(request.date_from),
            "date_to": date_type.fromisoformat(request.date_to),
            "bbox": request.bbox or [0, 0, 0, 0],
            "created_at": now,
        },
    )
    await db.commit()

    return JobTriggerResponse(
        id=job_id,
        status="pending",
        region_id=request.region_id,
        date_from=request.date_from,
        date_to=request.date_to,
        created_at=now,
    )


async def get_job_logs(
    db: AsyncSession,
    job_id: str,
) -> list[dict]:
    """Get execution logs for a job from audit_logs."""
    sql = """
        SELECT al.created_at, al.action, al.message, al.metadata
        FROM audit_logs al
        WHERE al.entity_type = 'ingestion_job'
          AND al.entity_id = :job_id
        ORDER BY al.created_at ASC
        LIMIT 100
    """
    result = await db.execute(text(sql), {"job_id": job_id})
    rows = result.fetchall()
    return [
        {"timestamp": row[0], "action": row[1], "message": row[2], "metadata": row[3]}
        for row in rows
    ]
