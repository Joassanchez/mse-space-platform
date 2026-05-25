"""Tests for Redis cache layer."""

import pytest

from backend.core.cache import CacheManager

pytestmark = pytest.mark.asyncio


class TestCacheKey:
    """CacheManager.make_key tests."""

    async def test_key_with_prefix_only(self) -> None:
        """GIVEN only prefix, THEN key is just the prefix."""
        key = CacheManager.make_key("analysis")
        assert key == "analysis"

    async def test_key_with_region(self) -> None:
        """GIVEN prefix and region, THEN key is prefix:region."""
        key = CacheManager.make_key("geo", "cordoba")
        assert key == "geo:cordoba"

    async def test_key_with_multiple_parts(self) -> None:
        """GIVEN prefix, region, and date, THEN key joins all."""
        key = CacheManager.make_key("geo:soil-moisture", "cordoba", "2024-01-15")
        assert key == "geo:soil-moisture:cordoba:2024-01-15"


class TestCacheTTL:
    """CacheManager.get_ttl tests."""

    async def test_ttl_for_analysis(self) -> None:
        """GIVEN analysis prefix, THEN TTL is 300s."""
        assert CacheManager.get_ttl("analysis") == 300

    async def test_ttl_for_geo(self) -> None:
        """GIVEN geo prefix, THEN TTL is 600s."""
        assert CacheManager.get_ttl("geo") == 600

    async def test_ttl_for_regions(self) -> None:
        """GIVEN regions prefix, THEN TTL is 3600s."""
        assert CacheManager.get_ttl("regions") == 3600

    async def test_ttl_default(self) -> None:
        """GIVEN unknown prefix, THEN TTL defaults to 300s."""
        assert CacheManager.get_ttl("unknown") == 300


class TestCacheManager:
    """CacheManager operations with no Redis (graceful degradation)."""

    async def test_get_returns_none_without_redis(self) -> None:
        """GIVEN no Redis client, THEN get returns None."""
        cm = CacheManager()
        result = await cm.get("test")
        assert result is None

    async def test_set_does_not_error_without_redis(self) -> None:
        """GIVEN no Redis client, THEN set does not raise."""
        cm = CacheManager()
        await cm.set("test", "value")  # should not raise

    async def test_invalidate_does_not_error_without_redis(self) -> None:
        """GIVEN no Redis client, THEN invalidate does not raise."""
        cm = CacheManager()
        await cm.invalidate("test:*")  # should not raise
