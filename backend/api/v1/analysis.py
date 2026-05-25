"""Analysis API endpoints — agent execution results (read-only)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db_session
from backend.schemas.analysis import (
    AnalysisListResponse,
    AnalysisDetailResponse,
    AnalysisLatestResponse,
    AnalysisSummaryResponse,
)
from backend.services.analysis_service import (
    list_analysis,
    get_analysis_detail,
    get_latest_analysis,
    get_analysis_summary,
)

router = APIRouter(tags=["analysis"])


@router.get("/analysis/", response_model=AnalysisListResponse)
async def list_analysis_endpoint(
    area: str | None = Query(None, description="Filter by orchestrator area"),
    agent_code: str | None = Query(None, description="Filter by agent code"),
    status: str | None = Query(None, description="Filter by status"),
    date_from: str | None = Query(None, description="Start date (ISO format)"),
    date_to: str | None = Query(None, description="End date (ISO format)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db_session),
):
    """List agent executions with optional filters and pagination."""
    return await list_analysis(
        db,
        area=area,
        agent_code=agent_code,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )


@router.get("/analysis/latest/", response_model=AnalysisLatestResponse)
async def latest_analysis(
    area: str | None = Query(None, description="Filter by orchestrator area"),
    agent_code: str | None = Query(None, description="Filter by agent code"),
    db: AsyncSession = Depends(get_db_session),
):
    """Get the most recent completed agent execution."""
    result = await get_latest_analysis(db, area=area, agent_code=agent_code)
    if not result:
        raise HTTPException(status_code=404, detail="No completed executions found")
    return result


@router.get("/analysis/summary/", response_model=AnalysisSummaryResponse)
async def analysis_summary(
    area: str | None = Query(None, description="Filter by orchestrator area"),
    db: AsyncSession = Depends(get_db_session),
):
    """Get aggregated summary of the latest analysis."""
    result = await get_analysis_summary(db, area=area)
    if not result:
        raise HTTPException(status_code=404, detail="No analysis summary available")
    return result


@router.get("/analysis/{execution_id}", response_model=AnalysisDetailResponse)
async def analysis_detail(
    execution_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Get full detail for a single agent execution."""
    result = await get_analysis_detail(db, execution_id)
    if not result:
        raise HTTPException(status_code=404, detail="Execution not found")
    return result
