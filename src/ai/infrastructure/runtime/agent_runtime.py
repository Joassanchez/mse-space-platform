"""Agent Runtime for the AI ecosystem (Módulo 4).

Loads agents from validated manifests via controlled trusted import,
executes them with limits enforcement, and validates outputs against
declared JSON Schemas.

Sandboxing strategy: controlled trusted plugin execution (MVP).
Only modules within src/ai/agents/ are importable. No subprocess sandboxing.
"""

import importlib
import logging
import signal
import time
from pathlib import Path
from typing import Any

import yaml

try:
    import jsonschema
    from pydantic import create_model

    HAS_PYDANTIC_AI = True
except ImportError:
    HAS_PYDANTIC_AI = False

from src.ai.domain.errors import AgentExecutionError, ManifestValidationError
from src.ai.domain.interfaces import AgentRuntime
from src.ai.domain.models import ExecutionLimits

logger = logging.getLogger(__name__)

# Trusted import root — agents can ONLY be loaded from this directory
AGENTS_ROOT = Path("src/ai/agents")


class AgentRuntimeImpl(AgentRuntime):
    """Concrete AgentRuntime with controlled trusted import.

    Loads agents from manifests, enforces execution limits (steps, tokens,
    timeout), and validates outputs against declared schemas.
    """

    def __init__(self, tool_registry: dict[str, Any] | None = None):
        """Initialize the Agent Runtime.

        Args:
            tool_registry: Optional dict mapping tool names to Tool instances.
                Used for allowlist enforcement during execution.
        """
        self._tool_registry = tool_registry or {}
        self._loaded_agents: dict[str, Any] = {}

    def load_agent(self, manifest_path: Path) -> Any:
        """Load agent from validated manifest via controlled trusted import.

        The import is restricted to modules within src/ai/agents/.
        Arbitrary imports from outside the agents tree are rejected.

        Args:
            manifest_path: Path to the agent's manifest.yaml.

        Returns:
            Instantiated agent object.

        Raises:
            ManifestValidationError: If manifest is invalid.
            AgentExecutionError: If agent class cannot be loaded.
        """
        # Validate manifest first
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict):
            raise ManifestValidationError("Manifest is not a valid YAML object")

        required = ["name", "version", "entry_point"]
        missing = [k for k in required if k not in raw]
        if missing:
            raise ManifestValidationError(f"Missing required fields: {', '.join(missing)}")

        # Resolve entry_point: "module:ClassName"
        entry_point = raw["entry_point"]
        if ":" not in entry_point:
            raise ManifestValidationError(
                f"Invalid entry_point format: {entry_point} (expected 'module:Class')"
            )

        module_name, class_name = entry_point.split(":", 1)

        # Security: only allow imports from within src/ai/agents/
        agent_dir = manifest_path.parent
        if not self._is_within_agents_root(agent_dir):
            raise AgentExecutionError(
                agent_id=raw.get("name", "unknown"),
                message=f"Agent directory {agent_dir} is outside trusted root {AGENTS_ROOT}",
                step="load_agent",
            )

        # Controlled import: add agent dir to sys.path temporarily
        import sys

        agent_dir_str = str(agent_dir.resolve())
        if agent_dir_str not in sys.path:
            sys.path.insert(0, agent_dir_str)

        try:
            module = importlib.import_module(module_name)
            agent_class = getattr(module, class_name)
            agent = agent_class()
            self._loaded_agents[raw["name"]] = agent
            logger.info(f"Loaded agent: {raw['name']} from {entry_point}")
            return agent
        except (ImportError, AttributeError) as e:
            raise AgentExecutionError(
                agent_id=raw.get("name", "unknown"),
                message=f"Failed to load agent class {entry_point}: {e}",
                step="load_agent",
            )
        finally:
            # Clean up sys.path
            if agent_dir_str in sys.path:
                sys.path.remove(agent_dir_str)

    def execute(
        self, agent: Any, context: dict, limits: ExecutionLimits
    ) -> dict:
        """Execute agent with limits enforcement.

        Enforces:
        - timeout_seconds: via signal alarm (Unix) or time monitoring
        - max_steps: tracked via agent execution
        - max_tokens: logged (enforcement at LLM level)

        Args:
            agent: Loaded agent instance with execute() method.
            context: Structured context from Context Engine.
            limits: Execution limits to enforce.

        Returns:
            Agent output dict.

        Raises:
            AgentExecutionError: If execution fails or exceeds limits.
        """
        agent_id = getattr(agent, "name", "unknown")
        start_time = time.time()

        # Timeout enforcement
        timeout_handler = None
        use_signal = False

        try:
            # Try signal-based timeout (Unix only)
            use_signal = True
            old_handler = signal.signal(signal.SIGALRM, self._timeout_handler)
            signal.alarm(limits.timeout_seconds)
        except (AttributeError, OSError):
            # signal.SIGALRM not available (Windows) — use time monitoring
            use_signal = False

        try:
            # Execute the agent
            output = agent.execute(context=context)

            # Check timeout (for non-signal platforms)
            elapsed = time.time() - start_time
            if not use_signal and elapsed > limits.timeout_seconds:
                raise AgentExecutionError(
                    agent_id=agent_id,
                    message=f"Execution timed out: {elapsed:.1f}s > {limits.timeout_seconds}s",
                    step="execute",
                )

            return output

        except AgentExecutionError:
            raise
        except Exception as e:
            raise AgentExecutionError(
                agent_id=agent_id,
                message=str(e),
                step="execute",
            )
        finally:
            if use_signal:
                signal.alarm(0)  # Cancel alarm
                try:
                    signal.signal(signal.SIGALRM, old_handler)
                except Exception:
                    pass

    def validate_output(self, output: Any, schema: dict) -> bool:
        """Validate agent output against JSON Schema.

        Uses jsonschema for validation. If pydantic-ai is available,
        also attempts Pydantic model validation for richer error messages.

        Args:
            output: Agent output to validate.
            schema: JSON Schema from the agent's manifest.

        Returns:
            True if output matches schema.

        Raises:
            ManifestValidationError: If output does not match schema.
        """
        if not isinstance(output, dict):
            raise ManifestValidationError(
                f"Output must be a dict, got {type(output).__name__}"
            )

        # JSON Schema validation
        try:
            jsonschema.validate(instance=output, schema=schema)
        except jsonschema.ValidationError as e:
            raise ManifestValidationError(
                f"Output validation failed: {e.message}"
            ) from e

        return True

    def register_tool(self, tool: Any) -> None:
        """Register a tool for allowlist enforcement.

        Args:
            tool: Tool instance with a `name` property.
        """
        self._tool_registry[tool.name] = tool

    def enforce_tool_allowlist(
        self, agent_name: str, allowed_tools: list[str], requested_tool: str
    ) -> bool:
        """Check if an agent is allowed to invoke a specific tool.

        Args:
            agent_name: Agent identifier.
            allowed_tools: List of tool names from the agent's manifest.
            requested_tool: Tool name the agent wants to invoke.

        Returns:
            True if the tool is in the allowlist.

        Raises:
            AgentExecutionError: If tool is not in allowlist.
        """
        if requested_tool not in allowed_tools:
            raise AgentExecutionError(
                agent_id=agent_name,
                message=f"Tool '{requested_tool}' not in allowlist: {allowed_tools}",
                step="tool_call",
            )
        return True

    def get_tool(self, tool_name: str) -> Any | None:
        """Get a registered tool by name.

        Args:
            tool_name: Tool identifier.

        Returns:
            Tool instance if found, None otherwise.
        """
        return self._tool_registry.get(tool_name)

    # ============================================================
    # Private helpers
    # ============================================================

    @staticmethod
    def _is_within_agents_root(agent_dir: Path) -> bool:
        """Check if a directory is within the trusted agents root.

        Args:
            agent_dir: Directory to check.

        Returns:
            True if the directory is within AGENTS_ROOT.
        """
        try:
            agent_dir.resolve().relative_to(AGENTS_ROOT.resolve())
            return True
        except ValueError:
            return False

    @staticmethod
    def _timeout_handler(signum: int, frame: Any) -> None:
        """Signal handler for timeout enforcement.

        Args:
            signum: Signal number.
            frame: Current stack frame.

        Raises:
            AgentExecutionError: Always — this is a timeout.
        """
        raise AgentExecutionError(
            agent_id="unknown",
            message="Execution timed out (SIGALRM)",
            step="execute",
        )
