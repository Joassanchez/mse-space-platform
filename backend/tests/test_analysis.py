"""Integration tests for analysis API endpoints."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestAnalysisEndpoints:
    """Analysis API endpoint tests."""

    async def test_list_analysis_requires_auth(self, client: AsyncClient) -> None:
        """GIVEN no API key, WHEN GET /api/v1/analysis/, THEN 401."""
        response = await client.get("/api/v1/analysis/")
        assert response.status_code == 401

    @pytest.mark.skip(reason="Requires DB fixture — covered by test_services.py")
    async def test_list_analysis_returns_200_with_auth(self, auth_client: AsyncClient) -> None:
        """GIVEN valid auth, WHEN GET /api/v1/analysis/, THEN 200."""
        response = await auth_client.get("/api/v1/analysis/")
        assert response.status_code == 200

    @pytest.mark.skip(reason="Requires DB fixture — covered by test_services.py")
    async def test_analysis_detail_not_found(self, auth_client: AsyncClient) -> None:
        """GIVEN unknown ID, WHEN GET /api/v1/analysis/unknown, THEN 404."""
        response = await auth_client.get("/api/v1/analysis/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    async def test_latest_analysis_requires_auth(self, client: AsyncClient) -> None:
        """GIVEN no API key, WHEN GET /api/v1/analysis/latest/, THEN 401."""
        response = await client.get("/api/v1/analysis/latest/?area=hydric-environmental")
        assert response.status_code == 401

    async def test_analysis_summary_requires_auth(self, client: AsyncClient) -> None:
        """GIVEN no API key, WHEN GET /api/v1/analysis/summary/, THEN 401."""
        response = await client.get("/api/v1/analysis/summary/")
        assert response.status_code == 401
