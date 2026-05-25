"""Tests for Pydantic schema validation and serialization."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.schemas.analysis import (
    AnalysisSummary,
    AnalysisListResponse,
    AnalysisDetailResponse,
    AnalysisLatestResponse,
    AnalysisSummaryResponse,
)
from backend.schemas.regions import RegionListItem, RegionDetail, RegionListResponse
from backend.schemas.geo import GeoJSONFeature, GeoJSONFeatureCollection
from backend.schemas.alerts import AlertItem, AlertListResponse, ActiveAlertCountResponse
from backend.schemas.jobs import JobItem, JobTriggerRequest, JobTriggerResponse

pytestmark = pytest.mark.asyncio


def _ts() -> datetime:
    return datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)


class TestAnalysisSummary:
    """AnalysisSummary schema tests."""

    async def test_valid_minimal(self) -> None:
        """GIVEN only required fields, THEN schema is valid."""
        eid = str(uuid4())
        summary = AnalysisSummary(execution_id=eid)
        assert summary.execution_id == eid
        assert summary.orchestrator_area is None

    async def test_with_all_fields(self) -> None:
        """GIVEN all fields, THEN schema includes them."""
        eid = str(uuid4())
        summary = AnalysisSummary(
            execution_id=eid,
            orchestrator_area="hydric-environmental",
            agent_code="AGENT-HYD-SM-001",
            workflow_id="wf-123",
            status="completed",
            confidence_score=0.85,
            finished_at=_ts(),
        )
        assert summary.orchestrator_area == "hydric-environmental"
        assert summary.confidence_score == 0.85


class TestAnalysisListResponse:
    """AnalysisListResponse schema tests."""

    async def test_empty_list(self) -> None:
        """GIVEN no items, THEN response has empty list and total=0."""
        resp = AnalysisListResponse(items=[], total=0, page=1, limit=20)
        assert resp.items == []
        assert resp.total == 0

    async def test_with_items(self) -> None:
        """GIVEN items, THEN response wraps them."""
        items = [AnalysisSummary(execution_id=str(uuid4())) for _ in range(2)]
        resp = AnalysisListResponse(items=items, total=2, page=1, limit=20)
        assert len(resp.items) == 2


class TestRegionListItem:
    """RegionListItem schema tests."""

    async def test_valid_minimal(self) -> None:
        """GIVEN required fields only, THEN valid."""
        item = RegionListItem(id=1, name="Córdoba")
        assert item.id == 1
        assert item.name == "Córdoba"
        assert item.bbox == []

    async def test_with_all_fields(self) -> None:
        """GIVEN all fields, THEN valid."""
        item = RegionListItem(
            id=1,
            name="Córdoba",
            region_type="administrative",
            country="Argentina",
            province="Córdoba",
            bbox=[-64.5, -31.5, -64.0, -31.0],
            is_active=True,
            created_at=_ts(),
        )
        assert item.country == "Argentina"
        assert item.bbox == [-64.5, -31.5, -64.0, -31.0]
        assert item.is_active is True


class TestGeoJSON:
    """GeoJSON schema tests."""

    async def test_feature_collection_structure(self) -> None:
        """GIVEN features, THEN FeatureCollection has correct GeoJSON structure."""
        feature = GeoJSONFeature(
            geometry={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
            properties={"zone_id": "z01", "value": 0.5},
        )
        fc = GeoJSONFeatureCollection(features=[feature], metadata={"date": "2024-01-15"})
        assert fc.type == "FeatureCollection"
        assert len(fc.features) == 1
        assert fc.features[0].geometry["type"] == "Polygon"
        assert fc.features[0].properties["zone_id"] == "z01"


class TestAlerts:
    """Alert schema tests."""

    async def test_alert_item_minimal(self) -> None:
        """GIVEN required fields, THEN alert is valid."""
        alert = AlertItem(
            id=1,
            alert_type="drought",
            severity="critical",
            title="Severe drought",
            status="active",
            region_id=1,
        )
        assert alert.severity == "critical"
        assert alert.title == "Severe drought"

    async def test_active_alert_count(self) -> None:
        """GIVEN severity counts, THEN response groups correctly."""
        counts = ActiveAlertCountResponse(critical=2, severe=5, warning=3, total=10)
        assert counts.critical == 2
        assert counts.severe == 5
        assert counts.total == 10


class TestJobs:
    """Job schema tests."""

    async def test_job_item_minimal(self) -> None:
        """GIVEN required fields, THEN job is valid."""
        job = JobItem(
            id="job-001",
            status="pending",
        )
        assert job.status == "pending"
        assert job.id == "job-001"

    async def test_trigger_request(self) -> None:
        """GIVEN valid trigger request, THEN serializes correctly."""
        req = JobTriggerRequest(
            region_id="cordoba_pilot",
            date_from="2024-01-01",
            date_to="2024-01-15",
        )
        assert req.region_id == "cordoba_pilot"
        assert req.date_from == "2024-01-01"
