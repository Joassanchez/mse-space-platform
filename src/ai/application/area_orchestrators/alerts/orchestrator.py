"""Alerts Area Orchestrator (PRD §8).

Coordinates 4 sub-agents:
- Alert Classification (AGENT-ALT-CL-001)
- Risk Communication (AGENT-ALT-COM-001)
- Operational Recommendations (AGENT-ALT-REC-001)
- Executive Summary (AGENT-ALT-EX-001)

Consumes hydric + risk outputs via pre-built context.
"""

import logging
from typing import Any, Optional

from src.ai.application.orchestrator import LangGraphOrchestrator
from src.ai.domain.interfaces import ContextEngine
from src.ai.domain.models import (
    AgentManifest,
    AgentStatus,
    AlertOutput,
    AlertSeverity,
    ExecutionLimits,
)
from src.ai.infrastructure.state.state_manager import StateManagerImpl

logger = logging.getLogger(__name__)

_AGENT_CODES = {
    "alert_classification": "AGENT-ALT-CL-001",
    "risk_communication": "AGENT-ALT-COM-001",
    "operational_recommendations": "AGENT-ALT-REC-001",
    "executive_summary": "AGENT-ALT-EX-001",
}


class AlertsOrchestrator:
    """Coordinates alert generation via 4 specialized agents."""

    def __init__(
        self,
        context_engine: ContextEngine,
        orchestrator: LangGraphOrchestrator,
        state_manager: StateManagerImpl,
    ):
        self._context_engine = context_engine
        self._orchestrator = orchestrator
        self._state_manager = state_manager

    def execute(
        self,
        region_ids: list[int],
        hydric_output: dict[str, Any],
        risk_output: dict[str, Any],
        indicator_codes: Optional[list[str]] = None,
        workflow_id: Optional[str] = None,
    ) -> AlertOutput:
        context = self._context_engine.build_context(region_ids, indicator_codes)
        context["hydric_output"] = hydric_output
        context["risk_output"] = risk_output
        context["alert_classification"] = {}

        manifests = self._create_manifests()
        result = self._orchestrator.execute_workflow(
            region_ids=region_ids,
            agent_manifests=manifests,
            indicator_codes=indicator_codes,
            workflow_id=workflow_id,
            context=context,
        )

        output = self._transform_output(result)
        self._persist_executions(result, workflow_id or result.get("workflow_id", ""))
        return output

    def _create_manifests(self) -> list[AgentManifest]:
        return [
            AgentManifest(name="alert_classification", version="1.0.0",
                entry_point="agent:AlertClassificationAgent",
                description="Alert severity and event type classification",
                agent_type="alerts",
                limits=ExecutionLimits(max_steps=5, max_tokens=2048, timeout_seconds=15)),
            AgentManifest(name="risk_communication", version="1.0.0",
                entry_point="agent:RiskCommunicationAgent",
                description="Differentiated messages per audience",
                agent_type="alerts",
                limits=ExecutionLimits(max_steps=5, max_tokens=2048, timeout_seconds=15)),
            AgentManifest(name="operational_recommendations", version="1.0.0",
                entry_point="agent:OperationalRecommendationsAgent",
                description="Prioritized operational actions",
                agent_type="alerts",
                limits=ExecutionLimits(max_steps=5, max_tokens=2048, timeout_seconds=15)),
            AgentManifest(name="executive_summary", version="1.0.0",
                entry_point="agent:ExecutiveSummaryAgent",
                description="Executive report synthesis",
                agent_type="alerts",
                limits=ExecutionLimits(max_steps=5, max_tokens=2048, timeout_seconds=15)),
        ]

    def _transform_output(self, result: dict[str, Any]) -> AlertOutput:
        outputs = result.get("agent_outputs", [])
        manifests = result.get("agent_manifests", [])
        out_map = {}
        for i, m in enumerate(manifests):
            name = m.get("name", f"agent_{i}")
            if i < len(outputs):
                out_map[name] = outputs[i]

        cls_out = out_map.get("alert_classification", {})
        comm_out = out_map.get("risk_communication", {})
        rec_out = out_map.get("operational_recommendations", {})
        exec_out = out_map.get("executive_summary", {})

        import uuid
        return AlertOutput(
            alert_id=str(uuid.uuid4()),
            severity=AlertSeverity(cls_out.get("severity", "info")),
            event_type=cls_out.get("event_type", "soil_moisture"),
            target_audience=list(comm_out.get("messages", {}).keys()),
            messages=comm_out.get("messages", {}),
            recommended_actions=[
                a.get("action", "") for a in rec_out.get("recommended_actions", [])
            ],
            executive_summary=exec_out.get("executive_summary", ""),
            confidence_score=cls_out.get("confidence_score", 0.0),
        )

    def _persist_executions(self, result: dict[str, Any], workflow_id: str) -> None:
        outputs = result.get("agent_outputs", [])
        manifests = result.get("agent_manifests", [])
        ctx = result.get("context", {})
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        for i, m in enumerate(manifests):
            name = m.get("name", f"agent_{i}")
            code = _AGENT_CODES.get(name, f"AGENT-UNKNOWN-{name}")
            out = outputs[i] if i < len(outputs) else {}
            try:
                self._state_manager.persist_agent_execution(
                    agent_code=code, orchestrator_area="alerts",
                    workflow_id=workflow_id, context_payload=ctx,
                    structured_output=out,
                    natural_language_output=out.get("natural_language_output", ""),
                    confidence_score=out.get("confidence_score", 0.0),
                    data_completeness=out.get("data_completeness", 0.0),
                    started_at=now, finished_at=now,
                    error_message=out.get("error"),
                    status=AgentStatus.FAILED.value if out.get("error") else AgentStatus.COMPLETED.value,
                )
            except Exception as e:
                logger.warning(f"Failed to persist alert execution for {name}: {e}")
