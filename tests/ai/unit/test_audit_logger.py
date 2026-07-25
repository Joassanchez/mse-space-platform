"""Unit tests for AIAuditLogger.

Tests:
- All log methods produce correct entity_type and action values
- Non-fatal behavior: audit failures don't raise exceptions
- Metadata includes workflow_id, agent_id, model, token_usage, duration_ms
- Input truncation at 500 characters
- No-repo mode (logging only, no DB writes)
"""

from unittest.mock import MagicMock, patch

import pytest

from src.ai.infrastructure.observability.audit_logger import AIAuditLogger


@pytest.fixture
def mock_audit_repo():
    """Create a mock audit repository."""
    repo = MagicMock()
    repo.log_event.return_value = 42
    return repo


@pytest.fixture
def logger(mock_audit_repo):
    """Create AIAuditLogger with mock repo."""
    return AIAuditLogger(audit_repo=mock_audit_repo)


@pytest.fixture
def logger_no_repo():
    """Create AIAuditLogger without repo (logging only)."""
    return AIAuditLogger(audit_repo=None)


class TestAIAuditLoggerWorkflowEvents:
    """Test workflow lifecycle audit events."""

    def test_log_workflow_start(self, logger, mock_audit_repo):
        """Workflow start logs correct entity_type and action."""
        result = logger.log_workflow_start("wf-001", workflow_type="analyze_region")

        assert result == 42
        call_args = mock_audit_repo.log_event.call_args
        log_entry = call_args[0][0]
        assert log_entry.entity_type == "ai_workflow"
        assert log_entry.action == "workflow_start"
        assert "wf-001" in log_entry.message
        assert log_entry.metadata["workflow_id"] == "wf-001"

    def test_log_workflow_complete(self, logger, mock_audit_repo):
        """Workflow complete includes aggregate metrics."""
        result = logger.log_workflow_complete(
            "wf-001",
            total_duration_ms=1500.0,
            step_count=5,
            total_tokens=2048,
        )

        assert result == 42
        call_args = mock_audit_repo.log_event.call_args
        log_entry = call_args[0][0]
        assert log_entry.action == "workflow_complete"
        assert log_entry.metadata["total_duration_ms"] == 1500.0
        assert log_entry.metadata["step_count"] == 5
        assert log_entry.metadata["total_tokens"] == 2048

    def test_log_workflow_failed(self, logger, mock_audit_repo):
        """Workflow failure includes error message."""
        result = logger.log_workflow_failed("wf-001", error="Connection timeout")

        assert result == 42
        call_args = mock_audit_repo.log_event.call_args
        log_entry = call_args[0][0]
        assert log_entry.action == "workflow_failed"
        assert log_entry.metadata["error"] == "Connection timeout"


class TestAIAuditLoggerAgentEvents:
    """Test agent execution audit events."""

    def test_log_agent_start(self, logger, mock_audit_repo):
        """Agent start logs correct entity_type and actor_type."""
        result = logger.log_agent_start("wf-001", "reference-agent")

        assert result == 42
        call_args = mock_audit_repo.log_event.call_args
        log_entry = call_args[0][0]
        assert log_entry.entity_type == "ai_agent"
        assert log_entry.action == "agent_start"
        assert log_entry.actor_type == "agent"
        assert log_entry.actor_id == "reference-agent"
        assert log_entry.metadata["workflow_id"] == "wf-001"
        assert log_entry.metadata["agent_id"] == "reference-agent"

    def test_log_agent_complete_with_llm_metadata(self, logger, mock_audit_repo):
        """Agent complete includes model, token_usage, and duration_ms."""
        result = logger.log_agent_complete(
            "wf-001",
            "reference-agent",
            model="gpt-4o-mini",
            token_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            duration_ms=250.0,
            output_preview="Agent concluded that...",
        )

        call_args = mock_audit_repo.log_event.call_args
        log_entry = call_args[0][0]
        assert log_entry.action == "agent_complete"
        assert log_entry.metadata["model"] == "gpt-4o-mini"
        assert log_entry.metadata["token_usage"]["total_tokens"] == 150
        assert log_entry.metadata["duration_ms"] == 250.0

    def test_log_agent_failed(self, logger, mock_audit_repo):
        """Agent failure includes error and duration."""
        result = logger.log_agent_failed(
            "wf-001", "reference-agent", error="Timeout", duration_ms=30000.0
        )

        call_args = mock_audit_repo.log_event.call_args
        log_entry = call_args[0][0]
        assert log_entry.action == "agent_failed"
        assert log_entry.metadata["error"] == "Timeout"
        assert log_entry.metadata["duration_ms"] == 30000.0


