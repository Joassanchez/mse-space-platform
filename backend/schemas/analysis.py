"""Pydantic schemas for analysis/agent execution endpoints."""

from datetime import datetime

from pydantic import BaseModel


class AnalysisSummary(BaseModel):
    """Summary view of a single agent execution (list items)."""

    execution_id: str
    orchestrator_area: str | None = None
    agent_code: str | None = None
    workflow_id: str | None = None
    status: str | None = None
    structured_output: dict | None = None
    natural_language_output: str | None = None
    confidence_score: float | None = None
    data_completeness: float | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None


class AnalysisListResponse(BaseModel):
    """Paginated list of analysis executions."""

    items: list[AnalysisSummary]
    total: int
    page: int
    limit: int


class AnalysisDetailResponse(BaseModel):
    """Full detail of a single agent execution."""

    execution_id: str
    orchestrator_area: str | None = None
    agent_code: str | None = None
    workflow_id: str | None = None
    status: str | None = None
    structured_output: dict = {}
    natural_language_output: str | None = None
    confidence_score: float | None = None
    data_completeness: float | None = None
    llm_model_used: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime | None = None


class AnalysisLatestResponse(BaseModel):
    """Most recent completed execution for an area/agent."""

    execution_id: str
    orchestrator_area: str | None = None
    agent_code: str | None = None
    workflow_id: str | None = None
    status: str | None = None
    structured_output: dict | None = None
    natural_language_output: str | None = None
    confidence_score: float | None = None
    data_completeness: float | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None


class AnalysisSummaryResponse(BaseModel):
    """Aggregated summary of latest analysis."""

    orchestrator_area: str | None = None
    overall_condition: str = "unknown"
    confidence_score: float = 0.0
    summary: str | None = None
    finished_at: datetime | None = None
