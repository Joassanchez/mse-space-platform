"""Tests for service layer — region and analysis services."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.db.models import Region, AgentExecution
from backend.services.region_service import get_regions, get_region
from backend.services.analysis_service import list_analysis, get_analysis_detail, get_latest_analysis

pytestmark = pytest.mark.asyncio


def _fake_region(**overrides) -> Region:
    """Create a fake Region model instance with defaults."""
    data = {
        "id": 1,
        "name": "Córdoba Pilot",
        "region_type": "administrative",
        "country": "Argentina",
        "province": "Córdoba",
        "bbox": [-64.5, -31.5, -64.0, -31.0] if "bbox" not in overrides else None,
        "area_km2": 1500.5,
        "extra_metadata": {"key": "value"},
        "is_active": True,
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
    }
    data.update(overrides)
    return Region(**{k: v for k, v in data.items()})


def _fake_execution(**overrides) -> AgentExecution:
    """Create a fake AgentExecution model instance with defaults."""
    data = {
        "id": str(uuid4()),
        "agent_code": "AGENT-HYD-SM-001",
        "orchestrator_area": "hydric-environmental",
        "workflow_id": "wf-123",
        "context_payload": None,
        "structured_output": {"overall_condition": "good"},
        "natural_language_output": "All clear",
        "confidence_score": 0.85,
        "data_completeness": 0.92,
        "llm_model_used": "gpt-4",
        "started_at": datetime(2024, 1, 15, 8, 0, tzinfo=timezone.utc),
        "finished_at": datetime(2024, 1, 15, 8, 30, tzinfo=timezone.utc),
        "error_message": None,
        "status": "completed",
        "created_at": datetime(2024, 1, 15, 8, 0, tzinfo=timezone.utc),
    }
    data.update(overrides)
    return AgentExecution(**data)


def _mock_scalar_result(rows: list) -> MagicMock:
    """Create a mock DB result that returns scalar().all()."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


def _mock_scalar_one_or_none(row) -> MagicMock:
    """Create a mock DB result that returns scalar_one_or_none()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    return result


def _mock_count_result(count: int) -> MagicMock:
    """Create a mock DB result for count queries."""
    result = MagicMock()
    result.scalar.return_value = count
    return result


class TestRegionService:
    """Region service tests."""

    async def test_get_regions_returns_list(self) -> None:
        """GIVEN regions in DB, WHEN get_regions called, THEN list of RegionListItem."""
        regions = [_fake_region(id=1, name="R1"), _fake_region(id=2, name="R2")]
        db = AsyncMock()
        db.execute.return_value = _mock_scalar_result(regions)

        result = await get_regions(db)
        assert len(result) == 2
        assert result[0].name == "R1"

    async def test_get_region_returns_detail(self) -> None:
        """GIVEN region exists, WHEN get_region called, THEN RegionDetail."""
        region = _fake_region(id=1)
        db = AsyncMock()
        db.execute.return_value = _mock_scalar_one_or_none(region)

        result = await get_region(db, 1)
        assert result is not None
        assert result.name == "Córdoba Pilot"
        assert result.area_km2 == 1500.5

    async def test_get_region_returns_none_for_missing(self) -> None:
        """GIVEN no region, WHEN get_region called, THEN None."""
        db = AsyncMock()
        db.execute.return_value = _mock_scalar_one_or_none(None)

        result = await get_region(db, 999)
        assert result is None


class TestAnalysisService:
    """Analysis service tests."""

    async def test_list_analysis_returns_paginated(self) -> None:
        """GIVEN executions, WHEN list_analysis, THEN paginated."""
        executions = [
            _fake_execution(id=str(uuid4())),
            _fake_execution(id=str(uuid4())),
        ]
        db = AsyncMock()
        db.execute.side_effect = [
            _mock_count_result(2),
            _mock_scalar_result(executions),
        ]

        result = await list_analysis(db, page=1, limit=10)
        assert len(result.items) == 2
        assert result.total == 2

    async def test_get_analysis_detail(self) -> None:
        """GIVEN execution exists, THEN full detail returned."""
        execution = _fake_execution()
        db = AsyncMock()
        db.execute.return_value = _mock_scalar_one_or_none(execution)

        result = await get_analysis_detail(db, str(execution.id))
        assert result is not None
        assert result.orchestrator_area == "hydric-environmental"
        assert result.structured_output["overall_condition"] == "good"
        assert result.agent_code == "AGENT-HYD-SM-001"

    async def test_get_analysis_detail_not_found(self) -> None:
        """GIVEN unknown execution, THEN returns None."""
        db = AsyncMock()
        db.execute.return_value = _mock_scalar_one_or_none(None)

        result = await get_analysis_detail(db, "unknown")
        assert result is None

    async def test_get_latest_analysis(self) -> None:
        """GIVEN completed execution, THEN returns latest."""
        execution = _fake_execution(status="completed")
        db = AsyncMock()
        db.execute.return_value = _mock_scalar_one_or_none(execution)

        result = await get_latest_analysis(db, area="hydric-environmental")
        assert result is not None
        assert result.orchestrator_area == "hydric-environmental"
        assert result.status == "completed"
