"""Unit tests for the economy module — service, client, and repository."""

from datetime import date, datetime, timezone

import pytest
from httpx import Response as HttpxResponse

from argplant.modules.economy.models import PriceSeries, PriceSeriesResponse
from argplant.modules.economy.repository import PriceSeriesRepo
from argplant.modules.economy.seed_data import (
    is_valid_port,
    is_valid_product,
    load_economy_seeds,
    valid_product_ids,
)
from argplant.modules.economy.service import PriceService, ServiceUnavailableError


# ---------------------------------------------------------------------------
# Mock MAGyP response
# ---------------------------------------------------------------------------

MOCK_MAGYP_RESPONSE = {
    "minimos": [
        {"fecha": "2026-07-17", "valor": "280000"},
        {"fecha": "2026-07-18", "valor": "282000"},
    ],
    "maximos": [
        {"fecha": "2026-07-17", "valor": "295000"},
        {"fecha": "2026-07-18", "valor": "298000"},
    ],
    "promedios": [
        {"fecha": "2026-07-17", "valor": "287500"},
        {"fecha": "2026-07-18", "valor": "290000"},
    ],
    "modal": [{"valor": "290000"}],
}


# ---------------------------------------------------------------------------
# Mock MagypClient
# ---------------------------------------------------------------------------


class _MockMagypClient:
    """Mock that returns a canned MAGyP response."""

    def __init__(self, response: dict | None = None, should_fail: bool = False):
        self._response = response or MOCK_MAGYP_RESPONSE
        self.should_fail = should_fail

    async def fetch(self, producto_id, puerto_id, desde, hasta):
        if self.should_fail:
            import httpx
            raise httpx.HTTPError("Connection error")
        return self._response


# ---------------------------------------------------------------------------
# Seed data loading tests
# ---------------------------------------------------------------------------


class TestEconomySeeds:
    """Tests for load_economy_seeds and ID validation."""

    def test_load_seeds_from_fixtures(self, monkeypatch):
        """GIVEN real fixture files in data/economy/
        WHEN load_economy_seeds is called
        THEN product and port mappings are populated."""
        # Force reload from real fixtures
        import argplant.modules.economy.seed_data as esd

        monkeypatch.setattr(esd, "FIXTURE_DIR", esd.FIXTURE_DIR)
        esd._product_map = {}
        esd._product_ids = set()
        esd._port_map = {}
        esd._port_ids = set()

        load_economy_seeds()
        assert is_valid_product(18)
        assert is_valid_port(23)
        assert 18 in valid_product_ids()

    def test_unknown_product(self, monkeypatch):
        """GIVEN no seed data loaded
        WHEN is_valid_product(999) is called
        THEN returns False."""
        import argplant.modules.economy.seed_data as esd

        monkeypatch.setattr(esd, "_product_ids", {18, 1})
        assert not is_valid_product(999)
        assert is_valid_product(18)

    def test_unknown_port(self, monkeypatch):
        """GIVEN no seed data loaded
        WHEN is_valid_port(999) is called
        THEN returns False."""
        import argplant.modules.economy.seed_data as esd

        monkeypatch.setattr(esd, "_port_ids", {23, 2})
        assert not is_valid_port(999)
        assert is_valid_port(23)


# ---------------------------------------------------------------------------
# PriceSeriesRepo tests
# ---------------------------------------------------------------------------


