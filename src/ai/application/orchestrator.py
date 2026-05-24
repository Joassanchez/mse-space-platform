"""LangGraph Orchestrator for the AI ecosystem (Módulo 4).

Defines the workflow graph, state machine, and step orchestration.
The orchestrator coordinates Context Engine + State Manager + Agent Runtime
to execute multi-agent workflows with explicit state transitions.

This orchestrator does NOT replace the existing GeospatialOrchestrator (M3).
It reads from M3 outputs via the Context Engine and coordinates AI agents.
"""

import logging
import uuid
from typing import Any, Callable, Optional

try:
    from typing_extensions import TypedDict
except ImportError:
    from typing import TypedDict  # Python 3.11+

try:
    from langgraph.graph import StateGraph, END
    from langgraph.graph.message import add_messages

    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False
    StateGraph = Any  # type: ignore
    END = "__end__"  # type: ignore

from src.ai.domain.constants import WorkflowStatus
from src.ai.domain.errors import AgentExecutionError, ContextError
from src.ai.domain.interfaces import (
    AgentRuntime,
    ContextEngine,
    StateManager,
)
from src.ai.domain.models import (
    AgentManifest,
    ExecutionLimits,
    WorkflowState,
)
from src.ai.application.response_consolidator import ResponseConsolidator

logger = logging.getLogger(__name__)


# LangGraph workflow state
class WorkflowGraphState(TypedDict, total=False):
    """State carried through the LangGraph workflow graph."""

    workflow_id: str
    state_id: int
    region_ids: list[int]
    indicator_codes: Optional[list[str]]
    context: dict
    agent_manifests: list[dict]
    agent_outputs: list[dict]
    consolidated_response: dict
    status: str
    error: Optional[str]
    messages: list


