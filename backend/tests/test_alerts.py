"""Tests for Alerts API endpoints and alert schemas."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from backend.schemas.alerts import (
    AlertItem,
    AlertListResponse,
    AlertDetailResponse,
    ActiveAlertCountResponse,
)
from backend.services.alert_service import get_alerts, get_alert_detail, get_active_alert_count

pytestmark = pytest.mark.asyncio


class TestAlertSchemas:
    """Alert Pydantic schema tests."""

    async def test_alert_item_minimal(self) -> None:
        """GIVEN required fields, THEN AlertItem valid."""
        item = AlertItem(
            id=1,
            alert_type="drought",
            severity="critical",
            title="Severe drought detected",
            status="active",
            region_id=1,
        )
        assert item.id == 1
        assert item.severity == "critical"

    async def test_active_alert_count(self) -> None:
        """GIVEN severity counts, THEN response is correct."""
        counts = ActiveAlertCountResponse(critical=2, severe=3, warning=5, total=10)
        assert counts.critical == 2
        assert counts.total == 10

    async def test_active_alert_count_defaults(self) -> None:
        """GIVEN no counts, THEN all default to zero."""
        counts = ActiveAlertCountResponse()
        assert counts.critical == 0
        assert counts.total == 0


class TestAlertService:
    """Alert service tests with mocked DB."""

    async def test_get_alerts_returns_list(self) -> None:
        """GIVEN alerts in DB, THEN returns paginated list."""
        db = AsyncMock()

        # Mock count
        count_result = MagicMock()
        count_result.scalar.return_value = 2
        # Mock data
        data_result = MagicMock()
        data_result.fetchall.return_value = [
            (1, "drought", "critical", "Alert 1", "active", 1, "Córdoba", None, None),
            (2, "flood", "severe", "Alert 2", "active", 1, "Córdoba", None, None),
        ]
        db.execute.side_effect = [count_result, data_result]

        result = await get_alerts(db, region_id=1)
        assert len(result.items) == 2
        assert result.items[0].title == "Alert 1"

    async def test_get_alert_detail_not_found(self) -> None:
        """GIVEN no alert, THEN returns None."""
        db = AsyncMock()
        result = MagicMock()
        result.fetchone.return_value = None
        db.execute.return_value = result

        alert = await get_alert_detail(db, 999)
        assert alert is None


async def test_list_alerts_requires_auth(client: AsyncClient) -> None:
    """GIVEN no API key, WHEN GET /api/v1/alerts/, THEN 401."""
    response = await client.get("/api/v1/alerts/")
    assert response.status_code == 401

async def test_alert_count_requires_auth(client: AsyncClient) -> None:
    """GIVEN no API key, WHEN GET /api/v1/alerts/active/count/, THEN 401."""
    response = await client.get("/api/v1/alerts/active/count/")
    assert response.status_code == 401

async def test_alert_detail_requires_auth(client: AsyncClient) -> None:
    """GIVEN no API key, WHEN GET /api/v1/alerts/1, THEN 401."""
    response = await client.get("/api/v1/alerts/1")
    assert response.status_code == 401

async def test_acknowledge_requires_auth(client: AsyncClient) -> None:
    """GIVEN no API key, WHEN PATCH /api/v1/alerts/1/acknowledge/, THEN 401."""
    response = await client.patch("/api/v1/alerts/1/acknowledge/")
    assert response.status_code == 401

async def test_sse_stream_requires_auth(client: AsyncClient) -> None:
    """GIVEN no API key, WHEN GET /api/v1/alerts/stream/, THEN 401."""
    response = await client.get("/api/v1/alerts/stream/")
    assert response.status_code == 401
