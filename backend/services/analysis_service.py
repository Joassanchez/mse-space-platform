"""Analysis service — queries agent_executions table for agent run results."""

from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import AgentExecution
from backend.schemas.analysis import (
    AnalysisSummary,
    AnalysisListResponse,
    AnalysisDetailResponse,
    AnalysisLatestResponse,
    AnalysisSummaryResponse,
)


async def list_analysis(
    db: AsyncSession,
    area: str | None = None,
    agent_code: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> AnalysisListResponse:
    """List agent executions with optional filters and pagination."""
    query = select(AgentExecution)

    if area:
        query = query.where(AgentExecution.orchestrator_area == area)
    if agent_code:
        query = query.where(AgentExecution.agent_code == agent_code)
    if status:
        query = query.where(AgentExecution.status == status)
    if date_from:
        query = query.where(AgentExecution.finished_at >= date_from)
    if date_to:
        query = query.where(AgentExecution.finished_at <= date_to)

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginated results
    offset = (page - 1) * limit
    ordered = query.order_by(desc(AgentExecution.finished_at)).offset(offset).limit(limit)
    rows = (await db.execute(ordered)).scalars().all()

    items = [
        AnalysisSummary(
            execution_id=str(e.id),
            orchestrator_area=e.orchestrator_area,
            agent_code=e.agent_code,
            workflow_id=e.workflow_id,
            status=e.status,
            structured_output=e.structured_output,
            natural_language_output=e.natural_language_output,
            confidence_score=float(e.confidence_score) if e.confidence_score else None,
            data_completeness=float(e.data_completeness) if e.data_completeness else None,
            started_at=e.started_at,
            finished_at=e.finished_at,
            created_at=e.created_at,
        )
        for e in rows
    ]

    return AnalysisListResponse(items=items, total=total, page=page, limit=limit)


async def get_analysis_detail(
    db: AsyncSession,
    execution_id: str,
) -> AnalysisDetailResponse | None:
    """Get full detail for a single agent execution."""
    result = await db.execute(
        select(AgentExecution).where(AgentExecution.id == execution_id)
    )
    execution = result.scalar_one_or_none()
    if not execution:
        return None

    return AnalysisDetailResponse(
        execution_id=str(execution.id),
        orchestrator_area=execution.orchestrator_area,
        agent_code=execution.agent_code,
        workflow_id=execution.workflow_id,
        status=execution.status,
        structured_output=execution.structured_output or {},
        natural_language_output=execution.natural_language_output,
        confidence_score=float(execution.confidence_score) if execution.confidence_score else None,
        data_completeness=float(execution.data_completeness) if execution.data_completeness else None,
        llm_model_used=execution.llm_model_used,
        started_at=execution.started_at,
        finished_at=execution.finished_at,
        error_message=execution.error_message,
        created_at=execution.created_at,
    )


async def get_latest_analysis(
    db: AsyncSession,
    area: str | None = None,
    agent_code: str | None = None,
) -> AnalysisLatestResponse | None:
    """Get the most recent completed agent execution."""
    query = (
        select(AgentExecution)
        .where(AgentExecution.status == "completed")
        .order_by(desc(AgentExecution.finished_at))
        .limit(1)
    )
    if area:
        query = query.where(AgentExecution.orchestrator_area == area)
    if agent_code:
        query = query.where(AgentExecution.agent_code == agent_code)

    result = await db.execute(query)
    execution = result.scalar_one_or_none()
    if not execution:
        return None

    return AnalysisLatestResponse(
        execution_id=str(execution.id),
        orchestrator_area=execution.orchestrator_area,
        agent_code=execution.agent_code,
        workflow_id=execution.workflow_id,
        status=execution.status,
        structured_output=execution.structured_output,
        natural_language_output=execution.natural_language_output,
        confidence_score=float(execution.confidence_score) if execution.confidence_score else None,
        data_completeness=float(execution.data_completeness) if execution.data_completeness else None,
        finished_at=execution.finished_at,
        created_at=execution.created_at,
    )


async def get_analysis_summary(
    db: AsyncSession,
    area: str | None = None,
) -> AnalysisSummaryResponse | None:
    """Get a summary of the latest completed analysis."""
    result = await db.execute(
        select(AgentExecution)
        .where(AgentExecution.status == "completed")
        .order_by(desc(AgentExecution.finished_at))
        .limit(1)
    )
    execution = result.scalar_one_or_none()
    if not execution:
        return None

    structured = execution.structured_output or {}
    return AnalysisSummaryResponse(
        orchestrator_area=execution.orchestrator_area,
        overall_condition=structured.get("overall_condition", "unknown"),
        confidence_score=float(execution.confidence_score) if execution.confidence_score else 0.0,
        summary=execution.natural_language_output,
        finished_at=execution.finished_at,
    )
