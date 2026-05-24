"""Unit tests for HydricEnvironmentalOrchestrator.

Tests:
- Complete execution with pre-built context
- Partial data (some agents degraded)
- Empty context (graceful degradation)
- Confidence degradation logic
- Data completeness calculation
"""

from unittest.mock import MagicMock, patch

import pytest

from src.ai.application.area_orchestrators.hydric_environmental.orchestrator import (
    HydricEnvironmentalOrchestrator,
)
from src.ai.domain.models import (
    DroughtSignal,
    HydricCondition,
    HydricEnvironmentalOutput,
    SoilMoistureStatus,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mock_context_engine():
    """Mock ContextEngine."""
    engine = MagicMock()
    engine.build_context.return_value = {
        "regions": [{"id": 1, "name": "Test Region", "country": "AR"}],
        "indicators": [
            {"indicator_code": "SM_SURFACE", "value": 0.35, "region_id": 1},
            {"indicator_code": "SM_ROOTZONE", "value": 0.28, "region_id": 1},
            {"indicator_code": "RAINFALL_30D", "value": 120.0, "region_id": 1},
            {"indicator_code": "RAINFALL_ANOMALY", "value": 0.15, "region_id": 1},
            {"indicator_code": "SPI_30D", "value": -0.8, "region_id": 1},
            {"indicator_code": "SPI_90D", "value": -1.2, "region_id": 1},
        ],
        "risk_assessments": [],
        "metadata": {"entity_counts": {"regions": 1, "indicators": 6}},
        "warnings": [],
    }
    return engine


@pytest.fixture
def mock_orchestrator():
    """Mock LangGraphOrchestrator."""
    orchestrator = MagicMock()
    orchestrator.execute_workflow.return_value = {
        "workflow_id": "wf-test-001",
        "state_id": 1,
        "status": "completed",
        "context": {
            "regions": [{"id": 1, "name": "Test Region"}],
            "indicators": [],
        },
        "agent_manifests": [
            {"name": "soil_moisture"},
            {"name": "weather"},
            {"name": "drought"},
        ],
        "agent_outputs": [
            {
                "conclusion": "Soil moisture is normal.",
                "confidence_score": 0.85,
                "sm_surface_status": "normal",
                "sm_rootzone_status": "normal",
                "data_completeness": 1.0,
                "natural_language_output": "Soil moisture conditions are normal.",
            },
            {
                "conclusion": "Rainfall is average.",
                "confidence_score": 0.80,
                "data_completeness": 1.0,
                "natural_language_output": "Rainfall conditions are average.",
            },
            {
                "conclusion": "No drought signal detected.",
                "confidence_score": 0.90,
                "drought_signal": "none",
                "data_completeness": 1.0,
                "natural_language_output": "No drought conditions detected.",
            },
        ],
        "consolidated_response": {
            "conclusion": "All agents completed successfully.",
            "confidence_score": 0.85,
            "agent_contributions": [],
        },
        "messages": ["Skipped build_context: using pre-built context (1 regions)"],
    }
    return orchestrator


@pytest.fixture
def mock_state_manager():
    """Mock StateManagerImpl."""
    manager = MagicMock()
    manager.persist_agent_execution.return_value = 1
    return manager


@pytest.fixture
def orchestrator(mock_context_engine, mock_orchestrator, mock_state_manager):
    """Create HydricEnvironmentalOrchestrator with all mocks."""
    return HydricEnvironmentalOrchestrator(
        context_engine=mock_context_engine,
        orchestrator=mock_orchestrator,
        state_manager=mock_state_manager,
    )


# ============================================================
# Tests: Complete execution
# ============================================================


class TestHydricOrchestratorCompleteExecution:
    """Test full execution with complete context and all agents."""

    def test_execute_calls_context_engine(self, orchestrator, mock_context_engine):
        """execute() MUST call ContextEngine.build_context first."""
        result = orchestrator.execute(region_ids=[1], indicator_codes=["SM_INDEX"])

        mock_context_engine.build_context.assert_called_once_with(
            [1], ["SM_INDEX"]
        )

    def test_execute_calls_orchestrator_with_context(
        self, orchestrator, mock_orchestrator
    ):
        """execute() MUST call LangGraphOrchestrator with pre-built context."""
        result = orchestrator.execute(region_ids=[1])

        mock_orchestrator.execute_workflow.assert_called_once()
        call_kwargs = mock_orchestrator.execute_workflow.call_args
        assert call_kwargs.kwargs["context"] is not None
        assert len(call_kwargs.kwargs["context"].get("regions", [])) == 1

    def test_execute_returns_hydric_output(self, orchestrator):
        """execute() MUST return HydricEnvironmentalOutput."""
        result = orchestrator.execute(region_ids=[1])

        assert isinstance(result, HydricEnvironmentalOutput)
        assert result.area == "hydric_environmental"
        assert result.soil_moisture_status == SoilMoistureStatus.NORMAL
        assert result.drought_signal == DroughtSignal.NONE
        assert result.flood_detected is False
        assert result.confidence_score > 0.0
        assert len(result.subagent_outputs) == 3

    def test_execute_persists_agent_executions(
        self, orchestrator, mock_state_manager
    ):
        """execute() MUST persist 3 agent execution records."""
        orchestrator.execute(region_ids=[1])

        assert mock_state_manager.persist_agent_execution.call_count == 3

    def test_execute_passes_workflow_id(self, orchestrator, mock_orchestrator):
        """execute() MUST pass workflow_id to orchestrator."""
        orchestrator.execute(region_ids=[1], workflow_id="wf-custom-001")

        call_kwargs = mock_orchestrator.execute_workflow.call_args
        assert call_kwargs.kwargs["workflow_id"] == "wf-custom-001"


# ============================================================
# Tests: Partial data / degraded agents
# ============================================================


class TestHydricOrchestratorPartialData:
    """Test execution with partial data (some agents degraded)."""

    def test_degraded_agent_confidence(self, orchestrator, mock_orchestrator):
        """When an agent has low confidence, overall confidence decreases."""
        mock_orchestrator.execute_workflow.return_value["agent_outputs"][0] = {
            "conclusion": "Agent failed: no SMAP data available.",
            "confidence_score": 0.1,
            "data_completeness": 0.0,
            "error": "No SMAP data",
        }

        result = orchestrator.execute(region_ids=[1])

        # Confidence should be degraded (SM agent failed with low completeness)
        assert result.confidence_score < 0.7

    def test_partial_indicators_completeness(
        self, orchestrator, mock_context_engine, mock_orchestrator
    ):
        """When only some indicators are found, completeness reflects that."""
        mock_context_engine.build_context.return_value["indicators"] = [
            {"indicator_code": "SM_SURFACE", "value": 0.35, "region_id": 1},
            # SM_ROOTZONE missing
            {"indicator_code": "RAINFALL_30D", "value": 120.0, "region_id": 1},
            # RAINFALL_ANOMALY missing
            {"indicator_code": "SPI_30D", "value": -0.8, "region_id": 1},
            # SPI_90D missing
        ]

        result = orchestrator.execute(region_ids=[1])

        # Completeness should be 0.5 for each agent (1 of 2 indicators found)
        assert result.data_completeness == pytest.approx(0.5, abs=0.01)

    def test_missing_agent_output_graceful(
        self, orchestrator, mock_orchestrator
    ):
        """When an agent output is missing, defaults are used."""
        mock_orchestrator.execute_workflow.return_value["agent_outputs"] = [
            {
                "conclusion": "Soil moisture normal.",
                "confidence_score": 0.8,
                "sm_surface_status": "normal",
                "data_completeness": 1.0,
            },
            # Weather agent output missing
            # Drought agent output missing
        ]

        result = orchestrator.execute(region_ids=[1])

        # Should not crash — defaults applied
        assert isinstance(result, HydricEnvironmentalOutput)
        assert result.flood_detected is False


# ============================================================
# Tests: Empty context / graceful degradation
# ============================================================


class TestHydricOrchestratorEmptyContext:
    """Test execution with empty or minimal context."""

    def test_empty_indicators_list(
        self, orchestrator, mock_context_engine, mock_orchestrator
    ):
        """When context has no indicators, completeness is 0."""
        mock_context_engine.build_context.return_value["indicators"] = []

        result = orchestrator.execute(region_ids=[1])

        assert result.data_completeness == 0.0

    def test_empty_context_regions(
        self, orchestrator, mock_context_engine, mock_orchestrator
    ):
        """When context has no regions, area defaults to 'unknown'."""
        mock_context_engine.build_context.return_value["regions"] = []
        mock_context_engine.build_context.return_value["indicators"] = []
        # Also update the workflow result context
        mock_orchestrator.execute_workflow.return_value["context"]["regions"] = []

        result = orchestrator.execute(region_ids=[1])

        assert result.area == "hydric_environmental"

    def test_all_agents_degraded_with_empty_context(
        self, orchestrator, mock_context_engine, mock_orchestrator
    ):
        """With empty context, all agents should have low completeness."""
        mock_context_engine.build_context.return_value["indicators"] = []
        mock_orchestrator.execute_workflow.return_value["agent_outputs"] = [
            {
                "conclusion": "No data available.",
                "confidence_score": 0.1,
                "data_completeness": 0.0,
            },
            {
                "conclusion": "No data available.",
                "confidence_score": 0.1,
                "data_completeness": 0.0,
            },
            {
                "conclusion": "No data available.",
                "confidence_score": 0.1,
                "data_completeness": 0.0,
            },
        ]

        result = orchestrator.execute(region_ids=[1])

        # Confidence should be very low with degradation
        assert result.confidence_score <= 0.08  # 0.1 * 0.8 degradation


# ============================================================
# Tests: Confidence degradation logic
# ============================================================


class TestHydricOrchestratorConfidenceDegradation:
    """Test confidence score calculation with degradation."""

    def test_weighted_average_no_degradation(self, orchestrator):
        """When all agents have high completeness, no degradation applied."""
        sm = {"confidence_score": 0.9, "data_completeness": 1.0}
        weather = {"confidence_score": 0.8, "data_completeness": 1.0}
        drought = {"confidence_score": 0.85, "data_completeness": 1.0}

        result = orchestrator._calc_confidence(sm, weather, drought)

        # 0.9*0.4 + 0.8*0.3 + 0.85*0.3 = 0.36 + 0.24 + 0.255 = 0.855
        assert result == pytest.approx(0.855, abs=0.001)

    def test_degradation_when_low_completeness(self, orchestrator):
        """When any agent has completeness < 0.5, degrade by 20%."""
        sm = {"confidence_score": 0.9, "data_completeness": 1.0}
        weather = {"confidence_score": 0.8, "data_completeness": 0.3}  # Below threshold
        drought = {"confidence_score": 0.85, "data_completeness": 1.0}

        result = orchestrator._calc_confidence(sm, weather, drought)

        # 0.855 * 0.8 = 0.684
        assert result == pytest.approx(0.684, abs=0.001)

    def test_degradation_sm_agent_low(self, orchestrator):
        """Degradation triggers when SM agent has low completeness."""
        sm = {"confidence_score": 0.9, "data_completeness": 0.4}
        weather = {"confidence_score": 0.8, "data_completeness": 1.0}
        drought = {"confidence_score": 0.85, "data_completeness": 1.0}

        result = orchestrator._calc_confidence(sm, weather, drought)

        expected = (0.9 * 0.4 + 0.8 * 0.3 + 0.85 * 0.3) * 0.8
        assert result == pytest.approx(expected, abs=0.001)

    def test_degradation_drought_agent_low(self, orchestrator):
        """Degradation triggers when drought agent has low completeness."""
        sm = {"confidence_score": 0.9, "data_completeness": 1.0}
        weather = {"confidence_score": 0.8, "data_completeness": 1.0}
        drought = {"confidence_score": 0.85, "data_completeness": 0.2}

        result = orchestrator._calc_confidence(sm, weather, drought)

        expected = (0.9 * 0.4 + 0.8 * 0.3 + 0.85 * 0.3) * 0.8
        assert result == pytest.approx(expected, abs=0.001)

    def test_no_degradation_at_threshold_boundary(self, orchestrator):
        """Completeness exactly at 0.5 does NOT trigger degradation."""
        sm = {"confidence_score": 0.9, "data_completeness": 0.5}
        weather = {"confidence_score": 0.8, "data_completeness": 0.5}
        drought = {"confidence_score": 0.85, "data_completeness": 0.5}

        result = orchestrator._calc_confidence(sm, weather, drought)

        # No degradation: 0.855
        assert result == pytest.approx(0.855, abs=0.001)

    def test_confidence_capped_at_1(self, orchestrator):
        """Confidence is capped at 1.0."""
        sm = {"confidence_score": 1.0, "data_completeness": 1.0}
        weather = {"confidence_score": 1.0, "data_completeness": 1.0}
        drought = {"confidence_score": 1.0, "data_completeness": 1.0}

        result = orchestrator._calc_confidence(sm, weather, drought)

        assert result <= 1.0


# ============================================================
# Tests: Data completeness calculation
# ============================================================


class TestHydricOrchestratorDataCompleteness:
    """Test _calc_completeness method."""

    def test_all_indicators_found(self, orchestrator, mock_context_engine):
        """When all expected indicators are found, completeness is 1.0."""
        context = mock_context_engine.build_context.return_value

        result = orchestrator._calc_completeness(
            context, {"SM_SURFACE", "SM_ROOTZONE"}
        )

        assert result == 1.0

    def test_partial_indicators_found(self, orchestrator):
        """When only some indicators are found, completeness is partial."""
        context = {
            "indicators": [
                {"indicator_code": "SM_SURFACE", "value": 0.35},
                # SM_ROOTZONE missing
            ]
        }

        result = orchestrator._calc_completeness(
            context, {"SM_SURFACE", "SM_ROOTZONE"}
        )

        assert result == 0.5

    def test_no_indicators_found(self, orchestrator):
        """When no expected indicators are found, completeness is 0.0."""
        context = {
            "indicators": [
                {"indicator_code": "UNRELATED_INDICATOR", "value": 1.0},
            ]
        }

        result = orchestrator._calc_completeness(
            context, {"SM_SURFACE", "SM_ROOTZONE"}
        )

        assert result == 0.0

    def test_empty_indicators_list(self, orchestrator):
        """When indicators list is empty, completeness is 0.0."""
        context = {"indicators": []}

        result = orchestrator._calc_completeness(
            context, {"SM_SURFACE", "SM_ROOTZONE"}
        )

        assert result == 0.0

    def test_no_indicators_key(self, orchestrator):
        """When context has no 'indicators' key, completeness is 0.0."""
        context = {"regions": []}

        result = orchestrator._calc_completeness(
            context, {"SM_SURFACE", "SM_ROOTZONE"}
        )

        assert result == 0.0


# ============================================================
# Tests: Output transformation helpers
# ============================================================


class TestHydricOrchestratorTransformHelpers:
    """Test _extract_sm_status, _extract_drought_signal, _compute_hydric_condition."""

    def test_extract_sm_status_from_field(self, orchestrator):
        """Extract status from sm_surface_status field."""
        output = {"sm_surface_status": "dry"}
        result = orchestrator._extract_sm_status(output)
        assert result == SoilMoistureStatus.DRY

    def test_extract_sm_status_from_conclusion(self, orchestrator):
        """Fallback: extract status from conclusion text."""
        output = {"conclusion": "Soil is critically dry in the region."}
        result = orchestrator._extract_sm_status(output)
        assert result == SoilMoistureStatus.CRITICAL_DRY

    def test_extract_sm_status_unavailable(self, orchestrator):
        """Default to UNAVAILABLE when no status found."""
        output = {"conclusion": "Unknown condition."}
        result = orchestrator._extract_sm_status(output)
        assert result == SoilMoistureStatus.UNAVAILABLE

    def test_extract_drought_signal_from_field(self, orchestrator):
        """Extract signal from drought_signal field."""
        output = {"drought_signal": "moderate"}
        result = orchestrator._extract_drought_signal(output)
        assert result == DroughtSignal.MODERATE

    def test_extract_drought_signal_from_conclusion(self, orchestrator):
        """Fallback: extract signal from conclusion text."""
        output = {"conclusion": "Severe drought conditions detected."}
        result = orchestrator._extract_drought_signal(output)
        assert result == DroughtSignal.SEVERE

    def test_extract_drought_signal_none(self, orchestrator):
        """Default to NONE when no signal found."""
        output = {"conclusion": "All good."}
        result = orchestrator._extract_drought_signal(output)
        assert result == DroughtSignal.NONE

    def test_compute_hydric_condition_critical_sm(self, orchestrator):
        """Critical soil moisture → CRITICAL condition."""
        result = orchestrator._compute_hydric_condition(
            SoilMoistureStatus.CRITICAL_DRY,
            DroughtSignal.NONE,
            {},
        )
        assert result == HydricCondition.CRITICAL

    def test_compute_hydric_condition_severe_drought(self, orchestrator):
        """Severe drought signal → CRITICAL condition."""
        result = orchestrator._compute_hydric_condition(
            SoilMoistureStatus.NORMAL,
            DroughtSignal.SEVERE,
            {},
        )
        assert result == HydricCondition.CRITICAL

    def test_compute_hydric_condition_stressed_dry(self, orchestrator):
        """Dry soil moisture → STRESSED condition."""
        result = orchestrator._compute_hydric_condition(
            SoilMoistureStatus.DRY,
            DroughtSignal.NONE,
            {},
        )
        assert result == HydricCondition.STRESSED

    def test_compute_hydric_condition_moderate_drought(self, orchestrator):
        """Moderate drought → STRESSED condition."""
        result = orchestrator._compute_hydric_condition(
            SoilMoistureStatus.NORMAL,
            DroughtSignal.MODERATE,
            {},
        )
        assert result == HydricCondition.STRESSED

    def test_compute_hydric_condition_optimal(self, orchestrator):
        """All normal → OPTIMAL condition."""
        result = orchestrator._compute_hydric_condition(
            SoilMoistureStatus.NORMAL,
            DroughtSignal.NONE,
            {},
        )
        assert result == HydricCondition.OPTIMAL


# ============================================================
# Tests: NL summary template
# ============================================================


class TestHydricOrchestratorNLSummary:
    """Test _build_nl_summary template rendering."""

    def test_optimal_summary(self, orchestrator):
        """Template renders correctly for optimal conditions."""
        summary = orchestrator._build_nl_summary(
            SoilMoistureStatus.NORMAL,
            DroughtSignal.NONE,
            HydricCondition.OPTIMAL,
            0.85,
        )

        assert "optimal" in summary
        assert "normal" in summary
        assert "no drought" in summary
        assert "85%" in summary

    def test_critical_summary(self, orchestrator):
        """Template renders correctly for critical conditions."""
        summary = orchestrator._build_nl_summary(
            SoilMoistureStatus.CRITICAL_DRY,
            DroughtSignal.SEVERE,
            HydricCondition.CRITICAL,
            0.40,
        )

        assert "critical" in summary
        assert "critically dry" in summary
        assert "severe drought" in summary