class TestPriceSeriesRepo:
    """Tests for PriceSeriesRepo with the test database."""

    @pytest.mark.asyncio
    async def test_upsert_and_find(self, test_session):
        """GIVEN an empty price_series table
        WHEN entries are upserted then queried
        THEN correct entries are returned in date order."""
        entries = [
            PriceSeries(
                producto_id=18,
                puerto_id=23,
                fecha=date(2026, 7, 17),
                minimo=280000,
                maximo=295000,
                promedio=287500,
                modal=290000,
            ),
            PriceSeries(
                producto_id=18,
                puerto_id=23,
                fecha=date(2026, 7, 18),
                minimo=282000,
                maximo=298000,
                promedio=290000,
                modal=290000,
            ),
        ]

        count = await PriceSeriesRepo.upsert(test_session, entries)
        assert count == 2

        results = await PriceSeriesRepo.find(
            test_session,
            producto_id=18,
            puerto_id=23,
            desde=date(2026, 7, 17),
            hasta=date(2026, 7, 18),
        )
        assert len(results) == 2
        assert results[0].fecha == date(2026, 7, 17)
        assert results[1].fecha == date(2026, 7, 18)

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, test_session):
        """GIVEN an existing price entry
        WHEN a new value is upserted for the same key
        THEN the row is updated, not duplicated."""
        entry = PriceSeries(
            producto_id=18,
            puerto_id=23,
            fecha=date(2026, 7, 17),
            minimo=280000,
            maximo=295000,
            promedio=287500,
            modal=290000,
        )
        await PriceSeriesRepo.upsert(test_session, [entry])

        # Upsert with new values
        updated = PriceSeries(
            producto_id=18,
            puerto_id=23,
            fecha=date(2026, 7, 17),
            minimo=285000,
            maximo=300000,
            promedio=292500,
            modal=292000,
        )
        await PriceSeriesRepo.upsert(test_session, [updated])

        results = await PriceSeriesRepo.find(
            test_session, 18, 23, date(2026, 7, 17), date(2026, 7, 17),
        )
        assert len(results) == 1
        assert results[0].minimo == 285000
        assert results[0].modal == 292000

    @pytest.mark.asyncio
    async def test_find_date_range_filter(self, test_session):
        """GIVEN entries spanning multiple dates
        WHEN find is called with a narrow date range
        THEN only entries within the range are returned."""
        entries = [
            PriceSeries(producto_id=18, puerto_id=23, fecha=date(2026, 7, 15), minimo=100, maximo=200, promedio=150, modal=150),
            PriceSeries(producto_id=18, puerto_id=23, fecha=date(2026, 7, 16), minimo=110, maximo=210, promedio=160, modal=160),
            PriceSeries(producto_id=18, puerto_id=23, fecha=date(2026, 7, 17), minimo=120, maximo=220, promedio=170, modal=170),
        ]
        await PriceSeriesRepo.upsert(test_session, entries)

        results = await PriceSeriesRepo.find(
            test_session, 18, 23, date(2026, 7, 16), date(2026, 7, 16),
        )
        assert len(results) == 1
        assert results[0].fecha == date(2026, 7, 16)


# ---------------------------------------------------------------------------
# PriceService tests
# ---------------------------------------------------------------------------


