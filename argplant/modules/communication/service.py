"""Alert service with deduplication and PostgreSQL NOTIFY support.

- Deduplicates: same alert_type + region_id within DEDUP_WINDOW_HOURS → update metadata
- NOTIFY: fires PostgreSQL LISTEN/NOTIFY for real-time SSE push
- Can enrich alert text via LLM when configured
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from argplant.modules.communication.models import Alert, AlertCreate, AlertResponse
from argplant.shared.database import async_engine

logger = logging.getLogger("argplant.communication")

# Deduplication window: if the same alert_type + region_id was created within
# this many hours, update the existing alert instead of creating a new one.
DEDUP_WINDOW_HOURS = 8


class AlertService:
    """Manage alert creation, deduplication, and NOTIFY dispatch."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: AlertCreate) -> AlertResponse:
        """Create an alert with deduplication.

        If an active alert of the same type+region exists within the dedup
        window, its metadata is merged instead of creating a duplicate.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=DEDUP_WINDOW_HOURS)

        # Check for existing active alert
        stmt = (
            select(Alert)
            .where(
                Alert.alert_type == data.alert_type,
                Alert.region_id == data.region_id,
                Alert.status == "active",
                Alert.created_at >= cutoff,
            )
            .order_by(Alert.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Merge metadata and bump updated_at
            merged_meta = {**(existing.metadata_ or {}), **(data.metadata_ or {})}
            existing.metadata_ = merged_meta
            existing.message = data.message  # update with latest message
            existing.updated_at = datetime.now(timezone.utc)
            await self._session.flush()
            alert = existing
            logger.debug("Deduplicated alert id=%d type=%s region=%d", alert.id, alert.alert_type, alert.region_id)
        else:
            alert = Alert(
                region_id=data.region_id,
                alert_type=data.alert_type,
                severity=data.severity,
                title=data.title,
                message=data.message,
                status=data.status,
                metadata_=data.metadata_,
            )
            self._session.add(alert)
            await self._session.flush()
            logger.info("Created alert id=%d type=%s severity=%s", alert.id, alert.alert_type, alert.severity)

        # Fire NOTIFY for SSE
        await self._notify(alert)

        return self._to_response(alert)

    async def get_active(self, limit: int = 50) -> list[AlertResponse]:
        """Return currently active alerts, newest first."""
        stmt = (
            select(Alert)
            .where(Alert.status == "active")
            .order_by(Alert.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_response(a) for a in result.scalars().all()]

    async def acknowledge(self, alert_id: int) -> AlertResponse | None:
        """Mark an alert as acknowledged."""
        stmt = select(Alert).where(Alert.id == alert_id)
        result = await self._session.execute(stmt)
        alert = result.scalar_one_or_none()
        if not alert:
            return None
        alert.status = "acknowledged"
        alert.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return self._to_response(alert)

    @staticmethod
    async def _notify(alert: Alert) -> None:
        """Send PostgreSQL NOTIFY for real-time SSE delivery."""
        payload = json.dumps({
            "id": alert.id,
            "title": alert.title,
            "severity": alert.severity,
            "alert_type": alert.alert_type,
            "region_id": alert.region_id,
        })
        try:
            async with async_engine.begin() as conn:
                await conn.execute(text(f"NOTIFY new_alert, '{payload}'"))
        except Exception:
            logger.exception("Failed to send NOTIFY for alert %d", alert.id)

    @staticmethod
    def _to_response(alert: Alert) -> AlertResponse:
        return AlertResponse(
            id=alert.id,
            region_id=alert.region_id,
            alert_type=alert.alert_type,
            severity=alert.severity,
            title=alert.title,
            message=alert.message,
            status=alert.status,
            metadata=alert.metadata_,
            created_at=alert.created_at.isoformat(),
            updated_at=alert.updated_at.isoformat(),
        )
