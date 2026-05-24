"""Unit tests for RiskOrchestrator."""

from unittest.mock import MagicMock

import pytest

from src.ai.application.area_orchestrators.risk.orchestrator import RiskOrchestrator
from src.ai.domain.models import RiskLevel


@pytest.fixture
def mock_context_engine():
    engine = MagicMock()
    engine.build_context.return_value = {
        "regions": [{"id": 1, "name": "Test", "metadata": {"population_density": 0.5}}],
        "indicators": [],
        "risk_assessments": [],
        "metadata": {"entity_counts": {}},
        "warnings": [],
    }
    return engine


@pytest.fixture
def mock_orchestrator():
    orch = MagicMock()
    orch.execute_workflow.return_value = {
        "workflow_id": "wf-risk-001",
        "state_id": 1,
        "status": "completed",
        "context": {"regions": [{"id": 1, "name": "Test"}], "indicators": []},
        "agent_manifests": [
            {"name": "risk_classification"},
            {"name": "territorial_prioritization"},
            {"name": "predictive_scenarios"},
        ],
        "agent_outputs": [
            {"risk_level": "high", "risk_score": 0.72, "confidence_score": 0.7,
             "data_completeness": 0.8, "natural_language_output": "Risk: high"},
            {"priority_zones": [{"zone_id": "1", "zone_name": "Test", "priority_score": 0.8}],
             "ranking": ["Test"], "confidence_score": 0.7, "data_completeness": 0.9,
             "natural_language_output": "Priority: Test"},
            {"scenarios": [{"horizon_days": 7, "scenario_type": "probable", "risk_level": "high"}],
             "confidence_score": 0.6, "data_completeness": 0.7,
             "natural_language_output": "Scenarios: 1"},
        ],
        "consolidated_response": {"conclusion": "All agents completed", "confidence": 0.7},
        "messages": [],
    }
    return orch


@pytest.fixture
def mock_state_manager():
    sm = MagicMock()
    sm.persist_agent_execution.return_value = "00000000-0000-0000-0000-000000000001"
    return sm


@pytest.fixture
def orchestrator(mock_context_engine, mock_orchestrator, mock_state_manager):
    return RiskOrchestrator(mock_context_engine, mock_orchestrator, mock_state_manager)


class TestRiskOrchestrator:
    def test_execute_calls_context_engine(self, orchestrator, mock_context_engine):
        orchestrator.execute(
            region_ids=[1],
            hydric_output={"overall_hydric_condition": "moderate"},
        )
        mock_context_engine.build_context.assert_called_once()

    def test_execute_calls_orchestrator(self, orchestrator, mock_orchestrator):
        orchestrator.execute(
            region_ids=[1],
            hydric_output={"overall_hydric_condition": "moderate"},
        )
        mock_orchestrator.execute_workflow.assert_called_once()

    def test_execute_returns_risk_output(self, orchestrator):
        result = orchestrator.execute(
            region_ids=[1],
            hydric_output={"overall_hydric_condition": "moderate"},
        )
        assert result.area == "risk"
        assert isinstance(result.risk_level, RiskLevel)

    def test_execute_persists_executions(self, orchestrator, mock_state_manager):
        orchestrator.execute(
            region_ids=[1],
            hydric_output={"overall_hydric_condition": "moderate"},
        )
        assert mock_state_manager.persist_agent_execution.call_count >= 1
