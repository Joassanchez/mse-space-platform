"""Integration tests for the ingestion pipeline — job status endpoint and cron jobs."""

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from argplant.main import app
from argplant.shared.database import get_session


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _mock_session_factory(test_session: AsyncSession):
    """Return a callable that yields the given test session via ``async with``."""
    @asynccontextmanager
    async def _factory():
        yield test_session

    return _factory


# ---------------------------------------------------------------------------
# Job status endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_job_status_not_found(test_session: AsyncSession) -> None:
    """GET /api/v1/jobs/{id} returns 404 when the job does not exist."""
    mock_arq = AsyncMock()

    with patch(
        "argplant.modules.ingestion.router._get_arq", return_value=mock_arq
    ), patch("arq.jobs.Job.info", return_value=None):

        async def override_get_session():
            yield test_session

        app.dependency_overrides[get_session] = override_get_session
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/jobs/nonexistent-job-id")
            assert resp.status_code == 404
            data = resp.json()
            assert "not found" in data["detail"].lower()

        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_job_status_completed(test_session: AsyncSession) -> None:
    """GET /api/v1/jobs/{id} returns 200 with status when the job exists."""
    mock_status = MagicMock()
    mock_status.success = True
    mock_status.finish_time = datetime(2026, 7, 25, 6, 0, 0, tzinfo=timezone.utc)
    mock_status.start_time = datetime(2026, 7, 25, 5, 59, 50, tzinfo=timezone.utc)
    mock_status.enqueue_time = datetime(2026, 7, 25, 5, 59, 0, tzinfo=timezone.utc)

    mock_result = MagicMock()
    mock_result.success = True
    mock_result.result = {
        "status": "completed",
        "file_path": "data/satellite/sentinel-2/abc123/product.zip",
        "size_bytes": 456789,
    }

    mock_arq = AsyncMock()
    mock_arq.aclose = AsyncMock()

    with (
        patch("argplant.modules.ingestion.router._arq_pool", mock_arq),
        patch("argplant.modules.ingestion.router._get_arq", return_value=mock_arq),
        patch("arq.jobs.Job.info", return_value=mock_status),
        patch("arq.jobs.Job.result_info", return_value=mock_result),
    ):

        async def override_get_session():
            yield test_session

        app.dependency_overrides[get_session] = override_get_session
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/jobs/test-job-123")
            assert resp.status_code == 200
            data = resp.json()
            assert data["job_id"] == "test-job-123"
            assert data["status"] == "completed"
            assert data["result"] is not None
            assert data["result"]["file_path"] == (
                "data/satellite/sentinel-2/abc123/product.zip"
            )

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_job_status_failed(test_session: AsyncSession) -> None:
    """GET /api/v1/jobs/{id} returns 'failed' status when the job errored."""
    mock_status = MagicMock()
    mock_status.success = False
    mock_status.finish_time = datetime(2026, 7, 25, 6, 5, 0, tzinfo=timezone.utc)
    mock_status.start_time = datetime(2026, 7, 25, 6, 0, 0, tzinfo=timezone.utc)
    mock_status.enqueue_time = datetime(2026, 7, 25, 5, 59, 0, tzinfo=timezone.utc)

    mock_result = MagicMock()
    mock_result.success = False
    mock_result.result = "CDSE download timeout after 3 retries"

    mock_arq = AsyncMock()

    with (
        patch("argplant.modules.ingestion.router._arq_pool", mock_arq),
        patch("argplant.modules.ingestion.router._get_arq", return_value=mock_arq),
        patch("arq.jobs.Job.info", return_value=mock_status),
        patch("arq.jobs.Job.result_info", return_value=mock_result),
    ):

        async def override_get_session():
            yield test_session

        app.dependency_overrides[get_session] = override_get_session
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/jobs/failed-job-456")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "failed"
            assert data["result"] is not None
            assert "error" in data["result"]

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Cron job functions — don't crash (idempotent, mocked external APIs)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cron_warmup_weather_cache_does_not_crash(
    test_session: AsyncSession, test_redis
) -> None:
    """warmup_weather_cache runs without exceptions with mocked OpenWeather + POWER."""
    mock_owm_response = {
        "main": {"temp": 22.5, "humidity": 65},
        "wind": {"speed": 3.1},
        "weather": [{"description": "clear sky"}],
    }
    mock_power_response = {
        "properties": {
            "parameter": {
                "T2M": {"20260725": 23.0},
                "PRECTOTCORR": {"20260725": 1.2},
                "ALLSKY_SFC_SW_DWN": {"20260725": 18.5},
            }
        }
    }

    with (
        patch(
            "argplant.modules.agroclimate.client.OpenWeatherClient.current",
            return_value=mock_owm_response,
        ),
        patch(
            "argplant.modules.agroclimate.client.NasaPowerClient.daily",
            return_value=mock_power_response,
        ),
        patch(
            "argplant.shared.cache._get_redis",
            return_value=test_redis,
        ),
    ):
        from argplant.modules.ingestion.cron import warmup_weather_cache

        await warmup_weather_cache({})


