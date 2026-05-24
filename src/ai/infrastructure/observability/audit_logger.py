"""Audit logger for the AI ecosystem (Modulo 4).

Writes AI events to the existing audit_logs table with entity_type values:
- ai_workflow: workflow lifecycle events (start, complete, fail)
- ai_agent: agent execution events (start, complete, fail)
- ai_tool_call: tool invocation events (start, complete, fail)

All audit writes are NON-FATAL: failures are logged as warnings but
never interrupt agent execution or workflow completion.

Metadata JSONB payload includes:
- workflow_id: parent workflow identifier
- agent_id: agent that performed the action
- model: LLM model used (if applicable)
- token_usage: {prompt_tokens, completion_tokens, total_tokens}
- duration_ms: execution duration in milliseconds
- input_preview: truncated input for debugging (max 500 chars)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# AI-specific entity types for audit_logs
ENTITY_TYPES = {
    "workflow": "ai_workflow",
    "agent": "ai_agent",
    "tool_call": "ai_tool_call",
}

# AI-specific action values
ACTIONS = {
    "workflow_start": "workflow_start",
    "workflow_complete": "workflow_complete",
    "workflow_failed": "workflow_failed",
    "workflow_step_complete": "workflow_step_complete",
    "agent_start": "agent_start",
    "agent_complete": "agent_complete",
    "agent_failed": "agent_failed",
    "tool_call_start": "tool_call_start",
    "tool_call_complete": "tool_call_complete",
    "tool_call_failed": "tool_call_failed",
}

INPUT_PREVIEW_MAX_LENGTH = 500


class AIAuditLogger:
    """Writes AI events to the audit_logs table.

    All write operations are wrapped in try/except — audit failures
    are logged as warnings but never raise exceptions.

    The logger uses an optional AuditRepository for persistence.
    If no repository is provided, events are logged but not persisted.
    """

    def __init__(self, audit_repo: Optional[Any] = None) -> None:
        """Initialize the AI audit logger.

        Args:
            audit_repo: Optional AuditRepository instance for persistence.
                If None, events are only logged (not written to DB).
        """
        self._audit_repo = audit_repo

    def log_workflow_start(
        self,
        workflow_id: str,
        workflow_type: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[int]:
        """Log a workflow start event.

        Args:
            workflow_id: Unique workflow identifier.
            workflow_type: Optional workflow type for classification.
            metadata: Additional metadata to include.

        Returns:
            Audit log ID if successful, None if write failed.
        """
        meta = {
            "workflow_id": workflow_id,
            "workflow_type": workflow_type,
            **(metadata or {}),
        }
        return self._log_event(
            entity_type=ENTITY_TYPES["workflow"],
            action=ACTIONS["workflow_start"],
            actor_type="system",
            message=f"Workflow {workflow_id} started",
            metadata=meta,
        )

    def log_workflow_complete(
        self,
        workflow_id: str,
        total_duration_ms: Optional[float] = None,
        step_count: Optional[int] = None,
        total_tokens: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[int]:
        """Log a workflow completion event.

        Args:
            workflow_id: Unique workflow identifier.
            total_duration_ms: Total workflow duration.
            step_count: Number of steps executed.
            total_tokens: Total tokens consumed.
            metadata: Additional metadata.

        Returns:
            Audit log ID if successful, None if write failed.
        """
        meta = {
            "workflow_id": workflow_id,
            "total_duration_ms": total_duration_ms,
            "step_count": step_count,
            "total_tokens": total_tokens,
            **(metadata or {}),
        }
        return self._log_event(
            entity_type=ENTITY_TYPES["workflow"],
            action=ACTIONS["workflow_complete"],
            actor_type="system",
            message=f"Workflow {workflow_id} completed",
            metadata=meta,
        )

    def log_workflow_failed(
        self,
        workflow_id: str,
        error: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[int]:
        """Log a workflow failure event.

        Args:
            workflow_id: Unique workflow identifier.
            error: Error message describing the failure.
            metadata: Additional metadata.

        Returns:
            Audit log ID if successful, None if write failed.
        """
        meta = {
            "workflow_id": workflow_id,
            "error": error,
            **(metadata or {}),
        }
        return self._log_event(
            entity_type=ENTITY_TYPES["workflow"],
            action=ACTIONS["workflow_failed"],
            actor_type="system",
            message=f"Workflow {workflow_id} failed: {error}",
            metadata=meta,
        )

    def log_agent_start(
        self,
        workflow_id: str,
        agent_id: str,
        input_preview: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[int]:
        """Log an agent start event.

        Args:
            workflow_id: Parent workflow identifier.
            agent_id: Agent identifier.
            input_preview: Truncated input for debugging.
            metadata: Additional metadata.

        Returns:
            Audit log ID if successful, None if write failed.
        """
        meta = {
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "input_preview": self._truncate(input_preview),
            **(metadata or {}),
        }
        return self._log_event(
            entity_type=ENTITY_TYPES["agent"],
            action=ACTIONS["agent_start"],
            actor_type="agent",
            actor_id=agent_id,
            message=f"Agent {agent_id} started in workflow {workflow_id}",
            metadata=meta,
        )

    def log_agent_complete(
        self,
        workflow_id: str,
        agent_id: str,
        model: Optional[str] = None,
        token_usage: Optional[dict[str, int]] = None,
        duration_ms: Optional[float] = None,
        output_preview: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[int]:
        """Log an agent completion event.

        Args:
            workflow_id: Parent workflow identifier.
            agent_id: Agent identifier.
            model: LLM model used (if applicable).
            token_usage: Token usage statistics.
            duration_ms: Agent execution duration.
            output_preview: Truncated output for debugging.
            metadata: Additional metadata.

        Returns:
            Audit log ID if successful, None if write failed.
        """
        meta = {
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "model": model,
            "token_usage": token_usage,
            "duration_ms": duration_ms,
            "output_preview": self._truncate(output_preview),
            **(metadata or {}),
        }
        return self._log_event(
            entity_type=ENTITY_TYPES["agent"],
            action=ACTIONS["agent_complete"],
            actor_type="agent",
            actor_id=agent_id,
            message=f"Agent {agent_id} completed in workflow {workflow_id}",
            metadata=meta,
        )

    def log_agent_failed(
        self,
        workflow_id: str,
        agent_id: str,
        error: str,
        duration_ms: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[int]:
        """Log an agent failure event.

        Args:
            workflow_id: Parent workflow identifier.
            agent_id: Agent identifier.
            error: Error message.
            duration_ms: Duration before failure.
            metadata: Additional metadata.

        Returns:
            Audit log ID if successful, None if write failed.
        """
        meta = {
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "error": error,
            "duration_ms": duration_ms,
            **(metadata or {}),
        }
        return self._log_event(
            entity_type=ENTITY_TYPES["agent"],
            action=ACTIONS["agent_failed"],
            actor_type="agent",
            actor_id=agent_id,
            message=f"Agent {agent_id} failed in workflow {workflow_id}: {error}",
            metadata=meta,
        )

    def log_tool_call_start(
        self,
        workflow_id: str,
        agent_id: str,
        tool_name: str,
        input_preview: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[int]:
        """Log a tool call start event.

        Args:
            workflow_id: Parent workflow identifier.
            agent_id: Agent that invoked the tool.
            tool_name: Tool identifier.
            input_preview: Truncated input parameters.
            metadata: Additional metadata.

        Returns:
            Audit log ID if successful, None if write failed.
        """
        meta = {
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "tool_name": tool_name,
            "input_preview": self._truncate(input_preview),
            **(metadata or {}),
        }
        return self._log_event(
            entity_type=ENTITY_TYPES["tool_call"],
            action=ACTIONS["tool_call_start"],
            actor_type="agent",
            actor_id=agent_id,
            message=f"Tool {tool_name} called by {agent_id}",
            metadata=meta,
        )

    def log_tool_call_complete(
        self,
        workflow_id: str,
        agent_id: str,
        tool_name: str,
        duration_ms: Optional[float] = None,
        output_preview: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[int]:
        """Log a tool call completion event.

        Args:
            workflow_id: Parent workflow identifier.
            agent_id: Agent that invoked the tool.
            tool_name: Tool identifier.
            duration_ms: Tool execution duration.
            output_preview: Truncated output.
            metadata: Additional metadata.

        Returns:
            Audit log ID if successful, None if write failed.
        """
        meta = {
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "tool_name": tool_name,
            "duration_ms": duration_ms,
            "output_preview": self._truncate(output_preview),
            **(metadata or {}),
        }
        return self._log_event(
            entity_type=ENTITY_TYPES["tool_call"],
            action=ACTIONS["tool_call_complete"],
            actor_type="agent",
            actor_id=agent_id,
            message=f"Tool {tool_name} completed for {agent_id}",
            metadata=meta,
        )

    def log_tool_call_failed(
        self,
        workflow_id: str,
        agent_id: str,
        tool_name: str,
        error: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[int]:
        """Log a tool call failure event.

        Args:
            workflow_id: Parent workflow identifier.
            agent_id: Agent that invoked the tool.
            tool_name: Tool identifier.
            error: Error message.
            metadata: Additional metadata.

        Returns:
            Audit log ID if successful, None if write failed.
        """
        meta = {
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "tool_name": tool_name,
            "error": error,
            **(metadata or {}),
        }
        return self._log_event(
            entity_type=ENTITY_TYPES["tool_call"],
            action=ACTIONS["tool_call_failed"],
            actor_type="agent",
            actor_id=agent_id,
            message=f"Tool {tool_name} failed for {agent_id}: {error}",
            metadata=meta,
        )

    def log_event(
        self,
        entity_type: str,
        action: str,
        message: str,
        actor_type: str = "system",
        actor_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[int]:
        """Log a generic AI audit event.

        This is the low-level method — all other log_* methods delegate here.

        Args:
            entity_type: Entity type (ai_workflow, ai_agent, ai_tool_call).
            action: Action performed.
            message: Human-readable description.
            actor_type: Actor type (system, user, agent).
            actor_id: Actor identifier.
            entity_id: Entity identifier.
            metadata: Additional JSONB metadata.

        Returns:
            Audit log ID if successful, None if write failed.
        """
        return self._log_event(
            entity_type=entity_type,
            action=action,
            message=message,
            actor_type=actor_type,
            actor_id=actor_id,
            entity_id=entity_id,
            metadata=metadata,
        )

    # ============================================================
    # Private helpers
    # ============================================================

    def _log_event(
        self,
        entity_type: str,
        action: str,
        message: str,
        actor_type: str = "system",
        actor_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[int]:
        """Internal log method with non-fatal error handling.

        Args:
            entity_type: Entity type for audit_logs.
            action: Action performed.
            message: Human-readable description.
            actor_type: Actor type.
            actor_id: Actor identifier.
            entity_id: Entity identifier.
            metadata: Additional metadata.

        Returns:
            Audit log ID if successful, None if write failed.
        """
        try:
            if self._audit_repo is None:
                logger.debug(
                    f"Audit event (no repo): {entity_type}/{action} — {message}"
                )
                return None

            # Import here to avoid circular dependency
            from src.geospatial.domain.models import AuditLog

            log_entry = AuditLog(
                entity_type=entity_type,
                action=action,
                actor_type=actor_type,
                actor_id=actor_id,
                entity_id=entity_id,
                message=message,
                metadata=metadata or {},
                created_at=datetime.now(timezone.utc).isoformat(),
            )

            audit_id = self._audit_repo.log_event(log_entry)
            logger.debug(f"Audit event logged: id={audit_id}, {entity_type}/{action}")
            return audit_id

        except Exception as e:
            # NON-FATAL: Log the failure but never raise
            logger.warning(
                f"Audit write failed (non-fatal) — {entity_type}/{action}: {e}"
            )
            return None

    @staticmethod
    def _truncate(value: Optional[str], max_length: int = INPUT_PREVIEW_MAX_LENGTH) -> Optional[str]:
        """Truncate a string to max_length characters.

        Args:
            value: String to truncate.
            max_length: Maximum length (default: 500).

        Returns:
            Truncated string with ellipsis if needed, or None.
        """
        if value is None:
            return None
        if len(value) <= max_length:
            return value
        return value[: max_length - 3] + "..."
