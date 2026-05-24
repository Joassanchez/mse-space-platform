"""OpenTelemetry tracing for the AI ecosystem (Modulo 4).

Provides span creation for workflow steps, tool calls, and LLM invocations.
All tracing operations are non-fatal — failures are logged but never
interrupt execution.

Usage:
    tracer = AITracer(service_name="ai-core")
    with tracer.workflow_span("wf-001", "analyze_region"):
        with tracer.step_span("build_context"):
            ...
        with tracer.tool_span("geospatial_query"):
            ...
        with tracer.llm_span("gpt-4o-mini"):
            ...
"""

import logging
from contextlib import contextmanager
from typing import Any, Generator, Optional

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

logger = logging.getLogger(__name__)


class AITracer:
    """OpenTelemetry tracer for AI workflow observability.

    Creates spans for:
    - Workflow lifecycle (start, complete, fail)
    - Individual workflow steps
    - Tool invocations
    - LLM completions

    All span operations are wrapped in try/except — tracing failures
    are logged as warnings but never raise exceptions to callers.
    """

    def __init__(self, service_name: str = "ai-core") -> None:
        """Initialize the AI tracer.

        Args:
            service_name: OpenTelemetry service name for the tracer.
        """
        self._tracer = trace.get_tracer(service_name)

    @contextmanager
    def workflow_span(
        self,
        workflow_id: str,
        workflow_type: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Generator[Span, None, None]:
        """Create a span for the entire workflow lifecycle.

        Args:
            workflow_id: Unique workflow identifier.
            workflow_type: Type of workflow (e.g. "analyze_region").
            metadata: Optional metadata to attach as span attributes.

        Yields:
            OpenTelemetry Span object for the workflow.
        """
        try:
            with self._tracer.start_as_current_span(
                f"workflow.{workflow_type}",
                attributes={
                    "workflow.id": workflow_id,
                    "workflow.type": workflow_type,
                    **(metadata or {}),
                },
            ) as span:
                yield span
                span.set_status(Status(StatusCode.OK))
        except Exception as e:
            logger.warning(f"Tracing workflow span failed (non-fatal): {e}")
            # Yield a no-op span context so the caller's code still works
            yield _NoOpSpan()

    @contextmanager
    def step_span(
        self,
        step_name: str,
        workflow_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Generator[Span, None, None]:
        """Create a span for a single workflow step.

        Args:
            step_name: Step identifier (e.g. "build_context", "execute_agents").
            workflow_id: Optional parent workflow ID for correlation.
            metadata: Optional metadata to attach as span attributes.

        Yields:
            OpenTelemetry Span object for the step.
        """
        try:
            attrs: dict[str, Any] = {"step.name": step_name}
            if workflow_id:
                attrs["workflow.id"] = workflow_id
            if metadata:
                attrs.update(metadata)

            with self._tracer.start_as_current_span(
                f"step.{step_name}",
                attributes=attrs,
            ) as span:
                yield span
                span.set_status(Status(StatusCode.OK))
        except Exception as e:
            logger.warning(f"Tracing step span '{step_name}' failed (non-fatal): {e}")
            yield _NoOpSpan()

    @contextmanager
    def tool_span(
        self,
        tool_name: str,
        workflow_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Generator[Span, None, None]:
        """Create a span for a tool invocation.

        Args:
            tool_name: Tool identifier (e.g. "geospatial_query").
            workflow_id: Optional parent workflow ID.
            agent_id: Optional agent that invoked the tool.
            metadata: Optional metadata to attach as span attributes.

        Yields:
            OpenTelemetry Span object for the tool call.
        """
        try:
            attrs: dict[str, Any] = {"tool.name": tool_name}
            if workflow_id:
                attrs["workflow.id"] = workflow_id
            if agent_id:
                attrs["agent.id"] = agent_id
            if metadata:
                attrs.update(metadata)

            with self._tracer.start_as_current_span(
                f"tool.{tool_name}",
                attributes=attrs,
            ) as span:
                yield span
                span.set_status(Status(StatusCode.OK))
        except Exception as e:
            logger.warning(f"Tracing tool span '{tool_name}' failed (non-fatal): {e}")
            yield _NoOpSpan()

    @contextmanager
    def llm_span(
        self,
        model: str,
        workflow_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Generator[Span, None, None]:
        """Create a span for an LLM invocation.

        Args:
            model: LLM model identifier (e.g. "gpt-4o-mini").
            workflow_id: Optional parent workflow ID.
            agent_id: Optional agent that invoked the LLM.
            metadata: Optional metadata (token usage, latency, etc.).

        Yields:
            OpenTelemetry Span object for the LLM call.
        """
        try:
            attrs: dict[str, Any] = {
                "llm.model": model,
            }
            if workflow_id:
                attrs["workflow.id"] = workflow_id
            if agent_id:
                attrs["agent.id"] = agent_id
            if metadata:
                attrs.update(metadata)

            with self._tracer.start_as_current_span(
                f"llm.{model}",
                attributes=attrs,
            ) as span:
                yield span
                span.set_status(Status(StatusCode.OK))
        except Exception as e:
            logger.warning(f"Tracing LLM span '{model}' failed (non-fatal): {e}")
            yield _NoOpSpan()

    def record_error(
        self,
        span: Span,
        error: Exception,
        workflow_id: Optional[str] = None,
    ) -> None:
        """Record an error on an existing span.

        Args:
            span: The span to record the error on.
            error: The exception that occurred.
            workflow_id: Optional workflow ID for logging.
        """
        try:
            span.set_status(Status(StatusCode.ERROR, str(error)))
            span.record_exception(error)
        except Exception as e:
            logger.warning(f"Recording error on span failed (non-fatal): {e}")


class _NoOpSpan:
    """Minimal no-op span for graceful degradation when tracing fails."""

    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def set_status(self, *args: Any, **kwargs: Any) -> None:
        pass

    def record_exception(self, *args: Any, **kwargs: Any) -> None:
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        pass
