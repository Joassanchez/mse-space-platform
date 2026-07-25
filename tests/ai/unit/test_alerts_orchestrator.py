"""Tests for AlertsOrchestrator."""

from unittest.mock import MagicMock
import pytest
from src.ai.application.area_orchestrators.alerts.orchestrator import AlertsOrchestrator


@pytest.fixture
def mocks():
    ce = MagicMock()
    ce.build_context.return_value = {"regions": [], "indicators": [], "risk_assessments": [], "metadata": {}, "warnings": []}

    mo = MagicMock()
    mo.execute_workflow.return_value = {
        "workflow_id": "wf-alert-001", "state_id": 1, "status": "completed",
        "context": {"regions": [{"id": 1}]},
        "agent_manifests": [
            {"name": "alert_classification"}, {"name": "risk_communication"},
            {"name": "operational_recommendations"}, {"name": "executive_summary"},
        ],
        "agent_outputs": [
            {"severity": "alert", "event_type": "drought", "confidence_score": 0.8, "data_completeness": 1.0, "natural_language_output": "Alert"},
            {"messages": {"municipalities": "msg"}, "confidence_score": 0.8, "data_completeness": 1.0, "natural_language_output": "Comm"},
            {"recommended_actions": [{"action": "Activar protocolo"}], "confidence_score": 0.7, "data_completeness": 1.0, "natural_language_output": "Recs"},
            {"executive_summary": "Resumen ejecutivo", "situation": "", "risk": "", "actions": "", "confidence_score": 0.8, "data_completeness": 1.0, "natural_language_output": "Exec"},
        ],
        "consolidated_response": {"conclusion": "OK", "confidence": 0.8},
        "messages": [],
    }
    sm = MagicMock()
    sm.persist_agent_execution.return_value = "00000000-0000-0000-0000-000000000001"
    return ce, mo, sm


@pytest.fixture
def orch(mocks):
    return AlertsOrchestrator(*mocks)


class TestAlertsOrchestrator:
    def test_execute_calls_context_engine(self, orch, mocks):
        orch.execute(region_ids=[1], hydric_output={}, risk_output={})
        mocks[0].build_context.assert_called_once()

    def test_execute_calls_orchestrator(self, orch, mocks):
        orch.execute(region_ids=[1], hydric_output={}, risk_output={})
        mocks[1].execute_workflow.assert_called_once()

    def test_execute_returns_alert_output(self, orch):
        r = orch.execute(region_ids=[1], hydric_output={}, risk_output={})
        assert r.severity.value == "alert"
        assert r.event_type == "drought"
        assert len(r.messages) > 0
        assert r.executive_summary

    def test_execute_persists_executions(self, orch, mocks):
        orch.execute(region_ids=[1], hydric_output={}, risk_output={})
        assert mocks[2].persist_agent_execution.call_count >= 1
