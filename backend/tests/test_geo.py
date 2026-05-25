"""Tests for Geo API endpoints and GeoJSON schemas."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from backend.schemas.geo import GeoJSONFeature, GeoJSONFeatureCollection
from backend.services.geo_service import _raw_geojson, get_region_geometries

pytestmark = pytest.mark.asyncio


class TestGeoSchemas:
    """GeoJSON Pydantic schema tests."""

    async def test_feature_default_type(self) -> None:
        """GIVEN minimal feature, THEN type defaults to Feature."""
        feature = GeoJSONFeature(
            geometry={"type": "Point", "coordinates": [0, 0]},
            properties={"name": "test"},
        )
        assert feature.type == "Feature"
        assert feature.geometry["type"] == "Point"

    async def test_feature_collection(self) -> None:
        """GIVEN features, THEN collection wraps them correctly."""
        features = [
            GeoJSONFeature(
                geometry={"type": "Point", "coordinates": [1, 2]},
                properties={"id": 1},
            )
        ]
        fc = GeoJSONFeatureCollection(features=features, metadata={"source": "test"})
        assert fc.type == "FeatureCollection"
        assert len(fc.features) == 1
        assert fc.metadata == {"source": "test"}

    async def test_feature_collection_no_metadata(self) -> None:
        """GIVEN no metadata, THEN FeatureCollection still valid."""
        fc = GeoJSONFeatureCollection(features=[])
        assert fc.type == "FeatureCollection"
        assert fc.features == []
        assert fc.metadata is None


class TestGeoService:
    """Geo service tests with mocked DB."""

    async def test_raw_geojson_handles_empty(self) -> None:
        """GIVEN empty DB result, THEN returns empty FeatureCollection."""
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.fetchall.return_value = []
        db.execute.return_value = result_mock

        fc = await _raw_geojson(db, "SELECT 1", metadata={"test": True})
        assert len(fc.features) == 0
        assert fc.metadata == {"test": True}

    async def test_get_region_geometries_requires_auth(self, client: AsyncClient) -> None:
        """GIVEN no API key, WHEN GET /api/v1/geo/regions/, THEN 401."""
        response = await client.get("/api/v1/geo/regions/")
        assert response.status_code == 401

    async def test_geo_layers_requires_auth(self, client: AsyncClient) -> None:
        """GIVEN no API key, WHEN GET /api/v1/geo/layers/, THEN 401."""
        response = await client.get("/api/v1/geo/layers/")
        assert response.status_code == 401

    async def test_geo_risk_zones_requires_auth(self, client: AsyncClient) -> None:
        """GIVEN no API key, WHEN GET /api/v1/geo/risk-zones/, THEN 401."""
        response = await client.get("/api/v1/geo/risk-zones/")
        assert response.status_code == 401

    async def test_geo_alerts_requires_auth(self, client: AsyncClient) -> None:
        """GIVEN no API key, WHEN GET /api/v1/geo/alerts/, THEN 401."""
        response = await client.get("/api/v1/geo/alerts/")
        assert response.status_code == 401

    async def test_geo_flood_extent_requires_auth(self, client: AsyncClient) -> None:
        """GIVEN no API key, WHEN GET /api/v1/geo/flood-extent/, THEN 401."""
        response = await client.get("/api/v1/geo/flood-extent/")
        assert response.status_code == 401
