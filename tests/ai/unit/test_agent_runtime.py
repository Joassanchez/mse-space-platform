"""Unit tests for Agent Runtime.

Tests:
- Controlled import: only from src/ai/agents/
- Execution limits: timeout enforcement
- Tool allowlist enforcement
- Output validation against JSON Schema
- Non-fatal behavior on import failures
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from src.ai.domain.errors import AgentExecutionError, ManifestValidationError
from src.ai.domain.models import ExecutionLimits
from src.ai.infrastructure.runtime.agent_runtime import AgentRuntimeImpl, AGENTS_ROOT


VALID_MANIFEST = {
    "name": "test-agent",
    "version": "1.0.0",
    "entry_point": "agent:TestAgent",
    "description": "A test agent",
    "tools": ["geospatial_query"],
    "output_schema": {
        "type": "object",
        "required": ["conclusion"],
        "properties": {"conclusion": {"type": "string"}},
    },
    "limits": {
        "max_steps": 10,
        "max_tokens": 4096,
        "timeout_seconds": 30,
    },
}


@pytest.fixture
def runtime():
    """Create AgentRuntimeImpl."""
    return AgentRuntimeImpl()


@pytest.fixture
def agent_dir_with_manifest():
    """Create a temporary agent directory with manifest and agent file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent_dir = Path(tmpdir)
        # Write manifest
        with open(agent_dir / "manifest.yaml", "w") as f:
            yaml.dump(VALID_MANIFEST, f)
        # Write agent file
        with open(agent_dir / "agent.py", "w") as f:
            f.write("""
class TestAgent:
    name = "test-agent"
    def execute(self, context, **kwargs):
        return {"conclusion": "Test output", "confidence": 0.5}
""")
        yield agent_dir


class TestAgentRuntimeLoadAgent:
    """Test agent loading."""

    def test_load_agent_missing_manifest_raises(self, runtime):
        """load_agent raises FileNotFoundError for missing manifest."""
        with pytest.raises(FileNotFoundError, match="Manifest not found"):
            runtime.load_agent(Path("/nonexistent/manifest.yaml"))

    def test_load_agent_invalid_entry_point_raises(self, runtime, tmp_path):
        """load_agent raises ManifestValidationError for bad entry_point."""
        manifest_path = tmp_path / "manifest.yaml"
        bad_manifest = {**VALID_MANIFEST, "entry_point": "no-colon"}
        with open(manifest_path, "w") as f:
            yaml.dump(bad_manifest, f)

        with pytest.raises(ManifestValidationError, match="entry_point"):
            runtime.load_agent(manifest_path)

    def test_load_agent_outside_agents_root_raises(self, runtime, tmp_path):
        """load_agent rejects agents outside trusted root."""
        manifest_path = tmp_path / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(VALID_MANIFEST, f)

        with pytest.raises(AgentExecutionError, match="outside trusted root"):
            runtime.load_agent(manifest_path)


class TestAgentRuntimeExecute:
    """Test agent execution with limits."""

    def test_execute_returns_agent_output(self, runtime):
        """execute returns the agent's output dict."""
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.execute.return_value = {
            "conclusion": "Test result",
            "confidence": 0.9,
        }

        limits = ExecutionLimits(timeout_seconds=30)
        result = runtime.execute(mock_agent, context={}, limits=limits)

        assert result["conclusion"] == "Test result"
        assert result["confidence"] == 0.9

    def test_execute_propagates_agent_execution_error(self, runtime):
        """AgentExecutionError from agent is propagated."""
        mock_agent = MagicMock()
        mock_agent.name = "failing-agent"
        mock_agent.execute.side_effect = RuntimeError("Agent crashed")

        limits = ExecutionLimits(timeout_seconds=30)

        with pytest.raises(AgentExecutionError, match="Agent crashed"):
            runtime.execute(mock_agent, context={}, limits=limits)

    def test_execute_windows_fallback(self, runtime):
        """execute works on Windows (signal fallback)."""
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.execute.return_value = {"conclusion": "OK", "confidence": 0.5}

        # Simulate Windows: signal.SIGALRM not available
        with patch("signal.signal", side_effect=AttributeError):
            limits = ExecutionLimits(timeout_seconds=30)
            result = runtime.execute(mock_agent, context={}, limits=limits)

        assert result["conclusion"] == "OK"


class TestAgentRuntimeToolAllowlist:
    """Test tool allowlist enforcement."""

    def test_enforce_tool_allowlist_allowed(self, runtime):
        """Allowed tool passes validation."""
        result = runtime.enforce_tool_allowlist(
            "test-agent", ["geospatial_query", "indicator_lookup"], "geospatial_query"
        )
        assert result is True

    def test_enforce_tool_allowlist_denied(self, runtime):
        """Disallowed tool raises AgentExecutionError."""
        with pytest.raises(AgentExecutionError, match="not in allowlist"):
            runtime.enforce_tool_allowlist(
                "test-agent", ["geospatial_query"], "summarization"
            )


class TestAgentRuntimeOutputValidation:
    """Test output validation against JSON Schema."""

    def test_validate_output_valid(self, runtime):
        """Valid output passes validation."""
        schema = {
            "type": "object",
            "required": ["conclusion"],
            "properties": {"conclusion": {"type": "string"}},
        }
        result = runtime.validate_output({"conclusion": "Test"}, schema)
        assert result is True

    def test_validate_output_non_dict_raises(self, runtime):
        """Non-dict output raises ManifestValidationError."""
        schema = {"type": "object"}
        with pytest.raises(ManifestValidationError, match="must be a dict"):
            runtime.validate_output("not a dict", schema)

    def test_validate_output_missing_required_raises(self, runtime):
        """Missing required field raises ManifestValidationError."""
        schema = {
            "type": "object",
            "required": ["conclusion", "confidence"],
            "properties": {
                "conclusion": {"type": "string"},
                "confidence": {"type": "number"},
            },
        }
        with pytest.raises(ManifestValidationError, match="validation failed"):
            runtime.validate_output({"conclusion": "Test"}, schema)


class TestAgentRuntimeToolRegistry:
    """Test tool registration and retrieval."""

    def test_register_and_get_tool(self, runtime):
        """register_tool stores tool, get_tool retrieves it."""
        mock_tool = MagicMock()
        mock_tool.name = "test-tool"

        runtime.register_tool(mock_tool)
        found = runtime.get_tool("test-tool")

        assert found is mock_tool

    def test_get_tool_not_found(self, runtime):
        """get_tool returns None for unknown tool."""
        assert runtime.get_tool("nonexistent") is None


class TestAgentRuntimeSecurity:
    """Test security constraints."""

    def test_is_within_agents_root_true(self):
        """_is_within_agents_root returns True for paths inside root."""
        test_path = AGENTS_ROOT / "reference_agent"
        assert AgentRuntimeImpl._is_within_agents_root(test_path) is True

    def test_is_within_agents_root_false(self):
        """_is_within_agents_root returns False for paths outside root."""
        test_path = Path("/tmp/malicious-agent")
        assert AgentRuntimeImpl._is_within_agents_root(test_path) is False
