"""Alerts API endpoints — active alert management + SSE stream."""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from backend.dependencies import get_db_session
from backend.schemas.alerts import (
    AlertListResponse,
    AlertDetailResponse,
    ActiveAlertCountResponse,
)
from backend.services.alert_service import (
    get_alerts,
    get_alert_detail,
    get_active_alert_count,
    acknowledge_alert,
)

logger = logging.getLogger("backend.alerts")
router = APIRouter(tags=["alerts"])


@router.get("/alerts/", response_model=AlertListResponse)
async def list_alerts(
    region_id: int | None = Query(None),
    severity: str | None = Query(None, description="Filter: info, warning, severe, critical"),
    status: str | None = Query("active", description="Filter by status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
):
    """List alerts ordered by severity (critical first) then date."""
    return await get_alerts(
        db,
        region_id=region_id,
        severity=severity,
        status=status,
        page=page,
        limit=limit,
    )


@router.get("/alerts/active/count/", response_model=ActiveAlertCountResponse)
async def active_alert_count(
    region_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db_session),
):
    """Return active alert counts grouped by severity."""
    return await get_active_alert_count(db, region_id=region_id)


@router.get("/alerts/{alert_id}", response_model=AlertDetailResponse)
async def alert_detail(
    alert_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """Get full detail for a single alert."""
    result = await get_alert_detail(db, alert_id)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


@router.patch("/alerts/{alert_id}/acknowledge/")
async def acknowledge_alert_endpoint(
    alert_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """Mark an active alert as acknowledged."""
    updated = await acknowledge_alert(db, alert_id)
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Alert not found or already acknowledged",
        )
    return {"status": "acknowledged", "alert_id": alert_id}


@router.get("/alerts/stream/")
async def alert_sse_stream(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """SSE stream for real-time alert notifications.

    Uses PostgreSQL LISTEN/NOTIFY via asyncpg connection.
    Falls back to polling if LISTEN/NOTIFY unavailable.
    """
    async def event_generator():
        try:
            # Try LISTEN/NOTIFY approach
            raw_conn = await db.connection()
            await raw_conn.exec_driver_sql("LISTEN new_alert")
            logger.info("SSE stream: listening for new alerts")

            while True:
                if await request.is_disconnected():
                    break

                # Check for notifications (non-blocking poll)
                conn = await raw_conn.get_raw_connection()
                try:
                    notifications = conn.driver_connection.notifications
                    while notifications:
                        notification = notifications.pop(0)
                        yield {
                            "event": "new_alert",
                            "data": notification.payload or "{}",
                        }
                except Exception:
                    pass

                # Fallback polling every 5s if LISTEN/NOTIFY fails
                import asyncio
                await asyncio.sleep(5)

        except Exception as e:
            logger.warning("SSE LISTEN/NOTIFY failed, falling back to polling: %s", e)
            # Fallback: poll every 10 seconds
            import asyncio
            last_check = datetime.utcnow()
            while True:
                if await request.is_disconnected():
                    break
                try:
                    alerts = await get_alerts(db, status="active", limit=5)
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps({
                            "active_alerts": alerts.total,
                            "timestamp": datetime.utcnow().isoformat(),
                        }),
                    }
                except Exception:
                    pass
                await asyncio.sleep(10)

    return EventSourceResponse(event_generator())
