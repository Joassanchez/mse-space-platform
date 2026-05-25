"""Redis cache layer for read-heavy endpoints.

Provides TTL-based caching with pattern-based invalidation.
Cache key format: {prefix}:{region}:{param} (e.g. analysis:latest:cordoba)
"""

from typing import Any

# TTL constants in seconds (matches PRD Section 8)
TTL_ANALYSIS = 300       # 5 min
TTL_GEO = 600            # 10 min
TTL_ALERTS_COUNT = 60    # 1 min
TTL_REGIONS = 3600       # 60 min

TTL_BY_PREFIX: dict[str, int] = {
    "analysis": TTL_ANALYSIS,
    "geo": TTL_GEO,
    "alerts:count": TTL_ALERTS_COUNT,
    "regions": TTL_REGIONS,
}


class CacheManager:
    """Async Redis cache wrapper. Gracefully handles missing Redis."""

    def __init__(self, redis_client: Any | None = None) -> None:
        self._redis = redis_client

    async def get(self, key: str) -> Any | None:
        """Get cached value by key. Returns None if miss or Redis unavailable."""
        if not self._redis:
            return None
        try:
            import json
            val = await self._redis.get(key)
            return json.loads(val) if val else None
        except Exception:
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set cached value with TTL. Silently ignores if Redis unavailable."""
        if not self._redis:
            return
        try:
            import json
            await self._redis.setex(key, ttl, json.dumps(value, default=str))
        except Exception:
            pass

    async def invalidate(self, pattern: str) -> None:
        """Invalidate all keys matching pattern (e.g. 'geo:*:cordoba:*')."""
        if not self._redis:
            return
        try:
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(cursor=cursor, match=pattern)
                if keys:
                    await self._redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception:
            pass

    @staticmethod
    def make_key(prefix: str, region: str | None = None, *suffixes: str) -> str:
        """Build a cache key like 'geo:soil-moisture:cordoba:2024-01-15'."""
        parts = [prefix]
        if region:
            parts.append(region)
        parts.extend(suffixes)
        return ":".join(parts)

    @staticmethod
    def get_ttl(prefix: str) -> int:
        """Get TTL for a cache prefix. Falls back to 300s."""
        return TTL_BY_PREFIX.get(prefix, 300)


# Singleton for use across the app
cache_manager: CacheManager = CacheManager()


async def init_cache(redis_url: str) -> None:
    """Initialize the Redis connection and set the cache manager singleton."""
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(redis_url, decode_responses=True)
        await client.ping()
        cache_manager._redis = client
    except Exception:
        cache_manager._redis = None


async def close_cache() -> None:
    """Close the Redis connection."""
    if cache_manager._redis:
        await cache_manager._redis.close()
        cache_manager._redis = None
