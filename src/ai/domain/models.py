"""Domain models for the AI ecosystem (Módulo 4).

Dataclasses represent the core entities flowing through the AI pipeline:
workflow states, execution traces, agent manifests, tool results, and LLM I/O.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


@dataclass
class ExecutionLimits:
    """Configurable limits for agent execution."""

    max_steps: int = 10
    max_tokens: int = 4096
    timeout_seconds: int = 30


@dataclass
class WorkflowState:
    """Persistence model for an AI workflow execution state.

    Attributes:
        workflow_id: Unique identifier for the workflow run.
        status: Current lifecycle state (pending, running, completed, failed).
        context: Structured context payload built by the Context Engine.
        metadata: Additional JSONB metadata (region_ids, agent_ids, etc.).
        id: Database-assigned ID (None before insert).
        created_at: ISO timestamp of creation.
        updated_at: ISO timestamp of last update.
    """

    workflow_id: str
    status: str = "pending"
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class ExecutionTrace:
    """Persistence model for a single step in an AI workflow execution.

    Attributes:
        state_id: FK reference to ai_workflow_states.id (logical, no FK constraint).
        step: Step identifier (e.g. "build_context", "execute_agent").
        action: Action performed in this step.
        result: Output/result of the step (JSON-serializable).
        error: Error message if the step failed.
        id: Database-assigned ID (None before insert).
        created_at: ISO timestamp of creation.
    """

    state_id: int
    step: str
    action: str
    result: Optional[Any] = None
    error: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class AgentManifest:
    """Declarative manifest for an AI agent plugin.

    Loaded from YAML files in src/ai/agents/*/manifest.yaml.
    Validated against JSON Schema before agent registration.

    Attributes:
        name: Agent identifier (e.g. "reference-agent").
        version: Semantic version string.
        entry_point: Module:class reference (e.g. "agent:ReferenceAgent").
        description: Human-readable description.
        tools: List of tool names this agent is allowed to use.
        limits: Execution limits (max_steps, max_tokens, timeout).
        output_schema: JSON Schema for validating agent output.
        agent_type: Type identifier (e.g. "reference").
    """

    name: str
    version: str
    entry_point: str
    description: str
    tools: list[str] = field(default_factory=list)
    limits: Optional[ExecutionLimits] = None
    output_schema: dict[str, Any] = field(default_factory=dict)
    agent_type: str = "reference"


@dataclass
class ToolResult:
    """Result of a tool execution.

    Attributes:
        tool_name: Identifier of the tool that was executed.
        success: Whether the execution succeeded.
        data: Result data (JSON-serializable).
        error: Error message if execution failed.
    """

    tool_name: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class LLMRequest:
    """Request parameters for an LLM completion.

    Attributes:
        prompt: The user/system prompt text.
        context: Optional structured context to include.
        model: Model identifier (e.g. "gpt-4", "claude-3-sonnet").
        max_tokens: Maximum tokens in the response.
        temperature: Sampling temperature (0.0-1.0).
    """

    prompt: str
    context: Optional[str] = None
    model: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.7


@dataclass
class LLMResponse:
    """Response from an LLM completion.

    Attributes:
        content: Generated text content.
        model: Model that generated the response.
        usage: Token usage statistics (prompt_tokens, completion_tokens, total_tokens).
        latency_ms: Time taken for the request in milliseconds.
        cost_usd: Estimated cost (if tracking enabled).
        metadata: Additional response metadata.
    """

    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    cost_usd: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# Módulo 5 — Area Orchestrators & Hydric Environmental Agents
# ============================================================


class SoilMoistureStatus(str, Enum):
    """Classification of soil moisture conditions from SMAP data."""

    NORMAL = "normal"
    DRY = "dry"
    WET = "wet"
    CRITICAL_DRY = "critical_dry"
    CRITICAL_WET = "critical_wet"
    UNAVAILABLE = "unavailable"


class WeatherCondition(str, Enum):
    """Rainfall anomaly classification relative to historical average."""

    FAR_BELOW = "far_below"
    BELOW_AVERAGE = "below_average"
    AVERAGE = "average"
    ABOVE_AVERAGE = "above_average"
    FAR_ABOVE = "far_above"


class DroughtCategory(str, Enum):
    """Drought severity category based on SPI thresholds."""

    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    EXTREME = "extreme"


class SpiStatus(str, Enum):
    """SPI-based moisture status derived from Standardized Precipitation Index.

    Maps to USDM (U.S. Drought Monitor) standard categories:
    - NORMAL → D0 (abnormally dry / no drought)
    - MODERATE_DROUGHT → D1 (moderate drought)
    - SEVERE_DROUGHT → D2 (severe drought)
    - EXTREME_DROUGHT → D3+ (extreme to exceptional drought)
    """

    NORMAL = "normal"
    MODERATE_DROUGHT = "moderate_drought"
    SEVERE_DROUGHT = "severe_drought"
    EXTREME_DROUGHT = "extreme_drought"


class DroughtSignal(str, Enum):
    """Actionable drought signal derived from SPI + soil moisture combination."""

    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"


class HydricCondition(str, Enum):
    """Overall hydric-environmental condition of an area."""

    OPTIMAL = "optimal"
    MODERATE = "moderate"
    STRESSED = "stressed"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    """Risk classification level (PRD §6.3)."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ImpactSeverity(str, Enum):
    """Impact severity classification (PRD §6.3)."""

    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CATASTROPHIC = "catastrophic"


class AgentStatus(str, Enum):
    """Lifecycle status of an agent execution record."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================
# Módulo 5 — Area Orchestrators & Hydric Environmental Agents
# ============================================================


@dataclass
class SoilMoistureOutput:
    """Structured output from the SoilMoistureAgent (AGENT-HYD-SM-001)."""

    surface_moisture: Optional[float] = None
    rootzone_moisture: Optional[float] = None
    sm_surface_status: str = "unavailable"
    sm_rootzone_status: str = "unavailable"
    trend_7d: str = "stable"
    anomaly_pct: Optional[float] = None
    confidence_score: float = 0.0
    data_completeness: float = 0.0
    natural_language_output: str = ""


@dataclass
class WeatherOutput:
    """Structured output from the WeatherAgent (AGENT-HYD-MET-001)."""

    rainfall_30d_mm: Optional[float] = None
    rainfall_7d_mm: Optional[float] = None
    rainfall_anomaly_pct: Optional[float] = None
    condition: str = "average"
    temperature_anomaly: Optional[float] = None
    temp_avg: Optional[float] = None
    humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    forecast_relevance: Optional[float] = None
    confidence_score: float = 0.0
    data_completeness: float = 0.0
    natural_language_output: str = ""


@dataclass
class DroughtOutput:
    """Structured output from the DroughtAgent (AGENT-HYD-DR-001)."""

    spi_30d: Optional[float] = None
    spi_90d: Optional[float] = None
    spi_status: str = "normal"
    drought_category: str = "none"
    drought_signal: str = "none"
    duration_weeks: Optional[int] = None
    spatial_extent_pct: Optional[float] = None
    trend: str = "stable"
    confidence_score: float = 0.0
    data_completeness: float = 0.0
    natural_language_output: str = ""


@dataclass
class HydricEnvironmentalOutput:
    """Consolidated output from the HydricEnvironmentalOrchestrator."""

    area: str = ""
    region_ids: list[int] = field(default_factory=list)
    timestamp: Optional[str] = None
    soil_moisture_status: SoilMoistureStatus = SoilMoistureStatus.UNAVAILABLE
    flood_detected: bool = False
    drought_signal: DroughtSignal = DroughtSignal.NONE
    overall_hydric_condition: HydricCondition = HydricCondition.OPTIMAL
    confidence_score: float = 0.0
    data_completeness: float = 0.0
    natural_language_summary: str = ""
    subagent_outputs: list[dict] = field(default_factory=list)


class AlertSeverity(str, Enum):
    """Alert severity classification (PRD §8.3)."""

    INFO = "info"
    WARNING = "warning"
    ALERT = "alert"
    CRITICAL = "critical"


class AlertEventType(str, Enum):
    """Type of event detected by the alert system (PRD §8.3)."""

    DROUGHT = "drought"
    FLOOD = "flood"
    SOIL_MOISTURE = "soil_moisture"
    WEATHER_ANOMALY = "weather_anomaly"
    RISK_ESCALATION = "risk_escalation"
    ECONOMIC_IMPACT = "economic_impact"


class TargetAudience(str, Enum):
    """Target audience for alerts (PRD §8.3)."""

    MUNICIPALITIES = "municipalities"
    PRODUCERS = "producers"
    COOPERATIVES = "cooperatives"
    INSURERS = "insurers"


@dataclass
class AffectedZone:
    """A zone affected by risk with coordinates and level (PRD §6.3)."""

    zone_id: str = ""
    zone_name: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    probability_score: float = 0.0
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    area_km2: Optional[float] = None


@dataclass
class AlertOutput:
    """Consolidated output from the AlertsOrchestrator (PRD §8.3)."""

    alert_id: str = ""
    severity: AlertSeverity = AlertSeverity.INFO
    event_type: AlertEventType = AlertEventType.SOIL_MOISTURE
    affected_zones: list[dict] = field(default_factory=list)
    target_audience: list[str] = field(default_factory=list)
    messages: dict[str, str] = field(default_factory=dict)
    recommended_actions: list[str] = field(default_factory=list)
    executive_summary: str = ""
    confidence_score: float = 0.0
    data_completeness: float = 0.0


@dataclass
class ScenarioProjection:
    """A risk scenario projection at a given horizon (PRD §6.3)."""

    horizon_days: int = 7
    scenario_type: str = "probable"
    risk_level: RiskLevel = RiskLevel.LOW
    probability_score: float = 0.0
    description: str = ""


@dataclass
class RiskOutput:
    """Consolidated output from the RiskOrchestrator (PRD §6.3)."""

    area: str = ""
    region_ids: list[int] = field(default_factory=list)
    timestamp: Optional[str] = None
    risk_level: RiskLevel = RiskLevel.LOW
    affected_zones: list[AffectedZone] = field(default_factory=list)
    probability_score: float = 0.0
    impact_severity: ImpactSeverity = ImpactSeverity.MINOR
    priority_zones: list[AffectedZone] = field(default_factory=list)
    scenario_projections: list[ScenarioProjection] = field(default_factory=list)
    confidence_score: float = 0.0
    data_completeness: float = 0.0
    natural_language_summary: str = ""
    subagent_outputs: list[dict] = field(default_factory=list)


@dataclass
class RiskClassificationOutput:
    """Structured output from RiskClassificationAgent (AGENT-RISK-CL-001)."""

    risk_level: RiskLevel = RiskLevel.LOW
    risk_score: float = 0.0
    contributing_factors: list[str] = field(default_factory=list)
    confidence_score: float = 0.0
    data_completeness: float = 0.0
    natural_language_output: str = ""


@dataclass
class TerritorialPrioritizationOutput:
    """Structured output from TerritorialPrioritizationAgent (AGENT-RISK-PR-001)."""

    priority_zones: list[AffectedZone] = field(default_factory=list)
    ranking: list[str] = field(default_factory=list)
    confidence_score: float = 0.0
    data_completeness: float = 0.0
    natural_language_output: str = ""


@dataclass
class PredictiveScenariosOutput:
    """Structured output from PredictiveScenariosAgent (AGENT-RISK-SC-001)."""

    scenarios: list[ScenarioProjection] = field(default_factory=list)
    confidence_score: float = 0.0
    data_completeness: float = 0.0
    natural_language_output: str = ""


@dataclass
class AgentExecutionRecord:
    """Persistence model for a single agent execution record.

    Stored in the agent_executions table (migration 005).

    Attributes:
        agent_code: Agent identifier (e.g. "AGENT-HYD-SM-001").
        orchestrator_area: Area that orchestrated this execution.
        workflow_id: Parent workflow run ID.
        context_payload: JSON context passed to the agent.
        structured_output: JSON structured output from the agent.
        natural_language_output: Template-based NL text.
        confidence_score: Execution confidence (0.0-1.0).
        data_completeness: Data completeness fraction (0.0-1.0).
        llm_model_used: LiteLLM model identifier (if LLM was used).
        started_at: ISO timestamp when execution started.
        finished_at: ISO timestamp when execution finished.
        error_message: Error text if execution failed (optional).
        status: Lifecycle status (pending, running, completed, failed).
        id: Database-assigned ID (None before insert).
        created_at: ISO timestamp of record creation.
    """

    agent_code: str = ""
    orchestrator_area: str = ""
    workflow_id: str = ""
    context_payload: Optional[dict] = None
    structured_output: Optional[dict] = None
    natural_language_output: Optional[str] = None
    confidence_score: float = 0.0
    data_completeness: float = 0.0
    llm_model_used: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error_message: Optional[str] = None
    status: AgentStatus = AgentStatus.PENDING
    id: Optional[int] = None
    created_at: Optional[str] = None
