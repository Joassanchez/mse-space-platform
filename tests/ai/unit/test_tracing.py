"""Unit tests for AITracer (OpenTelemetry spans).

Tests:
- Workflow span creation with correct attributes
- Step span creation
- Tool span creation
- LLM span creation
- Non-fatal behavior: tracing failures don't raise
- Error recording on spans
- No-op span fallback
"""

from unittest.mock import MagicMock, patch

import pytest

from src.ai.infrastructure.observability.tracing import AITracer, _NoOpSpan


@pytest.fixture
def mock_span():
    """Create a mock OpenTelemetry span."""
    span = MagicMock()
    span.__enter__ = MagicMock(return_value=span)
    span.__exit__ = MagicMock(return_value=False)
    return span


@pytest.fixture
def mock_tracer(mock_span):
    """Create a mock OpenTelemetry tracer."""
    tracer = MagicMock()
    tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
    tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
    return tracer


@pytest.fixture
def ai_tracer(mock_tracer):
    """Create AITracer with mocked OpenTelemetry."""
    with patch("src.ai.infrastructure.observability.tracing.trace") as mock_trace:
        mock_trace.get_tracer.return_value = mock_tracer
        return AITracer(service_name="test-ai")


class TestAITracerWorkflowSpan:
    """Test workflow span creation."""

    def test_workflow_span_correct_attributes(self, ai_tracer, mock_tracer, mock_span):
        """Workflow span includes workflow.id and workflow.type."""
        with ai_tracer.workflow_span("wf-001", "analyze_region") as span:
            pass

        mock_tracer.start_as_current_span.assert_called_once()
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[0][0] == "workflow.analyze_region"
        assert call_args[1]["attributes"]["workflow.id"] == "wf-001"
        assert call_args[1]["attributes"]["workflow.type"] == "analyze_region"

    def test_workflow_span_with_metadata(self, ai_tracer, mock_tracer):
        """Workflow span includes custom metadata."""
        with ai_tracer.workflow_span("wf-001", "test", metadata={"region_ids": [1, 2]}):
            pass

        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[1]["attributes"]["region_ids"] == [1, 2]

    def test_workflow_span_sets_ok_status(self, ai_tracer, mock_tracer, mock_span):
        """Workflow span sets OK status on completion."""
        with ai_tracer.workflow_span("wf-001", "test"):
            pass

        mock_span.set_status.assert_called()


class TestAITracerStepSpan:
    """Test step span creation."""

    def test_step_span_correct_attributes(self, ai_tracer, mock_tracer):
        """Step span includes step.name."""
        with ai_tracer.step_span("build_context", workflow_id="wf-001"):
            pass

        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[0][0] == "step.build_context"
        assert call_args[1]["attributes"]["step.name"] == "build_context"
        assert call_args[1]["attributes"]["workflow.id"] == "wf-001"


class TestAITracerToolSpan:
    """Test tool span creation."""

    def test_tool_span_correct_attributes(self, ai_tracer, mock_tracer):
        """Tool span includes tool.name and agent.id."""
        with ai_tracer.tool_span(
            "geospatial_query", workflow_id="wf-001", agent_id="reference-agent"
        ):
            pass

        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[0][0] == "tool.geospatial_query"
        assert call_args[1]["attributes"]["tool.name"] == "geospatial_query"
        assert call_args[1]["attributes"]["agent.id"] == "reference-agent"


class TestAITracerLLMSpan:
    """Test LLM span creation."""

    def test_llm_span_correct_attributes(self, ai_tracer, mock_tracer):
        """LLM span includes llm.model."""
        with ai_tracer.llm_span("gpt-4o-mini", metadata={"tokens": 100}):
            pass

        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[0][0] == "llm.gpt-4o-mini"
        assert call_args[1]["attributes"]["llm.model"] == "gpt-4o-mini"
        assert call_args[1]["attributes"]["tokens"] == 100


class TestAITracerNonFatal:
    """Test non-fatal tracing behavior."""

    def test_tracing_failure_returns_noop_span(self):
        """When tracing fails, a _NoOpSpan is yielded."""
        with patch("src.ai.infrastructure.observability.tracing.trace") as mock_trace:
            mock_trace.get_tracer.return_value.start_as_current_span.side_effect = Exception(
                "OTel unavailable"
            )
            tracer = AITracer()

            # Should NOT raise
            with tracer.workflow_span("wf-001", "test") as span:
                assert isinstance(span, _NoOpSpan)

    def test_noop_span_methods_do_not_raise(self):
        """_NoOpSpan methods are safe no-ops."""
        span = _NoOpSpan()
        span.set_status(MagicMock())
        span.record_exception(Exception("test"))
        span.set_attribute("key", "value")
        # No exceptions


class TestAITracerErrorRecording:
    """Test error recording on spans."""

    def test_record_error_sets_error_status(self, ai_tracer, mock_span):
        """record_error sets ERROR status on the span."""
        error = ValueError("test error")
        ai_tracer.record_error(mock_span, error)

        mock_span.set_status.assert_called()
        mock_span.record_exception.assert_called_with(error)

    def test_record_error_non_fatal(self, ai_tracer):
        """Error recording failure does NOT raise."""
        bad_span = MagicMock()
        bad_span.set_status.side_effect = Exception("span broken")

        # Should NOT raise
        ai_tracer.record_error(bad_span, ValueError("test"))