class TestAIAuditLoggerToolCallEvents:
    """Test tool call audit events."""

    def test_log_tool_call_start(self, logger, mock_audit_repo):
        """Tool call start logs correct entity_type."""
        result = logger.log_tool_call_start("wf-001", "reference-agent", "geospatial_query")

        call_args = mock_audit_repo.log_event.call_args
        log_entry = call_args[0][0]
        assert log_entry.entity_type == "ai_tool_call"
        assert log_entry.action == "tool_call_start"
        assert log_entry.metadata["tool_name"] == "geospatial_query"

    def test_log_tool_call_complete(self, logger, mock_audit_repo):
        """Tool call complete includes duration."""
        result = logger.log_tool_call_complete(
            "wf-001", "reference-agent", "geospatial_query", duration_ms=50.0
        )

        call_args = mock_audit_repo.log_event.call_args
        log_entry = call_args[0][0]
        assert log_entry.action == "tool_call_complete"
        assert log_entry.metadata["duration_ms"] == 50.0

    def test_log_tool_call_failed(self, logger, mock_audit_repo):
        """Tool call failure includes error."""
        result = logger.log_tool_call_failed(
            "wf-001", "reference-agent", "geospatial_query", error="DB unavailable"
        )

        call_args = mock_audit_repo.log_event.call_args
        log_entry = call_args[0][0]
        assert log_entry.action == "tool_call_failed"
        assert log_entry.metadata["error"] == "DB unavailable"


class TestAIAuditLoggerNonFatal:
    """Test non-fatal audit behavior."""

    def test_repo_failure_does_not_raise(self, logger):
        """Audit failure does NOT raise an exception."""
        logger._audit_repo.log_event.side_effect = Exception("DB connection lost")

        # Should NOT raise
        result = logger.log_workflow_start("wf-001")

        assert result is None  # Returns None on failure

    def test_no_repo_mode_logs_only(self, logger_no_repo, caplog):
        """Without repo, events are logged but not persisted."""
        with caplog.at_level("DEBUG"):
            result = logger_no_repo.log_workflow_start("wf-001")

        assert result is None
        assert "Audit event (no repo)" in caplog.text

    def test_generic_log_event(self, logger, mock_audit_repo):
        """Generic log_event method works for custom events."""
        result = logger.log_event(
            entity_type="ai_workflow",
            action="workflow_step_complete",
            message="Step completed",
            metadata={"step": "build_context"},
        )

        assert result == 42
        call_args = mock_audit_repo.log_event.call_args
        log_entry = call_args[0][0]
        assert log_entry.entity_type == "ai_workflow"
        assert log_entry.action == "workflow_step_complete"


class TestAIAuditLoggerTruncation:
    """Test input/output truncation."""

    def test_truncate_short_string(self, logger):
        """Short strings are not truncated."""
        result = logger._truncate("short text")
        assert result == "short text"

    def test_truncate_long_string(self, logger):
        """Long strings are truncated to 500 chars with ellipsis."""
        long_text = "x" * 600
        result = logger._truncate(long_text)

        assert len(result) == 500
        assert result.endswith("...")

    def test_truncate_none(self, logger):
        """None returns None."""
        assert logger._truncate(None) is None

    def test_truncate_custom_max_length(self, logger):
        """Custom max_length is respected."""
        result = logger._truncate("hello world", max_length=8)
        assert result == "hello..."
