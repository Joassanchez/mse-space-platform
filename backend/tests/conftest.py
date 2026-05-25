"""Async pytest fixtures for backend API tests."""

import os
from collections.abc import AsyncGenerator

# CRITICAL: Set test env vars BEFORE any backend imports
# Otherwise config singleton loads with production values
_TEST_API_KEY = "test-secret-key-12345"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://mse_user:mse_pass@postgres:5432/mse_platform"
os.environ["REDIS_URL"] = "redis://localhost:6379/2"
os.environ["API_KEY"] = _TEST_API_KEY
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import create_app

# Fixed test API key — used in all test assertions
TEST_API_KEY = _TEST_API_KEY


@pytest.fixture(autouse=True)
def reset_env():
    """Ensure env stays set for all tests (in case other fixtures modify it)."""
    yield


@pytest.fixture
def test_app():
    """Create a test FastAPI application with overridden dependencies."""
    app = create_app()
    yield app


@pytest.fixture
async def client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for testing the FastAPI app."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client with valid API key header pre-configured."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": TEST_API_KEY},
    ) as ac:
        yield ac
