"""Communication router — alerts REST API + SSE stream.

Endpoints:
  POST   /api/v1/alerts          — Create alert (with dedup)
  GET    /api/v1/alerts          — List active alerts
  POST   /api/v1/alerts/{id}/acknowledge — Acknowledge an alert
  GET    /api/v1/alerts/stream   — SSE real-time stream
"""

from __future__ import annotations

import asyncio
import json
import logging

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from argplant.modules.communication.models import AlertCreate, AlertResponse
from argplant.modules.communication.service import AlertService
from argplant.shared.config import settings
from argplant.shared.database import get_session

logger = logging.getLogger("argplant.communication")

router = APIRouter(tags=["communication"])


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@router.post("/alerts", response_model=AlertResponse, status_code=201)
async def create_alert(
    data: AlertCreate,
    session: AsyncSession = Depends(get_session),
) -> AlertResponse:
    """Create a new alert. Deduplicates within an 8-hour window."""
    if data.severity not in {"info", "warning", "severe", "critical"}:
        raise HTTPException(status_code=400, detail=f"Invalid severity: {data.severity}")
    if data.status not in {"active", "acknowledged", "resolved"}:
        raise HTTPException(status_code=400, detail=f"Invalid status: {data.status}")

    svc = AlertService(session)
    result = await svc.create(data)
    await session.commit()
    return result


@router.get("/alerts", response_model=list[AlertResponse])
async def list_alerts(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
) -> list[AlertResponse]:
    """Return currently active alerts, newest first."""
    svc = AlertService(session)
    return await svc.get_active(limit=limit)


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: int,
    session: AsyncSession = Depends(get_session),
) -> AlertResponse:
    """Mark an alert as acknowledged."""
    svc = AlertService(session)
    result = await svc.acknowledge(alert_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    await session.commit()
    return result


# ---------------------------------------------------------------------------
# SSE Stream (real-time push via PostgreSQL LISTEN/NOTIFY)
# ---------------------------------------------------------------------------


@router.get("/alerts/stream")
async def alert_stream():
    """Server-Sent Events stream — pushes new alerts in real time.

    Listens to PostgreSQL `new_alert` channel and forwards alerts to
    connected SSE clients as `data: {json}\n\n`.
    """
    async def event_generator():
        conn = await asyncpg.connect(
            dsn=settings.DATABASE_URL.replace("+asyncpg", ""),
        )
        await conn.add_listener("new_alert", lambda conn, pid, channel, payload: None)

        try:
            # Send initial heartbeat
            yield f"event: connected\ndata: {json.dumps({'status': 'connected'})}\n\n"

            while True:
                try:
                    # Wait for notifications with a keepalive timeout
                    notification = await asyncio.wait_for(
                        conn.get_notify_wrapper().__anext__(),
                        timeout=30.0,
                    )
                    if notification:
                        yield f"data: {notification.payload}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive comment to prevent proxy timeouts
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await conn.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
