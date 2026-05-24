"""Observability package for the AI ecosystem (Modulo 4).

Provides OpenTelemetry tracing and audit logging for AI workflows,
agents, and tool calls. All observability writes are non-fatal —
failures are logged but never interrupt execution.
"""

from src.ai.infrastructure.observability.tracing import AITracer
from src.ai.infrastructure.observability.audit_logger import AIAuditLogger

__all__ = ["AITracer", "AIAuditLogger"]