@pytest.mark.asyncio
async def test_cron_refresh_prices_does_not_crash(
    test_session: AsyncSession,
) -> None:
    """refresh_prices runs without exceptions with mocked MAGyP client."""
    today = date.today()
    mock_magyp_response = {
        "minimos": [{"fecha": today.isoformat(), "valor": 280000}],
        "maximos": [{"fecha": today.isoformat(), "valor": 310000}],
        "promedios": [{"fecha": today.isoformat(), "valor": 295000}],
        "modal": [{"valor": 290000}],
    }

    with (
        patch(
            "argplant.modules.economy.client.MagypClient.fetch",
            return_value=mock_magyp_response,
        ),
        patch(
            "argplant.modules.ingestion.cron.async_session",
            _mock_session_factory(test_session),
        ),
    ):
        from argplant.modules.ingestion.cron import refresh_prices

        await refresh_prices({})


@pytest.mark.asyncio
async def test_cron_scan_satellite_catalog_does_not_crash(
    test_session: AsyncSession,
) -> None:
    """scan_satellite_catalog runs without exceptions with mocked CDSE client."""
    mock_stac_features = [
        {
            "id": "S2A_test_scene",
            "bbox": [-61, -34, -60, -33],
            "properties": {
                "datetime": "2026-07-25T14:00:00Z",
                "eo:cloud_cover": 5.2,
                "platform": "sentinel-2",
            },
            "assets": {"thumbnail": {"href": "https://example.com/thumb.jpg"}},
        }
    ]

    with (
        patch(
            "argplant.modules.satellite.client.CdseClient.search_sentinel",
            return_value=mock_stac_features,
        ),
        patch(
            "argplant.modules.ingestion.cron.async_session",
            _mock_session_factory(test_session),
        ),
    ):
        from argplant.modules.ingestion.cron import scan_satellite_catalog

        await scan_satellite_catalog({})


# ---------------------------------------------------------------------------
# Cron persistence tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cron_refresh_prices_persists_to_db(
    test_session: AsyncSession,
) -> None:
    """refresh_prices actually writes rows to the price_series table."""
    today = date.today()
    mock_magyp_response = {
        "minimos": [{"fecha": today.isoformat(), "valor": 280000}],
        "maximos": [{"fecha": today.isoformat(), "valor": 310000}],
        "promedios": [{"fecha": today.isoformat(), "valor": 295000}],
        "modal": [{"valor": 290000}],
    }

    with (
        patch(
            "argplant.modules.economy.client.MagypClient.fetch",
            return_value=mock_magyp_response,
        ),
        patch(
            "argplant.modules.ingestion.cron.async_session",
            _mock_session_factory(test_session),
        ),
    ):
        from argplant.modules.ingestion.cron import refresh_prices

        await refresh_prices({})

    from argplant.modules.economy.repository import PriceSeriesRepo

    repo = PriceSeriesRepo()
    rows = await repo.find(test_session, 18, 23, today, today)
    assert len(rows) >= 1
    assert rows[0].minimo == 280000
    assert rows[0].producto_id == 18
    assert rows[0].puerto_id == 23


@pytest.mark.asyncio
async def test_cron_idempotent_rerun(test_session: AsyncSession) -> None:
    """Running refresh_prices twice should not duplicate rows."""
    today = date.today()
    mock_magyp_response = {
        "minimos": [{"fecha": today.isoformat(), "valor": 100}],
        "maximos": [{"fecha": today.isoformat(), "valor": 200}],
        "promedios": [{"fecha": today.isoformat(), "valor": 150}],
        "modal": [{"valor": 150}],
    }

    with (
        patch(
            "argplant.modules.economy.client.MagypClient.fetch",
            return_value=mock_magyp_response,
        ),
        patch(
            "argplant.modules.ingestion.cron.async_session",
            _mock_session_factory(test_session),
        ),
    ):
        from argplant.modules.ingestion.cron import refresh_prices

        await refresh_prices({})
        await refresh_prices({})

    from argplant.modules.economy.repository import PriceSeriesRepo

    repo = PriceSeriesRepo()
    rows = await repo.find(test_session, 18, 23, today, today)
    assert len(rows) == 1
    assert rows[0].minimo == 100
