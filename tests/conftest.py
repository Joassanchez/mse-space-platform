"""Shared test fixtures for ARGPLANT Data Service.

Provides async fixtures for test database, Redis, HTTP client, and mock settings.
"""

from collections.abc import AsyncGenerator

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from argplant.main import app
from argplant.shared.config import Settings
from argplant.shared.database import Base, get_session


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_engine():
    """Create an async engine connected to an in-memory SQLite database."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session backed by the test database."""
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Redis fixture (fakeredis — no real Redis needed)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_redis():
    """Yield a fakeredis client that mimics redis.asyncio."""
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield redis
    await redis.flushall()
    await redis.aclose()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# HTTP client fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_client(test_session) -> AsyncGenerator[AsyncClient, None]:
    """Yield an httpx AsyncClient bound to the FastAPI app with test overrides."""

    async def override_get_session():
        yield test_session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Settings fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_settings() -> Settings:
    """Return a Settings instance with test-safe defaults."""
    return Settings(
        DATABASE_URL="sqlite+aiosqlite://",
        REDIS_URL="redis://localhost:6379/0",
        OPENWEATHER_API_KEY="test-key",
        RATE_LIMIT_REQUESTS=5,
        RATE_LIMIT_WINDOW_SECONDS=60,
        SATELLITE_STORAGE_PATH="/tmp/argplant-test",
    )
