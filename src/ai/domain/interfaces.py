"""Generic ports (interfaces) for the AI ecosystem (Módulo 4).

All interfaces are provider-agnostic. Concrete implementations
(LiteLLMProviderImpl, ContextEngineImpl, StateManagerImpl, etc.)
live in the infrastructure layer and implement these ports.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from src.ai.domain.models import (
    AgentManifest,
    ExecutionLimits,
    ExecutionTrace,
    LLMRequest,
    LLMResponse,
    ToolResult,
    WorkflowState,
)


class LLMProvider(ABC):
    """Provider-agnostic interface for LLM completions.

    Implemented by LiteLLMProviderImpl. Allows switching providers
    (OpenAI, Claude, Gemini, Azure) without code changes.
    """

    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse:
        """Execute an LLM completion.

        Args:
            request: LLMRequest with prompt, context, model, and parameters.

        Returns:
            LLMResponse with content, model, usage, and metadata.
        """
        pass

    @abstractmethod
    def set_provider(self, provider: str) -> None:
        """Switch the underlying provider.

        Args:
            provider: Provider identifier (e.g. "openai", "claude", "gemini").
        """
        pass


class ContextEngine(ABC):
    """Builds structured context from M3 geospatial outputs.

    Reads processed_geospatial_layers, regions, indicators, and risk_assessments
    via existing repositories (read-only). Produces normalized JSON payloads.
    """

    @abstractmethod
    def build_context(
        self,
        region_ids: list[int],
        indicator_codes: list[str] | None = None,
        max_age_hours: int | None = None,
    ) -> dict:
        """Build structured JSON context from M3 tables (read-only).

        Args:
            region_ids: List of region IDs to include in context.
            indicator_codes: Optional filter by indicator codes.
            max_age_hours: Optional staleness threshold. If latest data exceeds
                this age, stale_data warning is included.

        Returns:
            Structured dict with region metadata, layer summaries, indicators,
            risk assessments, and optional stale_data/truncated warnings.
        """
        pass

    @abstractmethod
    def build_enriched_context(
        self,
        region_ids: list[int],
        indicator_codes: list[str] | None = None,
        max_age_hours: int | None = None,
        include_weather: bool = True,
        include_socioeconomic: bool = True,
    ) -> dict:
        """Build enriched context with weather and socioeconomic data.

        Extends build_context() with optional weather snapshots and
        socioeconomic indicators (Módulo 6 — Data Connectors).

        Args:
            region_ids: List of region IDs to include in context.
            indicator_codes: Optional filter by indicator codes.
            max_age_hours: Optional staleness threshold.
            include_weather: If True, attach latest weather per region.
            include_socioeconomic: If True, attach ECO_* indicators.

        Returns:
            Enriched context dict with optional "weather" and
            "socioeconomic" keys.
        """
        pass

    @abstractmethod
    def summarize_context(self, context: dict, max_tokens: int) -> dict:
        """Summarize context to fit token window.

        Uses field selection and per-entity limits (not just truncation).
        Includes metadata about entity counts, date ranges, and truncation warnings.

        Args:
            context: Full context dict from build_context().
            max_tokens: Maximum token budget for the summarized output.

        Returns:
            Summarized context dict with truncated flag if data was reduced.
        """
        pass


class StateManager(ABC):
    """Persist and retrieve AI workflow states and execution traces.

    Uses separate PostgreSQL tables (ai_workflow_states, ai_execution_traces)
    with no FK constraints to M3 tables.
    """

    @abstractmethod
    def create_state(self, workflow_id: str, initial_state: dict) -> int:
        """Create initial workflow state.

        Args:
            workflow_id: Unique workflow identifier.
            initial_state: Initial state dict (status, context, metadata).

        Returns:
            Database-assigned state ID.
        """
        pass

    @abstractmethod
    def update_state(self, state_id: int, state: dict) -> None:
        """Update workflow state (not audit_logs — separate table).

        Args:
            state_id: The ai_workflow_states.id value.
            state: Updated state dict.
        """
        pass

    @abstractmethod
    def persist_trace(self, state_id: int, step: str, action: str, result: Any) -> int:
        """Persist an execution trace entry.

        Args:
            state_id: FK reference to ai_workflow_states.id (logical).
            step: Step identifier.
            action: Action performed.
            result: Step result (JSON-serializable).

        Returns:
            Database-assigned trace ID.
        """
        pass


class AgentRuntime(ABC):
    """Controlled execution environment for agent plugins.

    Loads agents from validated manifests, enforces execution limits,
    and validates outputs against declared schemas.
    """

    @abstractmethod
    def load_agent(self, manifest_path: Path) -> Any:
        """Load agent from validated manifest.

        Controlled trusted import: only modules within src/ai/agents/.

        Args:
            manifest_path: Path to the agent's manifest.yaml.

        Returns:
            Instantiated agent object.
        """
        pass

    @abstractmethod
    def execute(self, agent: Any, context: dict, limits: ExecutionLimits) -> dict:
        """Execute agent with limits enforcement.

        Args:
            agent: Loaded agent instance.
            context: Structured context from Context Engine.
            limits: Execution limits to enforce.

        Returns:
            Agent output dict.
        """
        pass

    @abstractmethod
    def validate_output(self, output: Any, schema: dict) -> bool:
        """Validate agent output against JSON Schema via PydanticAI.

        Args:
            output: Agent output to validate.
            schema: JSON Schema from the agent's manifest.

        Returns:
            True if output matches schema.
        """
        pass


class Tool(ABC):
    """Base interface for tools available to AI agents.

    Tools are read-only wrappers over existing M2/M3 services.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool identifier — must match manifest tool list."""
        pass

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool (wraps existing M2/M3 service).

        Args:
            **kwargs: Tool-specific parameters.

        Returns:
            ToolResult with success status and data/error.
        """
        pass


class PromptTemplate(ABC):
    """Interface for loading and rendering prompt templates.

    Templates are versioned files in data/prompts/, with optional
    production overrides stored in ai_prompt_metadata table.
    """

    @abstractmethod
    def load(self, template_name: str) -> str:
        """Load a prompt template by name.

        Args:
            template_name: Template identifier (e.g. "maestro", "region_analysis").

        Returns:
            Template text content.
        """
        pass

    @abstractmethod
    def render(self, template_name: str, variables: dict[str, Any]) -> str:
        """Render a template with variable injection.

        Logs MissingVariableWarning for undefined variables.

        Args:
            template_name: Template identifier.
            variables: Dict of variable names to values.

        Returns:
            Rendered prompt text.
        """
        pass
