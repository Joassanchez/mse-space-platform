"""Unit tests for satellite service layer.

Tests SmapService and SentinelService with mocked external clients.
Covers search normalisation, catalog filtering, and error handling.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from argplant.modules.satellite.models import SatelliteScene, SentinelSceneMeta, SmSceneMeta
from argplant.modules.satellite.service import (
    SentinelService,
    SmapService,
    _normalise_sentinel_feature,
    _normalise_smap_granule,
)

# ---------------------------------------------------------------------------
# Shared mock data
# ---------------------------------------------------------------------------

MOCK_CMR_ENTRY = {
    "granule_ur": "SMAP_L3_SM_P_20260101_R18290_001.h5",
    "producer_granule_id": "SMAP_L3_SM_P_20260101_R18290_001.h5",
    "time_start": "2026-01-01T00:00:00.000Z",
    "boxes": ["-61 -34 -60 -33"],
}

MOCK_CMR_ENTRY_NO_BOXES = {
    "granule_ur": "SMAP_L3_SM_P_20260102_R18290_001.h5",
    "time_start": "2026-01-02T00:00:00.000Z",
}

MOCK_STAC_FEATURE = {
    "id": "S2A_MSIL2A_20260101T142741_N0500_R053_T20HNE_20260101T184502",
    "bbox": [-61.0, -34.0, -60.0, -33.0],
    "properties": {
        "datetime": "2026-01-01T14:27:41Z",
        "eo:cloud_cover": 8.5,
        "platform": "sentinel-2",
    },
    "assets": {
        "thumbnail": {
            "href": "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/20/H/NE/2026/01/01/0/thumbnail.jpg",
        }
    },
}

MOCK_STAC_FEATURE_S1 = {
    "id": "S1A_IW_GRDH_1SDV_20260101T223045_20260101T223110_057592_071B50_9E7E",
    "bbox": [-61.0, -34.0, -60.0, -33.0],
    "properties": {
        "datetime": "2026-01-01T22:30:45Z",
        "platform": "sentinel-1",
    },
    "assets": {},
}

MOCK_STAC_FEATURE_NO_BBOX = {
    "id": "S2A_MSIL2A_20260102T142741_N0500_R053_T20HNE_20260102T184502",
    "properties": {
        "datetime": "2026-01-02T14:27:41Z",
        "eo:cloud_cover": 15.0,
        "platform": "sentinel-2",
    },
    "assets": {},
}


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


def test_normalise_smap_granule():
    """CMR granule entry maps to SmSceneMeta."""
    result = _normalise_smap_granule(MOCK_CMR_ENTRY)
    assert isinstance(result, SmSceneMeta)
    assert result.scene_id == "SMAP_L3_SM_P_20260101_R18290_001.h5"
    assert result.platform == "smap"
    assert result.bbox == [-61, -34, -60, -33]
    assert result.granule_ur == "SMAP_L3_SM_P_20260101_R18290_001.h5"


def test_normalise_smap_no_boxes_falls_back():
    """CMR granule without boxes uses configured ingestion bbox."""
    result = _normalise_smap_granule(MOCK_CMR_ENTRY_NO_BOXES)
    assert result.scene_id == "SMAP_L3_SM_P_20260102_R18290_001.h5"
    assert len(result.bbox) == 4  # falls back to INGESTION_BBOX


def test_normalise_sentinel_feature():
    """STAC feature maps to SentinelSceneMeta."""
    result = _normalise_sentinel_feature(MOCK_STAC_FEATURE)
    assert isinstance(result, SentinelSceneMeta)
    assert result.scene_id == MOCK_STAC_FEATURE["id"]
    assert result.cloud_cover == 8.5
    assert result.platform == "sentinel-2"
    assert result.thumbnail_url is not None
    assert "thumbnail.jpg" in result.thumbnail_url
    assert result.bbox == [-61.0, -34.0, -60.0, -33.0]


def test_normalise_sentinel_s1_no_cloud():
    """Sentinel-1 feature has no cloud_cover (SAR)."""
    result = _normalise_sentinel_feature(MOCK_STAC_FEATURE_S1)
    assert result.cloud_cover is None
    assert result.platform == "sentinel-1"
    assert result.thumbnail_url is None


def test_normalise_sentinel_no_bbox_falls_back():
    """STAC feature without bbox uses configured ingestion bbox."""
    result = _normalise_sentinel_feature(MOCK_STAC_FEATURE_NO_BBOX)
    assert result.cloud_cover == 15.0
    assert len(result.bbox) == 4


# ---------------------------------------------------------------------------
# SmapService
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smap_search_returns_scenes(test_session: AsyncSession):
    """SmapService.search calls CMR, normalises, and persists."""
    with patch(
        "argplant.modules.satellite.service.EarthdataClient.search_smap",
        new_callable=AsyncMock,
    ) as mock_search:
        mock_search.return_value = [MOCK_CMR_ENTRY, MOCK_CMR_ENTRY_NO_BOXES]

        service = SmapService()
        results = await service.search(
            test_session,
            bbox="-61,-34,-60,-33",
            start_date="2026-01-01",
            end_date="2026-01-31",
        )

        assert len(results) == 2
        assert all(isinstance(r, SmSceneMeta) for r in results)
        mock_search.assert_called_once_with("-61,-34,-60,-33", "2026-01-01", "2026-01-31")

        # Verify persistence
        from argplant.modules.satellite.repository import SatelliteSceneRepo
        repo = SatelliteSceneRepo()
        saved = await repo.find_by_scene_id(test_session, results[0].scene_id)
        assert saved is not None
        assert saved.platform == "smap"


@pytest.mark.asyncio
async def test_smap_search_http_error_propagates(test_session: AsyncSession):
    """CMR HTTP error is re-raised."""
    with patch(
        "argplant.modules.satellite.service.EarthdataClient.search_smap",
        new_callable=AsyncMock,
    ) as mock_search:
        mock_search.side_effect = httpx.ConnectError("CMR unreachable")

        service = SmapService()
        with pytest.raises(httpx.ConnectError, match="CMR unreachable"):
            await service.search(
                test_session,
                bbox="-61,-34,-60,-33",
                start_date="2026-01-01",
                end_date="2026-01-31",
            )


# ---------------------------------------------------------------------------
# SentinelService
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sentinel_search_returns_scenes(test_session: AsyncSession):
    """SentinelService.search_catalog calls CDSE STAC, normalises, and persists."""
    with patch(
        "argplant.modules.satellite.service.CdseClient.search_sentinel",
        new_callable=AsyncMock,
    ) as mock_search:
        mock_search.return_value = [MOCK_STAC_FEATURE, MOCK_STAC_FEATURE_S1]

        service = SentinelService()
        results = await service.search_catalog(
            test_session,
            platform="sentinel-2",
            bbox="-61,-34,-60,-33",
            start_date="2026-01-01",
            end_date="2026-01-31",
            max_cloud=10.0,
        )

        assert len(results) == 2
        assert all(isinstance(r, SentinelSceneMeta) for r in results)
        mock_search.assert_called_once_with(
            "-61,-34,-60,-33", "2026-01-01", "2026-01-31", "sentinel-2", 10.0
        )

        # Verify persistence
        from argplant.modules.satellite.repository import SatelliteSceneRepo
        repo = SatelliteSceneRepo()
        saved = await repo.find_by_scene_id(test_session, results[0].scene_id)
        assert saved is not None
        assert saved.platform == "sentinel-2"


@pytest.mark.asyncio
async def test_sentinel_search_http_error_propagates(test_session: AsyncSession):
    """CDSE HTTP error is re-raised."""
    with patch(
        "argplant.modules.satellite.service.CdseClient.search_sentinel",
        new_callable=AsyncMock,
    ) as mock_search:
        mock_search.side_effect = httpx.HTTPStatusError(
            "unauthorized", request=AsyncMock(), response=AsyncMock(status_code=401)
        )

        service = SentinelService()
        with pytest.raises(httpx.HTTPStatusError):
            await service.search_catalog(
                test_session,
                platform="sentinel-2",
                bbox="-61,-34,-60,-33",
                start_date="2026-01-01",
                end_date="2026-01-31",
            )


@pytest.mark.asyncio
async def test_sentinel_validate_scene_not_found(test_session: AsyncSession):
    """validate_scene returns None for unknown scene_id."""
    service = SentinelService()
    result = await service.validate_scene(test_session, "nonexistent_scene")
    assert result is None


@pytest.mark.asyncio
async def test_sentinel_validate_scene_found(test_session: AsyncSession):
    """validate_scene returns the scene when it exists."""
    scene = SatelliteScene(
        scene_id="S1A_test",
        platform="sentinel-1",
        bbox=[-61, -34, -60, -33],
        acquisition_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        cloud_cover=None,
        metadata={"id": "S1A_test"},
    )
    test_session.add(scene)
    await test_session.flush()

    service = SentinelService()
    result = await service.validate_scene(test_session, "S1A_test")
    assert result is not None
    assert result.scene_id == "S1A_test"


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repo_find_by_bbox_filters_by_date(test_session: AsyncSession):
    """find_by_bbox filters scenes by platform and date range."""
    from argplant.modules.satellite.repository import SatelliteSceneRepo

    repo = SatelliteSceneRepo()

    # Insert two scenes: one in range, one out of range
    in_range = SatelliteScene(
        scene_id="s2_in_range",
        platform="sentinel-2",
        bbox=[-61, -34, -60, -33],
        acquisition_date=datetime(2026, 1, 5, tzinfo=timezone.utc),
        cloud_cover=None,
        metadata={},
    )
    out_range = SatelliteScene(
        scene_id="s2_out_range",
        platform="sentinel-2",
        bbox=[-61, -34, -60, -33],
        acquisition_date=datetime(2025, 12, 1, tzinfo=timezone.utc),
        cloud_cover=None,
        metadata={},
    )
    test_session.add_all([in_range, out_range])
    await test_session.flush()

    results = await repo.find_by_bbox(
        test_session,
        bbox=[-61, -34, -60, -33],
        platform="sentinel-2",
        since=datetime(2026, 1, 1, tzinfo=timezone.utc),
        until=datetime(2026, 1, 31, tzinfo=timezone.utc),
    )
    assert len(results) == 1
    assert results[0].scene_id == "s2_in_range"


@pytest.mark.asyncio
async def test_repo_update_file_path(test_session: AsyncSession):
    """update_file_path persists the download path."""
    from argplant.modules.satellite.repository import SatelliteSceneRepo

    repo = SatelliteSceneRepo()
    scene = SatelliteScene(
        scene_id="s2_download",
        platform="sentinel-2",
        bbox=[-61, -34, -60, -33],
        acquisition_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        cloud_cover=None,
        metadata={},
        file_path=None,
    )
    test_session.add(scene)
    await test_session.flush()

    updated = await repo.update_file_path(test_session, "s2_download", "/data/s2/product.zip")
    assert updated is not None
    assert updated.file_path == "/data/s2/product.zip"


@pytest.mark.asyncio
async def test_repo_upsert_inserts_and_updates(test_session: AsyncSession):
    """upsert inserts a new scene and updates an existing one."""
    from argplant.modules.satellite.repository import SatelliteSceneRepo

    repo = SatelliteSceneRepo()

    # Insert
    scene = SatelliteScene(
        scene_id="s2_upsert",
        platform="sentinel-2",
        bbox=[-61, -34, -60, -33],
        acquisition_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        cloud_cover=5.0,
        metadata={},
    )
    result = await repo.upsert(test_session, scene)
    assert result.cloud_cover == 5.0

    # Update
    scene.cloud_cover = 10.0
    result = await repo.upsert(test_session, scene)
    assert result.cloud_cover == 10.0

    # Only one row should exist
    all_scenes = await repo.find_by_bbox(
        test_session,
        bbox=[-61, -34, -60, -33],
        platform="sentinel-2",
        since=datetime(2025, 1, 1, tzinfo=timezone.utc),
        until=datetime(2027, 12, 31, tzinfo=timezone.utc),
    )
    assert len(all_scenes) == 1
