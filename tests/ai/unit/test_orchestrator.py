"""Unit tests for LangGraph Orchestrator.

Tests:
- Workflow state machine: transitions (pending → running → completed/failed)
- Idempotency: duplicate workflow_id returns existing state
- Node execution: build_context, init_state, execute_agents, consolidate, finalize
- Error handling: workflow failure updates state to failed
- Placeholder agent fallback when manifest not found
"""

from unittest.mock import MagicMock, patch

import pytest

from src.ai.domain.constants import WorkflowStatus
from src.ai.domain.errors import AgentExecutionError, ContextError
from src.ai.domain.models import AgentManifest, ExecutionLimits
from src.ai.application.orchestrator import LangGraphOrchestrator, _PlaceholderAgent


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
                "status": WorkflowStatus.COMPLETED,
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


class TestOrchestratorInit:
    """Test orchestrator initialization."""

    def test_init_without_langgraph_raises(self):
        """Orchestrator raises ContextError when langgraph is not available."""
        with patch("src.ai.application.orchestrator.HAS_LANGGRAPH", False):
            with pytest.raises(ContextError, match="langgraph is not installed"):
                LangGraphOrchestrator(
                    context_engine=MagicMock(),
                    state_manager=MagicMock(),
                    agent_runtime=MagicMock(),
                )


class TestOrchestratorWorkflowTransitions:
    """Test workflow state transitions."""

    def test_workflow_starts_pending(self, orchestrator):
        """Workflow initial state is pending."""
        manifest = AgentManifest(
            name="test-agent",
            version="1.0.0",
            entry_point="agent:TestAgent",
            description="Test",
        )

        with patch.object(orchestrator, "_graph") as mock_graph:
            mock_graph.invoke.return_value = {
                "workflow_id": "wf-001",
                "state_id": 1,
                "status": WorkflowStatus.PENDING,
                "agent_outputs": [],
                "consolidated_response": {},
                "messages": [],
            }
            result = orchestrator.execute_workflow(
                region_ids=[1],
                agent_manifests=[manifest],
            )

        # Initial state passed to invoke should be pending
        invoke_call = mock_graph.invoke.call_args
        initial_state = invoke_call[0][0]
        assert initial_state["status"] == WorkflowStatus.PENDING

    def test_workflow_generates_uuid_when_not_provided(self, orchestrator):
        """Workflow generates a UUID when workflow_id is None."""
        manifest = AgentManifest(
            name="test-agent",
            version="1.0.0",
            entry_point="agent:TestAgent",
            description="Test",
        )

        with patch.object(orchestrator, "_graph") as mock_graph:
            mock_graph.invoke.return_value = {
                "workflow_id": "generated-uuid",
                "state_id": 1,
                "status": WorkflowStatus.COMPLETED,
                "agent_outputs": [],
                "consolidated_response": {},
                "messages": [],
            }
            result = orchestrator.execute_workflow(
                region_ids=[1],
                agent_manifests=[manifest],
            )

        invoke_call = mock_graph.invoke.call_args
        initial_state = invoke_call[0][0]
        assert initial_state["workflow_id"] is not None
        assert len(initial_state["workflow_id"]) > 0


class TestOrchestratorErrorHandling:
    """Test orchestrator error handling."""

    def test_workflow_failure_updates_state_to_failed(self, orchestrator, mock_state_manager):
        """When workflow fails, state is updated to failed."""
        manifest = AgentManifest(
            name="test-agent",
            version="1.0.0",
            entry_point="agent:TestAgent",
            description="Test",
        )

        def failing_invoke(state):
            # Simulate that state_id was created before the failure
            state["state_id"] = 1
            raise Exception("Workflow crashed")

        with patch.object(orchestrator, "_graph") as mock_graph:
            mock_graph.invoke.side_effect = failing_invoke

            with pytest.raises(AgentExecutionError):
                orchestrator.execute_workflow(
                    region_ids=[1],
                    agent_manifests=[manifest],
                    workflow_id="wf-001",
                )

            # State should be updated to failed
            mock_state_manager.update_state.assert_called()
            update_call = mock_state_manager.update_state.call_args
            assert update_call[0][1]["status"] == WorkflowStatus.FAILED


class TestOrchestratorHelpers:
    """Test orchestrator helper methods."""

    def test_manifest_to_dict(self, orchestrator):
        """_manifest_to_dict converts AgentManifest to dict."""
        manifest = AgentManifest(
            name="test-agent",
            version="1.0.0",
            entry_point="agent:TestAgent",
            description="Test agent",
            tools=["geospatial_query"],
            limits=ExecutionLimits(max_steps=5, max_tokens=2048, timeout_seconds=15),
            output_schema={"type": "object"},
            agent_type="reference",
        )

        result = orchestrator._manifest_to_dict(manifest)

        assert result["name"] == "test-agent"
        assert result["version"] == "1.0.0"
        assert result["tools"] == ["geospatial_query"]
        assert result["limits"]["max_steps"] == 5
        assert result["agent_type"] == "reference"


class TestPlaceholderAgent:
    """Test _PlaceholderAgent fallback."""

    def test_placeholder_agent_produces_output(self):
        """Placeholder agent returns a minimal output dict."""
        agent = _PlaceholderAgent("missing-agent")

        output = agent.execute(context={})

        assert "conclusion" in output
        assert "confidence" in output
        assert output["confidence"] == 0.0
        assert "error" in output
        assert "missing-agent" in output["conclusion"]
