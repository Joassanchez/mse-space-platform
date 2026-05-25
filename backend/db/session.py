"""Async SQLAlchemy session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import config

async_engine = create_async_engine(config.DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(bind=async_engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def close_engine() -> None:
    """Dispose of the async engine at shutdown."""
    await async_engine.dispose()