class TestPriceService:
    """Tests for PriceService with mocked Redis and MAGyP client."""

    @pytest.mark.asyncio
    async def test_fresh_fetch_and_normalise(self, test_redis):
        """GIVEN a cold cache and mock MAGyP client
        WHEN get() is called
        THEN returns normalised PriceSeriesResponse with no stale flag."""
        import argplant.modules.economy.seed_data as esd

        # Ensure product/port are valid
        import argplant.modules.economy.seed_data as esd
        esd._product_ids = {18, 1}
        esd._port_ids = {23, 2}
        esd._product_map = {18: "Soja", 1: "Maíz"}
        esd._port_map = {23: "Rosario", 2: "Bahía Blanca"}

        mock_client = _MockMagypClient()
        service = PriceService(test_redis, client=mock_client)

        result, is_stale = await service.get(
            producto=18, puerto=23,
            desde=date(2026, 7, 17), hasta=date(2026, 7, 18),
        )

        assert not is_stale
        assert isinstance(result, PriceSeriesResponse)
        assert result.producto == "Soja"
        assert result.puerto == "Rosario"
        assert len(result.minimos) == 2
        assert "fecha" in result.minimos[0]

    @pytest.mark.asyncio
    async def test_cache_hit(self, test_redis):
        """GIVEN cached price data exists
        WHEN get() is called with the same params
        THEN returns from cache without external API call."""
        import argplant.modules.economy.seed_data as esd
        esd._product_ids = {18}
        esd._port_ids = {23}
        esd._product_map = {18: "Soja"}
        esd._port_map = {23: "Rosario"}

        from argplant.shared.cache import set_json

        cached_data = {
            "producto_id": 18,
            "producto": "Soja",
            "puerto_id": 23,
            "puerto": "Rosario",
            "minimos": [{"fecha": "2026-07-17", "valor": 280000}],
            "maximos": [{"fecha": "2026-07-17", "valor": 295000}],
            "promedios": [{"fecha": "2026-07-17", "valor": 287500}],
            "modal": [{"valor": 290000}],
        }
        cache_key = "prices:18:23:2026-07-17:2026-07-18"
        await set_json(test_redis, cache_key, cached_data, ttl=3600)

        service = PriceService(test_redis, client=_MockMagypClient())
        result, is_stale = await service.get(
            producto=18, puerto=23,
            desde=date(2026, 7, 17), hasta=date(2026, 7, 18),
        )

        assert not is_stale
        assert result.producto == "Soja"

    @pytest.mark.asyncio
    async def test_stale_fallback_on_api_failure(self, test_redis):
        """GIVEN MAGyP is failing AND stale cache exists (fresh expired)
        WHEN get() is called
        THEN returns stale data with is_stale=True."""
        import argplant.modules.economy.seed_data as esd
        esd._product_ids = {18}
        esd._port_ids = {23}
        esd._product_map = {18: "Soja"}
        esd._port_map = {23: "Rosario"}

        from argplant.shared.cache import set_json

        stale_data = {
            "producto_id": 18, "producto": "Soja",
            "puerto_id": 23, "puerto": "Rosario",
            "minimos": [{"fecha": "2026-07-17", "valor": 279000}],
            "maximos": [{"fecha": "2026-07-17", "valor": 294000}],
            "promedios": [{"fecha": "2026-07-17", "valor": 286500}],
            "modal": [{"valor": 289000}],
        }
        cache_key = "prices:18:23:2026-07-17:2026-07-18"
        await set_json(test_redis, cache_key, stale_data, ttl=1)
        # Explicitly expire the fresh key so the service hits stale fallback
        await test_redis.delete(cache_key)

        mock_client = _MockMagypClient(should_fail=True)
        service = PriceService(test_redis, client=mock_client)

        result, is_stale = await service.get(18, 23, date(2026, 7, 17), date(2026, 7, 18))
        assert is_stale
        assert result.producto == "Soja"

    @pytest.mark.asyncio
    async def test_cold_cache_api_failure_raises(self, test_redis):
        """GIVEN cold cache AND MAGyP is failing
        WHEN get() is called
        THEN ServiceUnavailableError is raised."""
        import argplant.modules.economy.seed_data as esd
        esd._product_ids = {18}
        esd._port_ids = {23}
        esd._product_map = {18: "Soja"}
        esd._port_map = {23: "Rosario"}

        mock_client = _MockMagypClient(should_fail=True)
        service = PriceService(test_redis, client=mock_client)

        with pytest.raises(ServiceUnavailableError):
            await service.get(18, 23, date(2026, 7, 17), date(2026, 7, 18))

    @pytest.mark.asyncio
    async def test_unknown_product_raises_valueerror(self, test_redis):
        """GIVEN an unrecognised product ID
        WHEN get() is called
        THEN ValueError is raised."""
        import argplant.modules.economy.seed_data as esd
        esd._product_ids = {18}
        esd._port_ids = {23}

        service = PriceService(test_redis, client=_MockMagypClient())

        with pytest.raises(ValueError, match="Unknown product"):
            await service.get(999, 23, date(2026, 7, 17), date(2026, 7, 18))

    @pytest.mark.asyncio
    async def test_unknown_port_raises_valueerror(self, test_redis):
        """GIVEN an unrecognised port ID
        WHEN get() is called
        THEN ValueError is raised."""
        import argplant.modules.economy.seed_data as esd
        esd._product_ids = {18}
        esd._port_ids = {23}

        service = PriceService(test_redis, client=_MockMagypClient())

        with pytest.raises(ValueError, match="Unknown port"):
            await service.get(18, 999, date(2026, 7, 17), date(2026, 7, 18))


# ---------------------------------------------------------------------------
# PriceService.to_orm_entries tests
# ---------------------------------------------------------------------------


class TestToOrmEntries:
    """Tests for converting MAGyP raw responses to ORM entries."""

    def test_conversion(self):
        """GIVEN a valid MAGyP response
        WHEN to_orm_entries() is called
        THEN returns correct PriceSeries instances."""
        entries = PriceService.to_orm_entries(MOCK_MAGYP_RESPONSE, producto_id=18, puerto_id=23)
        assert len(entries) == 2
        first = entries[0]
        assert first.producto_id == 18
        assert first.puerto_id == 23
        assert first.fecha == date(2026, 7, 17)
        assert first.minimo == 280000
        assert first.maximo == 295000
        assert first.promedio == 287500
        assert first.modal == 290000
