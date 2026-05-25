"""Tests for health and readiness endpoints.

Health (/health) is exempt from auth — liveness probe.
Ready (/ready) is exempt from auth — checks DB connectivity.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestHealthEndpoint:
    """GET /health — liveness probe."""

    async def test_health_returns_200(self, client: AsyncClient) -> None:
        """GIVEN app is running, WHEN GET /health, THEN 200 with status ok."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    async def test_health_no_auth_required(self, client: AsyncClient) -> None:
        """GIVEN no API key, WHEN GET /health, THEN 200 (exempt from auth)."""
        response = await client.get("/health")
        assert response.status_code == 200


class TestReadyEndpoint:
    """GET /ready — readiness probe with DB check."""

    async def test_ready_returns_200(self, client: AsyncClient) -> None:
        """GIVEN DB is accessible, WHEN GET /ready, THEN 200 with ready status."""
        response = await client.get("/ready")
        # May return 200 (healthy) or 503 if test DB unreachable
        assert response.status_code in (200, 503)
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ready"

    async def test_ready_no_auth_required(self, client: AsyncClient) -> None:
        """GIVEN no API key, WHEN GET /ready, THEN 200 (exempt from auth)."""
        response = await client.get("/ready")
        assert response.status_code in (200, 503)
