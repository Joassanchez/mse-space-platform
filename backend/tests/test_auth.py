"""Tests for API Key authentication dependency.

Verifies that:
- Health and ready endpoints are exempt from auth (200 without key)
- Protected endpoints require valid X-API-Key header
- Invalid API key returns 401
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_health_without_api_key_returns_200(client: AsyncClient) -> None:
    """GIVEN no X-API-Key header, WHEN GET /health, THEN 200."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_ready_without_api_key_returns_200(client: AsyncClient) -> None:
    """GIVEN no X-API-Key header, WHEN GET /ready, THEN 200."""
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


async def test_missing_api_key_returns_401(client: AsyncClient) -> None:
    """GIVEN no X-API-Key header, WHEN calling verify_api_key, THEN raises 401."""
    from backend.core.auth import verify_api_key
    from fastapi import HTTPException

    try:
        await verify_api_key(x_api_key=None)
        assert False, "Expected HTTPException"
    except HTTPException as e:
        assert e.status_code == 401


async def test_wrong_api_key_returns_401(client: AsyncClient) -> None:
    """GIVEN wrong X-API-Key, WHEN calling verify_api_key, THEN raises 401."""
    from backend.core.auth import verify_api_key
    from fastapi import HTTPException

    try:
        await verify_api_key(x_api_key="wrong-key")
        assert False, "Expected HTTPException"
    except HTTPException as e:
        assert e.status_code == 401


async def test_valid_api_key_accepted(client: AsyncClient) -> None:
    """GIVEN valid X-API-Key, WHEN calling verify_api_key, THEN returns the key."""
    from backend.core.auth import verify_api_key
    from backend.tests.conftest import TEST_API_KEY

    result = await verify_api_key(x_api_key=TEST_API_KEY)
    assert result == TEST_API_KEY


async def test_auth_client_receives_200_on_health(auth_client: AsyncClient) -> None:
    """GIVEN valid X-API-Key, WHEN GET /health, THEN 200."""
    response = await auth_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
