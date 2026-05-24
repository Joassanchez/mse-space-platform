"""Domain models for the AI ecosystem (Módulo 4).

Dataclasses represent the core entities flowing through the AI pipeline:
workflow states, execution traces, agent manifests, tool results, and LLM I/O.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class ExecutionLimits:
    """Configurable limits for agent execution."""

    max_steps: int = 10
    max_tokens: int = 4096
    timeout_seconds: int = 30


@dataclass
class WorkflowState:
    """Persistence model for an AI workflow execution state.

    Attributes:
        workflow_id: Unique identifier for the workflow run.
        status: Current lifecycle state (pending, running, completed, failed).
        context: Structured context payload built by the Context Engine.
        metadata: Additional JSONB metadata (region_ids, agent_ids, etc.).
        id: Database-assigned ID (None before insert).
        created_at: ISO timestamp of creation.
        updated_at: ISO timestamp of last update.
    """

    workflow_id: str
    status: str = "pending"
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class ExecutionTrace:
    """Persistence model for a single step in an AI workflow execution.

    Attributes:
        state_id: FK reference to ai_workflow_states.id (logical, no FK constraint).
        step: Step identifier (e.g. "build_context", "execute_agent").
        action: Action performed in this step.
        result: Output/result of the step (JSON-serializable).
        error: Error message if the step failed.
        id: Database-assigned ID (None before insert).
        created_at: ISO timestamp of creation.
    """

    state_id: int
    step: str
    action: str
    result: Optional[Any] = None
    error: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class AgentManifest:
    """Declarative manifest for an AI agent plugin.

    Loaded from YAML files in src/ai/agents/*/manifest.yaml.
    Validated against JSON Schema before agent registration.

    Attributes:
        name: Agent identifier (e.g. "reference-agent").
        version: Semantic version string.
        entry_point: Module:class reference (e.g. "agent:ReferenceAgent").
        description: Human-readable description.
        tools: List of tool names this agent is allowed to use.
        limits: Execution limits (max_steps, max_tokens, timeout).
        output_schema: JSON Schema for validating agent output.
        agent_type: Type identifier (e.g. "reference").
    """

    name: str
    version: str
    entry_point: str
    description: str
    tools: list[str] = field(default_factory=list)
    limits: Optional[ExecutionLimits] = None
    output_schema: dict[str, Any] = field(default_factory=dict)
    agent_type: str = "reference"


@dataclass
class ToolResult:
    """Result of a tool execution.

    Attributes:
        tool_name: Identifier of the tool that was executed.
        success: Whether the execution succeeded.
        data: Result data (JSON-serializable).
        error: Error message if execution failed.
    """

    tool_name: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class LLMRequest:
    """Request parameters for an LLM completion.

    Attributes:
        prompt: The user/system prompt text.
        context: Optional structured context to include.
        model: Model identifier (e.g. "gpt-4", "claude-3-sonnet").
        max_tokens: Maximum tokens in the response.
        temperature: Sampling temperature (0.0-1.0).
    """

    prompt: str
    context: Optional[str] = None
    model: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.7


@dataclass
class LLMResponse:
    """Response from an LLM completion.

    Attributes:
        content: Generated text content.
        model: Model that generated the response.
        usage: Token usage statistics (prompt_tokens, completion_tokens, total_tokens).
        latency_ms: Time taken for the request in milliseconds.
        cost_usd: Estimated cost (if tracking enabled).
        metadata: Additional response metadata.
    """

    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    cost_usd: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)
