"""Integration test for the /health endpoint."""

import pytest


@pytest.mark.asyncio
async def test_health_returns_200(test_client):
    """The /health endpoint must return 200 with {"status": "ok"}."""
    response = await test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
