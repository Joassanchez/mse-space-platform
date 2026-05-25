"""Integration tests for regions API endpoints."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestRegionsEndpoints:
    """Regions API endpoint tests."""

    async def test_list_regions_requires_auth(self, client: AsyncClient) -> None:
        """GIVEN no API key, WHEN GET /api/v1/regions/, THEN 401."""
        response = await client.get("/api/v1/regions/")
        assert response.status_code == 401

    @pytest.mark.skip(reason="Requires DB fixture — covered by test_services.py")
    async def test_list_regions_returns_200_with_auth(self, auth_client: AsyncClient) -> None:
        """GIVEN valid auth, WHEN GET /api/v1/regions/, THEN 200."""
        response = await auth_client.get("/api/v1/regions/")
        assert response.status_code == 200

    @pytest.mark.skip(reason="Requires DB fixture — covered by test_services.py")
    async def test_region_detail_not_found(self, auth_client: AsyncClient) -> None:
        """GIVEN unknown region_id, WHEN GET /api/v1/regions/9999, THEN 404."""
        response = await auth_client.get("/api/v1/regions/9999")
        assert response.status_code == 404

    async def test_region_detail_requires_auth(self, client: AsyncClient) -> None:
        """GIVEN no API key, WHEN GET /api/v1/regions/1, THEN 401."""
        response = await client.get("/api/v1/regions/1")
        assert response.status_code == 401
