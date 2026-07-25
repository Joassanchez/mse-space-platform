"""Integration tests for the agronomy and economy API routers.

Uses httpx.AsyncClient bound to the FastAPI app (via ASGITransport) with
mocked external HTTP clients and fakeredis so no real API keys or MAGyP
or Redis server are needed.
"""

from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
import pytest

from argplant.main import app


# ---------------------------------------------------------------------------
# Mock MAGyP data
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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _load_seeds():
    """Ensure agronomy and economy seeds are loaded before integration tests.

    The ASGITransport may not trigger the FastAPI lifespan, so we load seeds
    explicitly for test reliability.
    """
    from argplant.modules.agronomy.seed_data import load_agronomy_seeds
    from argplant.modules.economy.seed_data import load_economy_seeds
    load_agronomy_seeds()
    load_economy_seeds()


# ---------------------------------------------------------------------------
# Agronomy endpoint tests
# ---------------------------------------------------------------------------


class TestAgronomyRouter:
    """Integration tests for /api/v1/agronomy endpoints."""

    @pytest.mark.asyncio
    async def test_list_crops_returns_200(self, test_client):
        """GIVEN agronomy seeds loaded at startup
        WHEN GET /api/v1/agronomy/crops is called
        THEN returns 200 with soy and corn in the list."""
        response = await test_client.get("/api/v1/agronomy/crops")
        assert response.status_code == 200
        data = response.json()
        assert "crops" in data
        crop_ids = {c["id"] for c in data["crops"]}
        assert "soy" in crop_ids
        assert "corn" in crop_ids
        soy = next(c for c in data["crops"] if c["id"] == "soy")
        assert soy["scientific_name"] == "Glycine max"

    @pytest.mark.asyncio
    async def test_get_soy_stages_returns_200(self, test_client):
        """GIVEN BBCH stage data loaded
        WHEN GET /api/v1/agronomy/crops/soy/stages is called
        THEN returns 200 with BBCH 60 (flowering) and BBCH 79 present."""
        response = await test_client.get("/api/v1/agronomy/crops/soy/stages")
        assert response.status_code == 200
        data = response.json()
        assert data["crop_id"] == "soy"
        assert "stages" in data
        codes = {s["bbch_code"] for s in data["stages"]}
        assert "60" in codes  # flowering
        assert "79" in codes  # end of pod formation

    @pytest.mark.asyncio
    async def test_get_corn_stages_returns_200(self, test_client):
        """GIVEN BBCH stage data for corn loaded
        WHEN GET /api/v1/agronomy/crops/corn/stages is called
        THEN returns 200 with corn growth stages."""
        response = await test_client.get("/api/v1/agronomy/crops/corn/stages")
        assert response.status_code == 200
        data = response.json()
        assert data["crop_id"] == "corn"
        assert len(data["stages"]) > 0

    @pytest.mark.asyncio
    async def test_unknown_crop_returns_404(self, test_client):
        """GIVEN crop 'nonexistent' does not exist
        WHEN GET /api/v1/agronomy/crops/nonexistent/stages is called
        THEN returns 404."""
        response = await test_client.get("/api/v1/agronomy/crops/nonexistent/stages")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Economy endpoint tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Economy endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def _mock_redis():
    """Replace _get_redis with a fakeredis instance for integration tests."""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch("argplant.shared.cache._get_redis", new=lambda: fake):
        with patch("argplant.modules.economy.router._get_redis", new=lambda: fake):
            yield fake
    await fake.flushall()
    await fake.aclose()


class TestEconomyRouter:
    """Integration tests for /api/v1/economy/prices endpoint."""

    @pytest.mark.asyncio
    async def test_valid_product_returns_200(self, test_client, _mock_redis):
        """GIVEN valid product_id=18 (soy), puerto_id=23 (Rosario)
        WHEN GET /api/v1/economy/prices is called
        THEN returns 200 with price series data."""
        with patch(
            "argplant.modules.economy.client.MagypClient.fetch",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = MOCK_MAGYP_RESPONSE

            response = await test_client.get(
                "/api/v1/economy/prices",
                params={
                    "producto": 18,
                    "puerto": 23,
                    "desde": "2026-07-17",
                    "hasta": "2026-07-24",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["producto"] == "Soja"
            assert data["puerto"] == "Rosario"
            assert len(data["minimos"]) == 2
            assert "fecha" in data["minimos"][0]
            assert response.headers.get("X-Cache") == "HIT"

    @pytest.mark.asyncio
    async def test_unknown_product_returns_400(self, test_client, _mock_redis):
        """GIVEN product_id=999 is not in seed data
        WHEN GET /api/v1/economy/prices is called
        THEN returns 400 with valid product IDs message."""
        response = await test_client.get(
            "/api/v1/economy/prices",
            params={
                "producto": 999,
                "puerto": 23,
                "desde": "2026-07-17",
                "hasta": "2026-07-24",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert "Unknown product" in data["detail"]
        assert "18" in data["detail"]  # soy should be mentioned

    @pytest.mark.asyncio
    async def test_unknown_port_returns_400(self, test_client, _mock_redis):
        """GIVEN puerto_id=999 is not in seed data
        WHEN GET /api/v1/economy/prices is called
        THEN returns 400 with unknown port message."""
        response = await test_client.get(
            "/api/v1/economy/prices",
            params={
                "producto": 18,
                "puerto": 999,
                "desde": "2026-07-17",
                "hasta": "2026-07-24",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert "Unknown port" in data["detail"]

    @pytest.mark.asyncio
    async def test_stale_fallback_returns_x_stale(self, test_client, _mock_redis):
        """GIVEN MAGyP is failing AND stale cache exists (fresh expired)
        WHEN GET /api/v1/economy/prices is called
        THEN returns 200 with X-Stale: true and X-Cache: STALE headers."""
        import httpx

        with patch(
            "argplant.modules.economy.client.MagypClient.fetch",
            new_callable=AsyncMock,
        ) as mock_fetch:
            # First call: succeed to populate cache
            mock_fetch.return_value = MOCK_MAGYP_RESPONSE

            response = await test_client.get(
                "/api/v1/economy/prices",
                params={
                    "producto": 18,
                    "puerto": 23,
                    "desde": "2026-07-17",
                    "hasta": "2026-07-24",
                },
            )
            assert response.status_code == 200

            # Expire the fresh cache so the stale path is forced
            await _mock_redis.delete("prices:18:23:2026-07-17:2026-07-24")

            # Second call: simulate API failure
            mock_fetch.side_effect = httpx.HTTPError("Connection error")

            response2 = await test_client.get(
                "/api/v1/economy/prices",
                params={
                    "producto": 18,
                    "puerto": 23,
                    "desde": "2026-07-17",
                    "hasta": "2026-07-24",
                },
            )
            assert response2.status_code == 200
            assert response2.headers.get("X-Stale") == "true"
            assert response2.headers.get("X-Cache") == "STALE"

    @pytest.mark.asyncio
    async def test_missing_params_returns_422(self, test_client):
        """GIVEN required query params are missing
        WHEN GET /api/v1/economy/prices is called
        THEN returns 422 validation error."""
        response = await test_client.get("/api/v1/economy/prices")
        assert response.status_code == 422
