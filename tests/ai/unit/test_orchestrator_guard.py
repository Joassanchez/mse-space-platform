"""Unit tests for M4 backward-compatibility guard in _node_build_context.

Tests:
- Existing workflow WITHOUT pre-built context still calls build_context
- Workflow WITH pre-built context skips build_context
- Empty context dict still triggers normal build_context (edge case)
- Mock the ContextEngine to verify whether build_context was called
"""

from unittest.mock import MagicMock, patch

import pytest

from src.ai.application.orchestrator import LangGraphOrchestrator, WorkflowGraphState


@pytest.fixture
def mock_context_engine():
    """Mock ContextEngine."""
    engine = MagicMock()
    engine.build_context.return_value = {
        "regions": [{"id": 1, "name": "Test Region"}],
        "indicators": [],
        "risk_assessments": [],
        "metadata": {"entity_counts": {"regions": 1}},
        "warnings": [],
    }
    return engine


@pytest.fixture
def mock_state_manager():
    """Mock StateManager."""
    manager = MagicMock()
    manager.create_state.return_value = 1
    manager.update_state.return_value = None
    manager.persist_trace.return_value = 1
    return manager


@pytest.fixture
def mock_agent_runtime():
    """Mock AgentRuntime."""
    runtime = MagicMock()
    runtime.execute.return_value = {
        "conclusion": "Test conclusion",
        "confidence": 0.8,
    }
    runtime.load_agent.return_value = MagicMock()
    return runtime


@pytest.fixture
def mock_consolidator():
    """Mock ResponseConsolidator."""
    consolidator = MagicMock()
    consolidator.consolidate.return_value = {
        "conclusion": "Consolidated result",
        "confidence": 0.8,
        "agent_contributions": [],
        "conflicts": [],
    }
    return consolidator


@pytest.fixture
def orchestrator(mock_context_engine, mock_state_manager, mock_agent_runtime, mock_consolidator):
    """Create LangGraphOrchestrator with all mocks."""
    with patch("src.ai.application.orchestrator.HAS_LANGGRAPH", True):
        with patch("src.ai.application.orchestrator.StateGraph") as mock_graph_cls:
            mock_graph = MagicMock()
            mock_graph.add_node = MagicMock()
            mock_graph.add_edge = MagicMock()
            mock_graph.set_entry_point = MagicMock()
            mock_compiled = MagicMock()
            mock_compiled.invoke.return_value = {
                "workflow_id": "wf-001",
                "state_id": 1,
                "status": "completed",
                "agent_outputs": [{"conclusion": "Test", "confidence": 0.8}],
                "consolidated_response": {"conclusion": "Consolidated", "confidence": 0.8},
                "messages": [],
            }
            mock_graph.compile.return_value = mock_compiled
            mock_graph_cls.return_value = mock_graph

            return LangGraphOrchestrator(
                context_engine=mock_context_engine,
                state_manager=mock_state_manager,
                agent_runtime=mock_agent_runtime,
                consolidator=mock_consolidator,
            )


class TestOrchestratorGuardBackwardCompatibility:
    """Test M4 backward-compatibility guard in _node_build_context."""

    def test_without_prebuilt_context_calls_build_context(
        self, orchestrator, mock_context_engine
    ):
        """Workflow WITHOUT pre-built context still calls build_context (M4 behavior)."""
        state: WorkflowGraphState = {
            "workflow_id": "wf-m4-001",
            "region_ids": [1, 2],
            "context": {},  # Empty dict — M4 default
            "agent_manifests": [],
            "agent_outputs": [],
            "consolidated_response": {},
            "status": "pending",
            "error": None,
            "messages": [],
        }

        result = orchestrator._node_build_context(state)

        # build_context MUST have been called
        mock_context_engine.build_context.assert_called_once_with(
            region_ids=[1, 2],
            indicator_codes=None,
        )
        # Result context should be populated
        assert "regions" in result["context"]
        assert len(result["context"]["regions"]) == 1

    def test_with_prebuilt_context_skips_build_context(
        self, orchestrator, mock_context_engine
    ):
        """Workflow WITH pre-built context skips build_context (M5 area orchestrator)."""
        prebuilt = {
            "regions": [{"id": 10, "name": "Pre-built Region"}],
            "indicators": [{"code": "SMAP_SOIL_MOISTURE"}],
            "metadata": {"source": "hydric-environmental-orchestrator"},
        }
        state: WorkflowGraphState = {
            "workflow_id": "wf-m5-001",
            "region_ids": [10],
            "context": prebuilt,  # Pre-built context from area orchestrator
            "agent_manifests": [],
            "agent_outputs": [],
            "consolidated_response": {},
            "status": "pending",
            "error": None,
            "messages": [],
        }

        result = orchestrator._node_build_context(state)

        # build_context MUST NOT have been called
        mock_context_engine.build_context.assert_not_called()
        # Context should remain the pre-built one
        assert result["context"] is prebuilt
        assert result["context"]["regions"][0]["id"] == 10
        # Message should indicate skip
        assert any("pre-built context" in m for m in result["messages"])

    def test_empty_context_dict_triggers_build_context(
        self, orchestrator, mock_context_engine
    ):
        """Edge case: empty context dict {} still triggers normal build_context."""
        state: WorkflowGraphState = {
            "workflow_id": "wf-edge-001",
            "region_ids": [5],
            "context": {},  # Empty dict, not None — should still build
            "agent_manifests": [],
            "agent_outputs": [],
            "consolidated_response": {},
            "status": "pending",
            "error": None,
            "messages": [],
        }

        result = orchestrator._node_build_context(state)

        # build_context MUST have been called (empty dict is falsy for len check)
        mock_context_engine.build_context.assert_called_once_with(
            region_ids=[5],
            indicator_codes=None,
        )
        assert "regions" in result["context"]

    def test_none_context_triggers_build_context(
        self, orchestrator, mock_context_engine
    ):
        """Edge case: None context triggers normal build_context."""
        state: WorkflowGraphState = {
            "workflow_id": "wf-edge-002",
            "region_ids": [3],
            "context": None,  # type: ignore[typeddict-item]
            "agent_manifests": [],
            "agent_outputs": [],
            "consolidated_response": {},
            "status": "pending",
            "error": None,
            "messages": [],
        }

        result = orchestrator._node_build_context(state)

        # build_context MUST have been called
        mock_context_engine.build_context.assert_called_once_with(
            region_ids=[3],
            indicator_codes=None,
        )

    def test_prebuilt_context_preserves_region_ids(
        self, orchestrator, mock_context_engine
    ):
        """Pre-built context path preserves original region_ids in state."""
        prebuilt = {"regions": [{"id": 99}], "indicators": []}
        state: WorkflowGraphState = {
            "workflow_id": "wf-m5-002",
            "region_ids": [99],
            "context": prebuilt,
            "agent_manifests": [],
            "agent_outputs": [],
            "consolidated_response": {},
            "status": "pending",
            "error": None,
            "messages": [],
        }

        result = orchestrator._node_build_context(state)

        # region_ids should be unchanged
        assert result["region_ids"] == [99]
        # Context should be the same pre-built dict
        assert result["context"] is prebuilt
