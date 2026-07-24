"""Redis client wrapper with JSON helpers and stale-cache support."""

import json
from typing import Any

import redis.asyncio as aioredis

from argplant.shared.config import settings

# Stale cache TTL multiplier — how long stale data remains available after expiration
STALE_TTL_MULTIPLIER = 24


async def _get_redis() -> aioredis.Redis:
    """Create a new Redis connection. Used as a factory."""
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def get_json(redis: aioredis.Redis, key: str) -> dict[str, Any] | None:
    """Retrieve a JSON value from cache. Returns None on miss."""
    raw = await redis.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def set_json(
    redis: aioredis.Redis,
    key: str,
    value: dict[str, Any],
    ttl: int,
) -> None:
    """Store a JSON value in cache with TTL. Also stores a stale copy with extended TTL."""
    payload = json.dumps(value, default=str)
    stale_key = _stale_key(key)
    async with redis.pipeline() as pipe:
        pipe.set(key, payload, ex=ttl)
        pipe.set(stale_key, payload, ex=ttl * STALE_TTL_MULTIPLIER)
        await pipe.execute()


async def get_stale(redis: aioredis.Redis, key: str) -> dict[str, Any] | None:
    """Retrieve stale cached data (extended TTL copy). Returns None if not even stale data exists."""
    raw = await redis.get(_stale_key(key))
    if raw is None:
        return None
    return json.loads(raw)


async def delete(redis: aioredis.Redis, key: str) -> None:
    """Delete both fresh and stale cache entries for a key."""
    async with redis.pipeline() as pipe:
        pipe.delete(key, _stale_key(key))
        await pipe.execute()


def _stale_key(key: str) -> str:
    """Generate the stale-cache key for a given cache key."""
    return f"{key}:stale"
