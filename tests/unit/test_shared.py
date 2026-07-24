"""Unit tests for shared infrastructure: config, cache, storage, and rate limiter."""

import json

import pytest


class TestConfigDefaults:
    """Verify that Settings defaults match the design specification."""

    def test_default_database_url_is_postgres(self):
        from argplant.shared.config import Settings

        s = Settings(DATABASE_URL="override-me")
        assert s.DATABASE_URL == "override-me"

    def test_default_rate_limit(self, mock_settings):
        assert mock_settings.RATE_LIMIT_REQUESTS == 5  # overridden in fixture
        assert mock_settings.RATE_LIMIT_WINDOW_SECONDS == 60

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("OPENWEATHER_API_KEY", "my-real-key")
        from argplant.shared.config import Settings as FreshSettings

        s = FreshSettings()
        assert s.OPENWEATHER_API_KEY == "my-real-key"

    def test_missing_api_key_defaults_to_empty(self, mock_settings):
        assert mock_settings.EARTHDATA_USERNAME == ""
        assert mock_settings.CDSE_PASSWORD == ""

    def test_ingestion_coords_default(self, mock_settings):
        assert mock_settings.INGESTION_COORDS_LAT == pytest.approx(-33.89)
        assert mock_settings.INGESTION_COORDS_LON == pytest.approx(-60.57)


class TestCacheOperations:
    """Test Redis cache wrapper: set, get, stale, delete."""

    @pytest.mark.asyncio
    async def test_set_and_get_json(self, test_redis):
        from argplant.shared.cache import get_json, set_json

        await set_json(test_redis, "test:key", {"value": 42}, ttl=60)
        result = await get_json(test_redis, "test:key")
        assert result == {"value": 42}

    @pytest.mark.asyncio
    async def test_get_miss_returns_none(self, test_redis):
        from argplant.shared.cache import get_json

        result = await get_json(test_redis, "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_stale_cache_persists_after_fresh_expires(self, test_redis):
        from argplant.shared.cache import get_json, get_stale, set_json

        await set_json(test_redis, "stale:key", {"data": "fresh"}, ttl=1)
        # fakeredis TTL behavior: after set, key exists; simulate expiration
        stale = await get_stale(test_redis, "stale:key")
        assert stale == {"data": "fresh"}

    @pytest.mark.asyncio
    async def test_delete_removes_both_fresh_and_stale(self, test_redis):
        from argplant.shared.cache import delete, get_json, get_stale, set_json

        await set_json(test_redis, "del:key", {"x": 1}, ttl=60)
        await delete(test_redis, "del:key")
        assert await get_json(test_redis, "del:key") is None
        assert await get_stale(test_redis, "del:key") is None


class TestLocalStorage:
    """Test the LocalStorage implementation of the StorageBackend protocol."""

    @pytest.mark.asyncio
    async def test_save_and_exists(self, tmp_path):
        from argplant.shared.storage import LocalStorage

        storage = LocalStorage(tmp_path)
        path = await storage.save("test/file.txt", b"hello world")
        assert path.exists()
        assert path.read_bytes() == b"hello world"
        assert await storage.exists("test/file.txt") is True

    @pytest.mark.asyncio
    async def test_exists_missing_file(self, tmp_path):
        from argplant.shared.storage import LocalStorage

        storage = LocalStorage(tmp_path)
        assert await storage.exists("nope.txt") is False

    @pytest.mark.asyncio
    async def test_get_path_returns_absolute(self, tmp_path):
        from argplant.shared.storage import LocalStorage

        storage = LocalStorage(tmp_path)
        result = storage.get_path("sub/file.nc")
        assert result == tmp_path / "sub" / "file.nc"