class LangGraphOrchestrator:
    """LangGraph-based orchestrator for AI workflows.

    Coordinates the execution of multi-agent workflows by:
    1. Building context via Context Engine
    2. Creating and managing workflow state via State Manager
    3. Loading and executing agents via Agent Runtime
    4. Consolidating responses from multiple agents

    The orchestrator is stateless from the ETL pipeline's perspective —
    it reads M3 data but never modifies it.
    """

    def __init__(
        self,
        context_engine: ContextEngine,
        state_manager: StateManager,
        agent_runtime: AgentRuntime,
        consolidator: Optional[ResponseConsolidator] = None,
    ):
        """Initialize the orchestrator with its dependencies.

        Args:
            context_engine: ContextEngine for building geospatial context.
            state_manager: StateManager for persisting workflow state.
            agent_runtime: AgentRuntime for loading and executing agents.
            consolidator: Optional ResponseConsolidator for merging outputs.
        """
        if not HAS_LANGGRAPH:
            raise ContextError(
                "langgraph is not installed. Run: pip install langgraph>=0.2.0"
            )

        self._context_engine = context_engine
        self._state_manager = state_manager
        self._agent_runtime = agent_runtime
        self._consolidator = consolidator or ResponseConsolidator()
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow definition.

        The graph defines the following steps:
        1. build_context: Build geospatial context from M3
        2. init_state: Create workflow state in DB
        3. execute_agents: Load and execute each agent
        4. consolidate: Merge agent outputs into unified response
        5. finalize: Update workflow state to completed/failed

        Returns:
            Compiled LangGraph StateGraph.
        """
        graph = StateGraph(WorkflowGraphState)

        # Add nodes
        graph.add_node("build_context", self._node_build_context)
        graph.add_node("init_state", self._node_init_state)
        graph.add_node("execute_agents", self._node_execute_agents)
        graph.add_node("consolidate", self._node_consolidate)
        graph.add_node("finalize", self._node_finalize)

        # Define edges
        graph.set_entry_point("build_context")
        graph.add_edge("build_context", "init_state")
        graph.add_edge("init_state", "execute_agents")
        graph.add_edge("execute_agents", "consolidate")
        graph.add_edge("consolidate", "finalize")
        graph.add_edge("finalize", END)

        return graph.compile()

    def execute_workflow(
        self,
        region_ids: list[int],
        agent_manifests: list[AgentManifest],
        indicator_codes: Optional[list[str]] = None,
        workflow_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute a complete AI workflow.

        Orchestrates context building, agent execution, and response
        consolidation in a single call.

        Args:
            region_ids: Regions to analyze.
            agent_manifests: Agent manifests to execute.
            indicator_codes: Optional indicator filter for context.
            workflow_id: Optional explicit workflow ID (generated if None).

        Returns:
            Final workflow result dict with consolidated response.

        Raises:
            ContextError: If LangGraph is not available.
            AgentExecutionError: If workflow execution fails.
        """
        wid = workflow_id or str(uuid.uuid4())

        initial_state: WorkflowGraphState = {
            "workflow_id": wid,
            "region_ids": region_ids,
            "indicator_codes": indicator_codes,
            "context": {},
            "agent_manifests": [
                self._manifest_to_dict(m) for m in agent_manifests
            ],
            "agent_outputs": [],
            "consolidated_response": {},
            "status": WorkflowStatus.PENDING,
            "error": None,
            "messages": [],
        }

        try:
            result = self._graph.invoke(initial_state)
            return result
        except Exception as e:
            logger.error(f"Workflow {wid} failed: {e}")
            # Attempt to update state to failed if state_id was created
            if "state_id" in initial_state:
                try:
                    self._state_manager.update_state(
                        initial_state["state_id"],
                        {"status": WorkflowStatus.FAILED},
                    )
                    self._state_manager.persist_trace(
                        initial_state["state_id"],
                        step="workflow_error",
                        action="workflow_failed",
                        result={"error": str(e)},
                    )
                except Exception:
                    logger.warning("Failed to persist workflow error state")

            raise AgentExecutionError(
                agent_id="orchestrator",
                message=str(e),
                step="execute_workflow",
            )

    # ============================================================
    # Graph Nodes
    # ============================================================

    def _node_build_context(self, state: WorkflowGraphState) -> WorkflowGraphState:
        """Node: Build geospatial context from M3 tables.

        Reads regions, indicators, and risk assessments via the
        Context Engine (read-only).

        Args:
            state: Current workflow state.

        Returns:
            Updated state with context populated.
        """
        logger.info(
            f"Workflow {state['workflow_id']}: building context "
            f"for regions {state['region_ids']}"
        )

        context = self._context_engine.build_context(
            region_ids=state["region_ids"],
            indicator_codes=state.get("indicator_codes"),
        )

        state["context"] = context
        state["messages"].append(f"Context built: {len(context.get('regions', []))} regions")
        return state

    def _node_init_state(self, state: WorkflowGraphState) -> WorkflowGraphState:
        """Node: Create workflow state in database.

        Persists the initial workflow state with status=running.

        Args:
            state: Current workflow state.

        Returns:
            Updated state with state_id populated.
        """
        logger.info(f"Workflow {state['workflow_id']}: initializing state")

        state_id = self._state_manager.create_state(
            workflow_id=state["workflow_id"],
            initial_state={
                "status": WorkflowStatus.RUNNING,
                "context": state["context"],
                "metadata": {
                    "region_ids": state["region_ids"],
                    "agent_count": len(state["agent_manifests"]),
                },
            },
        )

        state["state_id"] = state_id
        state["status"] = WorkflowStatus.RUNNING
        state["messages"].append(f"State created: id={state_id}")

        self._state_manager.persist_trace(
            state_id,
            step="init_state",
            action="workflow_started",
            result={"workflow_id": state["workflow_id"]},
        )

        return state

    def _node_execute_agents(self, state: WorkflowGraphState) -> WorkflowGraphState:
        """Node: Load and execute each agent.

        For each agent manifest:
        1. Load agent via AgentRuntime
        2. Execute with context and limits
        3. Collect output

        Args:
            state: Current workflow state.

        Returns:
            Updated state with agent_outputs populated.
        """
        logger.info(
            f"Workflow {state['workflow_id']}: executing "
            f"{len(state['agent_manifests'])} agent(s)"
        )

        outputs: list[dict] = []
        agent_ids: list[str] = []

        for manifest_dict in state["agent_manifests"]:
            agent_name = manifest_dict.get("name", "unknown")
            logger.info(f"  Executing agent: {agent_name}")

            try:
                # Build limits from manifest
                limits_dict = manifest_dict.get("limits", {})
                limits = ExecutionLimits(
                    max_steps=limits_dict.get("max_steps", 10),
                    max_tokens=limits_dict.get("max_tokens", 4096),
                    timeout_seconds=limits_dict.get("timeout_seconds", 30),
                )

                # Execute agent (runtime handles loading via manifest)
                output = self._agent_runtime.execute(
                    agent=self._load_agent_from_manifest(manifest_dict),
                    context=state["context"],
                    limits=limits,
                )

                outputs.append(output)
                agent_ids.append(agent_name)

                # Persist trace
                self._state_manager.persist_trace(
                    state["state_id"],
                    step=f"execute_{agent_name}",
                    action="agent_complete",
                    result={
                        "agent_id": agent_name,
                        "output_summary": str(output)[:500],
                    },
                )

            except Exception as e:
                logger.error(f"  Agent {agent_name} failed: {e}")
                outputs.append(
                    {
                        "conclusion": f"Agent {agent_name} failed: {e}",
                        "confidence": 0.0,
                        "error": str(e),
                    }
                )
                agent_ids.append(agent_name)

                self._state_manager.persist_trace(
                    state["state_id"],
                    step=f"execute_{agent_name}",
                    action="agent_failed",
                    result={
                        "agent_id": agent_name,
                        "error": str(e),
                    },
                )

        state["agent_outputs"] = outputs
        state["messages"].append(
            f"Executed {len(outputs)} agent(s)"
        )
        return state

    def _node_consolidate(self, state: WorkflowGraphState) -> WorkflowGraphState:
        """Node: Consolidate multi-agent outputs into unified response.

        Args:
            state: Current workflow state.

        Returns:
            Updated state with consolidated_response populated.
        """
        logger.info(f"Workflow {state['workflow_id']}: consolidating responses")

        # Extract agent IDs from manifests
        agent_ids = [
            m.get("name", f"agent_{i}")
            for i, m in enumerate(state["agent_manifests"])
        ]

        consolidated = self._consolidator.consolidate(
            agent_outputs=state["agent_outputs"],
            agent_ids=agent_ids,
        )

        state["consolidated_response"] = consolidated
        state["messages"].append(
            f"Consolidated: confidence={consolidated.get('confidence', 0):.3f}"
        )
        return state

    def _node_finalize(self, state: WorkflowGraphState) -> WorkflowGraphState:
        """Node: Finalize workflow state.

        Updates the workflow state to completed and persists the
        final trace.

        Args:
            state: Current workflow state.

        Returns:
            Finalized state.
        """
        logger.info(f"Workflow {state['workflow_id']}: finalizing")

        has_errors = any(
            "error" in o for o in state["agent_outputs"]
        )

        final_status = (
            WorkflowStatus.FAILED if has_errors else WorkflowStatus.COMPLETED
        )

        state["status"] = final_status

        # Update state in DB
        self._state_manager.update_state(
            state["state_id"],
            {"status": final_status},
        )

        # Persist final trace
        self._state_manager.persist_trace(
            state["state_id"],
            step="finalize",
            action=f"workflow_{final_status}",
            result={
                "consolidated_response": state["consolidated_response"],
                "agent_count": len(state["agent_outputs"]),
            },
        )

        state["messages"].append(f"Workflow finalized: {final_status}")
        return state

    # ============================================================
    # Helpers
    # ============================================================

    def _load_agent_from_manifest(self, manifest_dict: dict) -> Any:
        """Load an agent from its manifest dict.

        For Slice 2, the runtime loads agents from the agents directory.
        This helper bridges the manifest dict to the runtime's load_agent.

        Args:
            manifest_dict: Agent manifest as a dict.

        Returns:
            Instantiated agent object.
        """
        from pathlib import Path

        agent_name = manifest_dict.get("name", "unknown")
        agents_dir = Path("src/ai/agents") / agent_name
        manifest_path = agents_dir / "manifest.yaml"

        if manifest_path.exists():
            return self._agent_runtime.load_agent(manifest_path)

        # Fallback: for manifests not backed by a file (e.g. dynamic),
        # return a minimal callable that produces a placeholder output.
        logger.warning(
            f"Manifest file not found for {agent_name} — using placeholder"
        )
        return _PlaceholderAgent(agent_name)

    @staticmethod
    def _manifest_to_dict(manifest: AgentManifest) -> dict:
        """Convert an AgentManifest dataclass to a dict for graph state.

        Args:
            manifest: AgentManifest dataclass.

        Returns:
            Dict representation suitable for LangGraph state.
        """
        result: dict[str, Any] = {
            "name": manifest.name,
            "version": manifest.version,
            "entry_point": manifest.entry_point,
            "description": manifest.description,
            "tools": manifest.tools,
            "output_schema": manifest.output_schema,
            "agent_type": manifest.agent_type,
        }
        if manifest.limits:
            result["limits"] = {
                "max_steps": manifest.limits.max_steps,
                "max_tokens": manifest.limits.max_tokens,
                "timeout_seconds": manifest.limits.timeout_seconds,
            }
        return result


class _PlaceholderAgent:
    """Fallback agent when manifest file is not found.

    Produces a minimal output so the workflow can continue.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def execute(self, context: dict, **kwargs: Any) -> dict:
        """Execute the placeholder agent.

        Args:
            context: Structured context.
            **kwargs: Additional parameters.

        Returns:
            Placeholder output dict.
        """
        return {
            "conclusion": f"Placeholder agent '{self.name}' — no manifest file found.",
            "confidence": 0.0,
            "error": "Manifest file not found",
        }
