"""Custom exceptions for the AI ecosystem (Módulo 4)."""


class ManifestValidationError(Exception):
    """Raised when an agent manifest fails JSON Schema validation."""

    pass


class AgentExecutionError(Exception):
    """Raised when an agent execution fails."""

    def __init__(self, agent_id: str, message: str, step: str | None = None):
        self.agent_id = agent_id
        self.step = step
        super().__init__(f"Agent '{agent_id}' failed at step '{step}': {message}")


class ToolExecutionError(Exception):
    """Raised when a tool execution fails."""

    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' failed: {message}")


class ContextError(Exception):
    """Raised when context building or summarization fails."""

    pass
