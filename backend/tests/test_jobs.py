"""Tests for Jobs API endpoints and schemas."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from backend.schemas.jobs import JobItem, JobListResponse, JobTriggerRequest, JobTriggerResponse
from backend.services.job_service import get_jobs, get_job_detail
from backend.core.ws_manager import ConnectionManager

pytestmark = pytest.mark.asyncio


class TestJobSchemas:
    """Job Pydantic schema tests."""

    async def test_job_item_minimal(self) -> None:
        """GIVEN required fields, THEN JobItem valid."""
        item = JobItem(id="job-001", status="completed")
        assert item.id == "job-001"
        assert item.status == "completed"

    async def test_job_list_response(self) -> None:
        """GIVEN items, THEN list response wraps them."""
        items = [JobItem(id="j1", status="pending"), JobItem(id="j2", status="running")]
        resp = JobListResponse(items=items, total=2)
        assert len(resp.items) == 2
        assert resp.total == 2

    async def test_job_trigger_request(self) -> None:
        """GIVEN valid trigger request, THEN serializes correctly."""
        req = JobTriggerRequest(region_id="1", date_from="2024-01-01", date_to="2024-01-15")
        assert req.region_id == "1"
        assert req.date_from == "2024-01-01"


class TestJobService:
    """Job service tests with mocked DB."""

    async def test_get_jobs_returns_list(self) -> None:
        """GIVEN jobs in DB, THEN returns paginated list."""
        db = AsyncMock()
        count_mock = MagicMock()
        count_mock.scalar.return_value = 2
        data_mock = MagicMock()
        data_mock.fetchall.return_value = [
            ("j1", "completed", "region-1", 1, "2024-01-01", "2024-01-15", None, None, None),
            ("j2", "running", "region-1", 1, "2024-01-01", "2024-01-15", None, None, None),
        ]
        db.execute.side_effect = [count_mock, data_mock]

        result = await get_jobs(db)
        assert len(result.items) == 2
        assert result.items[0].id == "j1"

    async def test_get_job_detail_not_found(self) -> None:
        """GIVEN no job, THEN returns None."""
        db = AsyncMock()
        result = MagicMock()
        result.fetchone.return_value = None
        db.execute.return_value = result
        job = await get_job_detail(db, "unknown")
        assert job is None


class TestWebSocketManager:
    """WebSocket ConnectionManager tests."""

    async def test_connect_disconnect(self) -> None:
        """GIVEN WS connects, THEN manager tracks and removes it."""
        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect(ws, "job-1")
        assert mgr.active_connections == 1
        mgr.disconnect(ws, "job-1")
        assert mgr.active_connections == 0

    async def test_broadcast_to_job(self) -> None:
        """GIVEN connected clients, THEN broadcast sends to all."""
        mgr = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await mgr.connect(ws1, "job-1")
        await mgr.connect(ws2, "job-1")
        await mgr.broadcast_to_job("job-1", "test", {"msg": "hello"})
        assert ws1.send_text.called
        assert ws2.send_text.called

    async def test_broadcast_to_unknown_job(self) -> None:
        """GIVEN no connected clients, THEN broadcast does nothing."""
        mgr = ConnectionManager()
        await mgr.broadcast_to_job("unknown", "test", {})  # should not raise


class TestJobAuth:
    """Job endpoint auth tests."""

    async def test_list_jobs_requires_auth(self, client: AsyncClient) -> None:
        """GIVEN no API key, WHEN GET /api/v1/jobs/, THEN 401."""
        response = await client.get("/api/v1/jobs/")
        assert response.status_code == 401

    async def test_job_detail_requires_auth(self, client: AsyncClient) -> None:
        """GIVEN no API key, WHEN GET /api/v1/jobs/job-1, THEN 401."""
        response = await client.get("/api/v1/jobs/job-1")
        assert response.status_code == 401

    async def test_job_trigger_requires_auth(self, client: AsyncClient) -> None:
        """GIVEN no API key, WHEN POST /api/v1/jobs/trigger/, THEN 401."""
        response = await client.post("/api/v1/jobs/trigger/", json={})
        assert response.status_code == 401

    async def test_job_logs_requires_auth(self, client: AsyncClient) -> None:
        """GIVEN no API key, WHEN GET /api/v1/jobs/job-1/logs/, THEN 401."""
        response = await client.get("/api/v1/jobs/job-1/logs/")
        assert response.status_code == 401
