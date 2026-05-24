"""Risk Area Orchestrator (PRD §6).

Coordinates risk analysis via 3 specialized agents:
- Risk Classification (AGENT-RISK-CL-001)
- Territorial Prioritization (AGENT-RISK-PR-001)
- Predictive Scenarios (AGENT-RISK-SC-001)

Pre-builds context + hydric output, delegates to LangGraphOrchestrator,
transforms to RiskOutput, and persists agent executions.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from src.ai.application.orchestrator import LangGraphOrchestrator
from src.ai.domain.interfaces import ContextEngine
from src.ai.domain.models import (
    AgentManifest,
    AgentStatus,
    ExecutionLimits,
    ImpactSeverity,
    RiskLevel,
    RiskOutput,
)
from src.ai.infrastructure.state.state_manager import StateManagerImpl

logger = logging.getLogger(__name__)

_AGENT_CODES = {
    "risk_classification": "AGENT-RISK-CL-001",
    "territorial_prioritization": "AGENT-RISK-PR-001",
    "predictive_scenarios": "AGENT-RISK-SC-001",
}


class RiskOrchestrator:
    """Coordinates risk analysis via 3 specialized agents.

    Consumes hydric-environmental output (pre-built context) and territorial
    variables to produce classified, prioritized, and projected risk assessments.
    """

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
        indicator_codes: Optional[list[str]] = None,
        workflow_id: Optional[str] = None,
    ) -> RiskOutput:
        # 1. Pre-build context with territorial data
        context = self._context_engine.build_context(region_ids, indicator_codes)

        # 2. Enrich context with hydric and risk output placeholders
        context["hydric_output"] = hydric_output
        context["risk_output"] = {"risk_level": "moderate"}

        # 3. Create manifests and execute
        manifests = self._create_manifests()
        result = self._orchestrator.execute_workflow(
            region_ids=region_ids,
            agent_manifests=manifests,
            indicator_codes=indicator_codes,
            workflow_id=workflow_id,
            context=context,
        )

        # 4. Transform to RiskOutput
        output = self._transform_output(result)

        # 5. Overall completeness
        output.data_completeness = self._calc_overall_completeness(result)

        # 6. Persist executions
        self._persist_executions(result, workflow_id or result.get("workflow_id", ""))

        return output

    def _create_manifests(self) -> list[AgentManifest]:
        return [
            AgentManifest(
                name="risk_classification", version="1.0.0",
                entry_point="agent:RiskClassificationAgent",
                description="Risk level classification from hydric + territorial data",
                agent_type="risk",
                limits=ExecutionLimits(max_steps=10, max_tokens=4096, timeout_seconds=30),
            ),
            AgentManifest(
                name="territorial_prioritization", version="1.0.0",
                entry_point="agent:TerritorialPrioritizationAgent",
                description="Priority zone identification based on risk + exposure",
                agent_type="risk",
                limits=ExecutionLimits(max_steps=10, max_tokens=4096, timeout_seconds=30),
            ),
            AgentManifest(
                name="predictive_scenarios", version="1.0.0",
                entry_point="agent:PredictiveScenariosAgent",
                description="Risk scenario projections at 7/30/90 day horizons",
                agent_type="risk",
                limits=ExecutionLimits(max_steps=10, max_tokens=4096, timeout_seconds=30),
            ),
        ]

    def _transform_output(self, result: dict[str, Any]) -> RiskOutput:
        agent_outputs = result.get("agent_outputs", [])
        agent_manifests = result.get("agent_manifests", [])
        context = result.get("context", {})

        out_map = {}
        for i, m in enumerate(agent_manifests):
            name = m.get("name", f"agent_{i}")
            if i < len(agent_outputs):
                out_map[name] = agent_outputs[i]

        cls_out = out_map.get("risk_classification", {})
        prio_out = out_map.get("territorial_prioritization", {})
        scen_out = out_map.get("predictive_scenarios", {})

        region_ids = [
            r.get("id") for r in context.get("regions", []) if r.get("id") is not None
        ]

        return RiskOutput(
            area="risk",
            region_ids=region_ids,
            timestamp=datetime.now(timezone.utc).isoformat(),
            risk_level=RiskLevel(cls_out.get("risk_level", "low")),
            probability_score=cls_out.get("risk_score", 0.0),
            impact_severity=self._compute_impact_severity(cls_out),
            priority_zones=[],
            scenario_projections=[],
            confidence_score=cls_out.get("confidence_score", 0.0),
            natural_language_summary=self._build_nl_summary(cls_out, prio_out, scen_out),
            subagent_outputs=agent_outputs,
        )

    def _compute_impact_severity(self, cls_out: dict) -> ImpactSeverity:
        rl = cls_out.get("risk_level", "low")
        mapping = {
            "critical": ImpactSeverity.CATASTROPHIC,
            "high": ImpactSeverity.MAJOR,
            "moderate": ImpactSeverity.MODERATE,
        }
        return mapping.get(rl, ImpactSeverity.MINOR)

    def _calc_overall_completeness(self, result: dict) -> float:
        outputs = result.get("agent_outputs", [])
        if not outputs:
            return 0.0
        scores = [o.get("data_completeness", 0.0) for o in outputs]
        return round(sum(scores) / len(scores), 3)

    def _build_nl_summary(self, cls_out: dict, prio_out: dict, scen_out: dict) -> str:
        rl = cls_out.get("risk_level", "unknown")
        prio_count = len(prio_out.get("priority_zones", []))
        scen_count = len(scen_out.get("scenarios", []))
        return (
            f"Risk assessment: level {rl}. "
            f"{prio_count} priority zone(s) identified. "
            f"{scen_count} scenario projection(s) generated."
        )

    def _persist_executions(self, result: dict[str, Any], workflow_id: str) -> None:
        outputs = result.get("agent_outputs", [])
        manifests = result.get("agent_manifests", [])
        context_payload = result.get("context", {})
        now = datetime.now(timezone.utc).isoformat()

        for i, m in enumerate(manifests):
            name = m.get("name", f"agent_{i}")
            code = _AGENT_CODES.get(name, f"AGENT-UNKNOWN-{name}")
            out = outputs[i] if i < len(outputs) else {}
            error_msg = out.get("error")

            try:
                self._state_manager.persist_agent_execution(
                    agent_code=code,
                    orchestrator_area="risk",
                    workflow_id=workflow_id,
                    context_payload=context_payload,
                    structured_output={k: v for k, v in out.items()
                                       if k not in ("error",)},
                    natural_language_output=out.get("natural_language_output", ""),
                    confidence_score=out.get("confidence_score", 0.0),
                    data_completeness=out.get("data_completeness", 0.0),
                    started_at=now,
                    finished_at=now,
                    error_message=error_msg,
                    status=AgentStatus.FAILED.value if error_msg else AgentStatus.COMPLETED.value,
                )
            except Exception as e:
                logger.warning(f"Failed to persist risk execution for {name}: {e}")
