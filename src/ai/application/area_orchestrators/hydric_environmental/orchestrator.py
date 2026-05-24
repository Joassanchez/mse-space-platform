"""Hydric Environmental Area Orchestrator.

Coordinates hydric-environmental analysis via 3 specialized agents:
- Soil Moisture (AGENT-HYD-SM-001)
- Weather (AGENT-HYD-MET-001)
- Drought (AGENT-HYD-DR-001)

Pre-builds context via ContextEngine, delegates execution to
LangGraphOrchestrator, transforms output to area-specific schema,
and persists individual agent execution records.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from src.ai.application.orchestrator import LangGraphOrchestrator
from src.ai.domain.interfaces import ContextEngine
from src.ai.domain.models import (
    AgentManifest,
    AgentStatus,
    DroughtSignal,
    ExecutionLimits,
    HydricCondition,
    HydricEnvironmentalOutput,
    SoilMoistureStatus,
)
from src.ai.infrastructure.state.state_manager import StateManagerImpl

logger = logging.getLogger(__name__)

# Expected indicator codes per agent
_SM_INDICATORS = {"SM_SURFACE", "SM_ROOTZONE"}
_WEATHER_INDICATORS = {"RAINFALL_30D", "RAINFALL_ANOMALY"}
_DROUGHT_INDICATORS = {"SPI_30D", "SPI_90D"}

# Confidence weights per agent
_WEIGHTS = {"soil_moisture": 0.4, "weather": 0.3, "drought": 0.3}

# Agent code mapping
_AGENT_CODES = {
    "soil_moisture": "AGENT-HYD-SM-001",
    "weather": "AGENT-HYD-MET-001",
    "drought": "AGENT-HYD-DR-001",
}


class HydricEnvironmentalOrchestrator:
    """Coordinates hydric-environmental analysis via 3 specialized agents.

    Pre-builds context, delegates execution to LangGraphOrchestrator,
    transforms output to area-specific schema, and persists agent_executions.
    """

    def __init__(
        self,
        context_engine: ContextEngine,
        orchestrator: LangGraphOrchestrator,
        state_manager: StateManagerImpl,
    ):
        """Initialize with dependencies.

        Args:
            context_engine: ContextEngine for pre-building geospatial context.
            orchestrator: LangGraphOrchestrator for agent coordination.
            state_manager: StateManagerImpl for persisting agent executions.
        """
        self._context_engine = context_engine
        self._orchestrator = orchestrator
        self._state_manager = state_manager

    def execute(
        self,
        region_ids: list[int],
        indicator_codes: Optional[list[str]] = None,
        workflow_id: Optional[str] = None,
    ) -> HydricEnvironmentalOutput:
        """Execute the full hydric-environmental analysis workflow.

        1. Pre-build context via ContextEngine
        2. Calculate data completeness per agent
        3. Create agent manifests
        4. Execute via LangGraphOrchestrator with pre-built context
        5. Transform to HydricEnvironmentalOutput
        6. Persist agent execution records

        Args:
            region_ids: Regions to analyze.
            indicator_codes: Optional filter for context building.
            workflow_id: Optional explicit workflow ID.

        Returns:
            HydricEnvironmentalOutput with consolidated analysis.
        """
        # 1. Pre-build context
        context = self._context_engine.build_context(
            region_ids, indicator_codes
        )

        # 2. Calculate data completeness per agent
        sm_completeness = self._calc_completeness(context, _SM_INDICATORS)
        weather_completeness = self._calc_completeness(context, _WEATHER_INDICATORS)
        drought_completeness = self._calc_completeness(context, _DROUGHT_INDICATORS)

        logger.info(
            f"Hydric workflow: data completeness — "
            f"SM={sm_completeness:.2f}, Weather={weather_completeness:.2f}, "
            f"Drought={drought_completeness:.2f}"
        )

        # 3. Create agent manifests
        manifests = self._create_manifests(
            sm_completeness, weather_completeness, drought_completeness
        )

        # 4. Execute via LangGraphOrchestrator with pre-built context
        result = self._orchestrator.execute_workflow(
            region_ids=region_ids,
            agent_manifests=manifests,
            indicator_codes=indicator_codes,
            workflow_id=workflow_id,
            context=context,
        )

        # 5. Transform to HydricEnvironmentalOutput
        output = self._transform_output(result)

        # Attach completeness info to output
        overall_completeness = (
            sm_completeness + weather_completeness + drought_completeness
        ) / 3.0
        output.data_completeness = round(overall_completeness, 3)

        # 6. Persist agent execution records
        self._persist_executions(result, workflow_id or result.get("workflow_id", ""))

        return output

    def _calc_completeness(
        self, context: dict, expected_codes: set[str]
    ) -> float:
        """Calculate data completeness: found_indicators / expected_indicators.

        Args:
            context: Context payload from ContextEngine.build_context().
            expected_codes: Set of indicator codes expected for this agent.

        Returns:
            Completeness fraction (0.0-1.0).
        """
        indicators = context.get("indicators", [])
        if not indicators or not expected_codes:
            return 0.0

        found_codes = {
            ind.get("indicator_code")
            for ind in indicators
            if ind.get("indicator_code")
        }
        found = found_codes & expected_codes
        return len(found) / len(expected_codes)

    def _create_manifests(
        self,
        sm_completeness: float,
        weather_completeness: float,
        drought_completeness: float,
    ) -> list[AgentManifest]:
        """Create AgentManifest instances for the 3 hydric agents.

        Args:
            sm_completeness: Data completeness for soil moisture agent.
            weather_completeness: Data completeness for weather agent.
            drought_completeness: Data completeness for drought agent.

        Returns:
            List of 3 AgentManifest instances.
        """
        return [
            AgentManifest(
                name="soil_moisture",
                version="1.0.0",
                entry_point="agent:SoilMoistureAgent",
                description="Soil moisture analysis from SMAP data",
                agent_type="hydric",
                limits=ExecutionLimits(max_steps=10, max_tokens=4096, timeout_seconds=30),
            ),
            AgentManifest(
                name="weather",
                version="1.0.0",
                entry_point="agent:WeatherAgent",
                description="Weather and rainfall anomaly analysis",
                agent_type="hydric",
                limits=ExecutionLimits(max_steps=10, max_tokens=4096, timeout_seconds=30),
            ),
            AgentManifest(
                name="drought",
                version="1.0.0",
                entry_point="agent:DroughtAgent",
                description="Drought classification from SPI indicators",
                agent_type="hydric",
                limits=ExecutionLimits(max_steps=10, max_tokens=4096, timeout_seconds=30),
            ),
        ]

    def _transform_output(
        self, result: dict[str, Any]
    ) -> HydricEnvironmentalOutput:
        """Transform generic consolidated response to HydricEnvironmentalOutput.

        Extracts per-agent outputs from the workflow result and maps them
        to the area-specific schema.

        Args:
            result: Workflow result from LangGraphOrchestrator.execute_workflow().

        Returns:
            HydricEnvironmentalOutput with consolidated area analysis.
        """
        consolidated = result.get("consolidated_response", {})
        agent_outputs = result.get("agent_outputs", [])
        agent_manifests = result.get("agent_manifests", [])

        # Build agent name → output mapping
        agent_output_map: dict[str, dict] = {}
        for i, manifest in enumerate(agent_manifests):
            name = manifest.get("name", f"agent_{i}")
            if i < len(agent_outputs):
                agent_output_map[name] = agent_outputs[i]

        # Extract soil moisture status
        sm_output = agent_output_map.get("soil_moisture", {})
        soil_moisture_status = self._extract_sm_status(sm_output)

        # Extract drought signal
        drought_output = agent_output_map.get("drought", {})
        drought_signal = self._extract_drought_signal(drought_output)

        # Flood detection: default false for MVP (no SAR data)
        flood_detected = False

        # Compute overall hydric condition
        weather_output = agent_output_map.get("weather", {})
        overall_condition = self._compute_hydric_condition(
            soil_moisture_status, drought_signal, weather_output
        )

        # Confidence score with degradation
        confidence = self._calc_confidence(
            sm_output, weather_output, drought_output
        )

        # Template-based natural language summary
        nl_summary = self._build_nl_summary(
            soil_moisture_status, drought_signal, overall_condition, confidence
        )

        # Extract region IDs from context
        context = result.get("context", {})
        region_ids = [
            r.get("id") for r in context.get("regions", []) if r.get("id") is not None
        ]

        return HydricEnvironmentalOutput(
            area=self._extract_area(result),
            region_ids=region_ids,
            timestamp=datetime.now(timezone.utc).isoformat(),
            soil_moisture_status=soil_moisture_status,
            flood_detected=flood_detected,
            drought_signal=drought_signal,
            overall_hydric_condition=overall_condition,
            confidence_score=confidence,
            natural_language_summary=nl_summary,
            subagent_outputs=agent_outputs,
        )

    def _extract_sm_status(self, output: dict) -> SoilMoistureStatus:
        """Extract soil moisture status from agent output.

        Args:
            output: Soil moisture agent output dict.

        Returns:
            SoilMoistureStatus enum value.
        """
        # Try structured field first
        status = output.get("sm_surface_status")
        if status:
            try:
                return SoilMoistureStatus(status)
            except (ValueError, TypeError):
                pass

        # Fallback: check conclusion text
        conclusion = output.get("conclusion", "").lower()
        if "critical dry" in conclusion or "critically dry" in conclusion:
            return SoilMoistureStatus.CRITICAL_DRY
        if "critical wet" in conclusion or "critically wet" in conclusion:
            return SoilMoistureStatus.CRITICAL_WET
        if "dry" in conclusion:
            return SoilMoistureStatus.DRY
        if "wet" in conclusion:
            return SoilMoistureStatus.WET
        if "failed" in conclusion or "error" in conclusion:
            return SoilMoistureStatus.UNAVAILABLE

        return SoilMoistureStatus.UNAVAILABLE

    def _extract_drought_signal(self, output: dict) -> DroughtSignal:
        """Extract drought signal from agent output.

        Args:
            output: Drought agent output dict.

        Returns:
            DroughtSignal enum value.
        """
        signal = output.get("drought_signal")
        if signal:
            try:
                return DroughtSignal(signal)
            except (ValueError, TypeError):
                pass

        # Fallback: check conclusion text
        conclusion = output.get("conclusion", "").lower()
        if "severe" in conclusion:
            return DroughtSignal.SEVERE
        if "moderate" in conclusion:
            return DroughtSignal.MODERATE
        if "mild" in conclusion:
            return DroughtSignal.MILD
        if "failed" in conclusion or "error" in conclusion:
            return DroughtSignal.NONE

        return DroughtSignal.NONE

    def _compute_hydric_condition(
        self,
        sm_status: SoilMoistureStatus,
        drought_signal: DroughtSignal,
        weather_output: dict,
    ) -> HydricCondition:
        """Compute overall hydric condition from all 3 agent outputs.

        Args:
            sm_status: Soil moisture status classification.
            drought_signal: Drought signal classification.
            weather_output: Weather agent output dict.

        Returns:
            HydricCondition enum value.
        """
        critical_sm = sm_status in (
            SoilMoistureStatus.CRITICAL_DRY,
            SoilMoistureStatus.CRITICAL_WET,
        )
        severe_drought = drought_signal == DroughtSignal.SEVERE

        if critical_sm or severe_drought:
            return HydricCondition.CRITICAL

        stressed_sm = sm_status in (
            SoilMoistureStatus.DRY,
            SoilMoistureStatus.WET,
        )
        moderate_drought = drought_signal in (
            DroughtSignal.MODERATE,
            DroughtSignal.SEVERE,
        )

        if stressed_sm or moderate_drought:
            return HydricCondition.STRESSED

        # Any non-normal, non-critical signal → moderate
        non_normal = (
            sm_status not in (SoilMoistureStatus.NORMAL, SoilMoistureStatus.UNAVAILABLE)
            or drought_signal != DroughtSignal.NONE
        )
        if non_normal:
            return HydricCondition.MODERATE

        return HydricCondition.OPTIMAL

    def _calc_confidence(
        self,
        sm_output: dict,
        weather_output: dict,
        drought_output: dict,
    ) -> float:
        """Calculate area-level confidence with degradation logic.

        confidence = weighted average (SM=0.4, Weather=0.3, Drought=0.3)
        If any agent has data_completeness < 0.5, degrade by 20%.

        Args:
            sm_output: Soil moisture agent output.
            weather_output: Weather agent output.
            drought_output: Drought agent output.

        Returns:
            Confidence score (0.0-1.0).
        """
        sm_conf = sm_output.get("confidence_score", 0.0)
        weather_conf = weather_output.get("confidence_score", 0.0)
        drought_conf = drought_output.get("confidence_score", 0.0)

        weighted = (
            sm_conf * _WEIGHTS["soil_moisture"]
            + weather_conf * _WEIGHTS["weather"]
            + drought_conf * _WEIGHTS["drought"]
        )

        # Degradation: if any agent has low data completeness
        sm_completeness = sm_output.get("data_completeness", 0.0)
        weather_completeness = weather_output.get("data_completeness", 0.0)
        drought_completeness = drought_output.get("data_completeness", 0.0)

        if (
            sm_completeness < 0.5
            or weather_completeness < 0.5
            or drought_completeness < 0.5
        ):
            weighted *= 0.8  # Degrade by 20%

        return round(min(weighted, 1.0), 3)

    def _build_nl_summary(
        self,
        sm_status: SoilMoistureStatus,
        drought_signal: DroughtSignal,
        condition: HydricCondition,
        confidence: float,
    ) -> str:
        """Build template-based natural language summary.

        No LLM calls — deterministic template rendering.

        Args:
            sm_status: Soil moisture status.
            drought_signal: Drought signal.
            condition: Overall hydric condition.
            confidence: Area-level confidence score.

        Returns:
            Template-based NL summary string.
        """
        condition_labels = {
            HydricCondition.OPTIMAL: "optimal",
            HydricCondition.MODERATE: "moderate",
            HydricCondition.STRESSED: "stressed",
            HydricCondition.CRITICAL: "critical",
        }
        sm_labels = {
            SoilMoistureStatus.NORMAL: "normal",
            SoilMoistureStatus.DRY: "dry",
            SoilMoistureStatus.WET: "wet",
            SoilMoistureStatus.CRITICAL_DRY: "critically dry",
            SoilMoistureStatus.CRITICAL_WET: "critically wet",
            SoilMoistureStatus.UNAVAILABLE: "unavailable",
        }
        drought_labels = {
            DroughtSignal.NONE: "no drought signal",
            DroughtSignal.MILD: "mild drought signal",
            DroughtSignal.MODERATE: "moderate drought signal",
            DroughtSignal.SEVERE: "severe drought signal",
        }

        return (
            f"Hydric-environmental analysis: overall condition is "
            f"{condition_labels.get(condition, 'unknown')}. "
            f"Soil moisture: {sm_labels.get(sm_status, 'unknown')}. "
            f"Drought: {drought_labels.get(drought_signal, 'unknown')}. "
            f"Confidence: {confidence:.0%}."
        )

    def _extract_area(self, result: dict[str, Any]) -> str:
        """Extract area identifier from workflow result.

        The area identifier is the orchestrator area code (e.g. "hydric_environmental"),
        NOT the geographic region. Region info is in the context payload.

        Args:
            result: Workflow result dict.

        Returns:
            Area identifier string: "hydric_environmental".
        """
        return "hydric_environmental"

    def _persist_executions(
        self, result: dict[str, Any], workflow_id: str
    ) -> None:
        """Persist individual agent execution records.

        For each agent output, calls state_manager.persist_agent_execution()
        with context_payload, structured_output, natural_language_output,
        confidence_score, and data_completeness.

        Args:
            result: Workflow result from LangGraphOrchestrator.
            workflow_id: Parent workflow run ID.
        """
        agent_outputs = result.get("agent_outputs", [])
        agent_manifests = result.get("agent_manifests", [])
        context_payload = result.get("context", {})

        now = datetime.now(timezone.utc).isoformat()

        for i, manifest in enumerate(agent_manifests):
            agent_name = manifest.get("name", f"agent_{i}")
            agent_code = _AGENT_CODES.get(agent_name, f"AGENT-UNKNOWN-{agent_name}")

            output = agent_outputs[i] if i < len(agent_outputs) else {}

            # Extract structured output (all fields except conclusion/confidence)
            structured_output = {
                k: v
                for k, v in output.items()
                if k not in ("conclusion", "confidence", "error")
            }

            # Natural language output
            nl_output = output.get("natural_language_output", output.get("conclusion", ""))

            # Confidence and completeness
            conf_score = output.get("confidence", 0.0)
            data_completeness = output.get("data_completeness", 0.0)

            # Error handling
            error_msg = output.get("error")
            status = AgentStatus.FAILED.value if error_msg else AgentStatus.COMPLETED.value

            try:
                self._state_manager.persist_agent_execution(
                    agent_code=agent_code,
                    orchestrator_area="hydric-environmental",
                    workflow_id=workflow_id,
                    context_payload=context_payload,
                    structured_output=structured_output,
                    natural_language_output=nl_output,
                    confidence_score=conf_score,
                    data_completeness=data_completeness,
                    started_at=now,
                    finished_at=now,
                    error_message=error_msg,
                    status=status,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to persist agent execution for {agent_name}: {e}"
                )
