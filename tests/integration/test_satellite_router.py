"""Integration tests for the satellite API router.

Uses httpx.AsyncClient bound to the FastAPI app with mocked external APIs.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from argplant.main import app
from argplant.modules.satellite.models import SatelliteScene

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_CMR_ENTRIES = [
    {
        "granule_ur": "SMAP_L3_SM_P_20260101_R18290_001.h5",
        "producer_granule_id": "SMAP_L3_SM_P_20260101_R18290_001.h5",
        "time_start": "2026-01-01T00:00:00.000Z",
        "boxes": ["-61 -34 -60 -33"],
    },
    {
        "granule_ur": "SMAP_L3_SM_P_20260102_R18290_001.h5",
        "time_start": "2026-01-02T00:00:00.000Z",
    },
]

MOCK_STAC_FEATURES = [
    {
        "id": "S2A_MSIL2A_20260101T142741_N0500_R053_T20HNE_20260101T184502",
        "bbox": [-61.0, -34.0, -60.0, -33.0],
        "properties": {
            "datetime": "2026-01-01T14:27:41Z",
            "eo:cloud_cover": 8.5,
            "platform": "sentinel-2",
        },
        "assets": {
            "thumbnail": {
                "href": "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/thumbnail.jpg",
            }
        },
    },
    {
        "id": "S2A_MSIL2A_20260103T142741_N0500_R053_T20HNE_20260103T184502",
        "bbox": [-61.0, -34.0, -60.0, -33.0],
        "properties": {
            "datetime": "2026-01-03T14:27:41Z",
            "eo:cloud_cover": 3.2,
            "platform": "sentinel-2",
        },
        "assets": {},
    },
]

MOCK_STAC_S1 = [
    {
        "id": "S1A_IW_GRDH_1SDV_20260103T223045_20260103T223110_057592_071B50_9E7E",
        "bbox": [-61.0, -34.0, -60.0, -33.0],
        "properties": {
            "datetime": "2026-01-03T22:30:45Z",
            "platform": "sentinel-1",
        },
        "assets": {},
    },
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_earthdata():
    """Mock EarthdataClient.search_smap."""
    with patch(
        "argplant.modules.satellite.service.EarthdataClient.search_smap",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = MOCK_CMR_ENTRIES
        yield mock


@pytest.fixture
def mock_cdse():
    """Mock CdseClient.search_sentinel."""
    with patch(
        "argplant.modules.satellite.service.CdseClient.search_sentinel",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = MOCK_STAC_FEATURES
        yield mock


@pytest.fixture
def mock_cdse_s1():
    """Mock CdseClient.search_sentinel for Sentinel-1 results."""
    with patch(
        "argplant.modules.satellite.service.CdseClient.search_sentinel",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = MOCK_STAC_S1
        yield mock


@pytest.fixture
def mock_cdse_failing():
    """Mock CdseClient to raise an HTTP error."""
    import httpx

    with patch(
        "argplant.modules.satellite.service.CdseClient.search_sentinel",
        new_callable=AsyncMock,
    ) as mock:
        mock.side_effect = httpx.ConnectError("CDSE unreachable")
        yield mock


# ---------------------------------------------------------------------------
# SMAP endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smap_search_returns_200(
    test_client: AsyncClient, mock_earthdata: AsyncMock
):
    """SMAP search returns 200 with scene metadata array."""
    response = await test_client.get(
        "/api/v1/satellite/smap",
        params={
            "bbox": "-61,-34,-60,-33",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 2
    assert body[0]["scene_id"] == "SMAP_L3_SM_P_20260101_R18290_001.h5"
    assert body[0]["platform"] == "smap"
    assert "acquisition_date" in body[0]
    assert "granule_ur" in body[0]
    assert "bbox" in body[0]

    mock_earthdata.assert_called_once()


@pytest.mark.asyncio
async def test_smap_search_no_auth_graceful(
    test_client: AsyncClient, mock_earthdata: AsyncMock
):
    """SMAP search succeeds even when credentials are not set (CMR metadata is public)."""
    response = await test_client.get(
        "/api/v1/satellite/smap",
        params={
            "bbox": "-61,-34,-60,-33",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        },
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Sentinel search endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sentinel_search_returns_200(
    test_client: AsyncClient, mock_cdse: AsyncMock
):
    """Sentinel-2 search returns 200 with scene metadata array."""
    response = await test_client.get(
        "/api/v1/satellite/sentinel/search",
        params={
            "platform": "sentinel-2",
            "bbox": "-61,-34,-60,-33",
            "start": "2026-01-01",
            "end": "2026-01-31",
            "max_cloud_cover": 10.0,
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 2
    assert body[0]["id"] == MOCK_STAC_FEATURES[0]["id"]
    assert body[0]["cloud_cover"] == 8.5
    assert body[0]["platform"] == "sentinel-2"
    assert body[0]["thumbnail_url"] is not None

    # Verify max_cloud is forwarded
    mock_cdse.assert_called_once()
    call_args = mock_cdse.call_args[0]  # positional args: bbox, start_date, end_date, platform, max_cloud
    assert call_args[4] == 10.0


@pytest.mark.asyncio
async def test_sentinel_search_s1_no_cloud(
    test_client: AsyncClient, mock_cdse_s1: AsyncMock
):
    """Sentinel-1 search returns metadata without cloud_cover."""
    response = await test_client.get(
        "/api/v1/satellite/sentinel/search",
        params={
            "platform": "sentinel-1",
            "bbox": "-61,-34,-60,-33",
            "start": "2026-01-01",
            "end": "2026-01-31",
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert len(body) == 1
    assert body[0]["cloud_cover"] is None
    assert body[0]["platform"] == "sentinel-1"


@pytest.mark.asyncio
async def test_sentinel_search_invalid_platform_400(test_client: AsyncClient):
    """Invalid platform returns 400."""
    response = await test_client.get(
        "/api/v1/satellite/sentinel/search",
        params={
            "platform": "landsat-8",
            "bbox": "-61,-34,-60,-33",
            "start": "2026-01-01",
            "end": "2026-01-31",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_sentinel_search_cdse_failure_502(
    test_client: AsyncClient, mock_cdse_failing: AsyncMock
):
    """CDSE unreachable returns 502 Bad Gateway."""
    response = await test_client.get(
        "/api/v1/satellite/sentinel/search",
        params={
            "platform": "sentinel-2",
            "bbox": "-61,-34,-60,-33",
            "start": "2026-01-01",
            "end": "2026-01-31",
        },
    )
    assert response.status_code == 502


# ---------------------------------------------------------------------------
# Download endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_scene_not_found_returns_404(test_client: AsyncClient):
    """Unknown scene_id → 404."""
    response = await test_client.post(
        "/api/v1/satellite/sentinel/nonexistent_scene/download",
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_with_arq_mocked(test_engine):
    """POST download enqueues an arq job and returns 202.

    Uses test_engine directly to pre-seed a scene in the test DB,
    then creates its own client because the session must share the engine.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from argplant.shared.database import get_session

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Pre-seed a scene in the test DB
    async with session_factory() as s:
        async with s.begin():
            scene = SatelliteScene(
                scene_id="S2A_download_test",
                platform="sentinel-2",
                bbox=[-61.0, -34.0, -60.0, -33.0],
                acquisition_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
                cloud_cover=5.0,
                scene_metadata={"id": "S2A_download_test"},
            )
            s.add(scene)

    # 2. Override get_session with our engine
    async def override_session():
        async with session_factory() as sess:
            yield sess

    app.dependency_overrides[get_session] = override_session

    # 3. Mock arq pool
    with patch(
        "argplant.modules.satellite.router.arq.create_pool",
        new_callable=AsyncMock,
    ) as mock_pool:
        mock_job = AsyncMock()
        mock_job.job_id = "test-job-uuid-123"
        mock_redis = AsyncMock()
        mock_redis.enqueue_job = AsyncMock(return_value=mock_job)
        mock_pool.return_value = mock_redis

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/satellite/sentinel/S2A_download_test/download",
            )
            assert response.status_code == 202

            body = response.json()
            assert body["job_id"] == "test-job-uuid-123"
            assert body["status"] == "queued"
            mock_redis.enqueue_job.assert_called_once_with(
                "download_sentinel", "S2A_download_test"
            )

    app.dependency_overrides.clear()
