"""FastAPI router for model/prediction module.

POST /api/v1/predict — runs the rule engine on analysis data and returns
anomalies, risk assessment, yield prediction, economic impact, and recommendations.
"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException

from argplant.modules.analysis.orchestrator import AnalysisOrchestrator
from argplant.modules.analysis.models import AnalysisRequest
from argplant.modules.communication.models import AlertCreate
from argplant.modules.communication.service import AlertService
from argplant.modules.model.engine import RuleEngine
from argplant.modules.model.models import PredictRequest, PredictResponse
from argplant.shared.cache import _get_redis
from argplant.shared.config import settings
from argplant.shared.database import async_session
from argplant.shared.llm import get_llm_client

logger = logging.getLogger("argplant.model")

router = APIRouter(tags=["model"])

_engine = RuleEngine()


@router.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest) -> PredictResponse:
    """Run prediction on a lot/crop/date combination.

    Internally calls the analysis orchestrator to gather raw data, then
    applies the agronomic rule engine to detect anomalies and generate
    actionable recommendations.

    Returns 502 if the analysis orchestrator fails to gather data.
    """
    # 1. Gather raw data via the analysis orchestrator
    redis = await _get_redis()
    orchestrator = AnalysisOrchestrator(redis=redis)
    analysis_req = AnalysisRequest(
        lot_id=request.lot_id,
        crop=request.crop,
        lat=request.lat,
        lon=request.lon,
        date=request.date,
    )

    try:
        raw = await orchestrator.gather(
            lot_id=analysis_req.lot_id,
            crop=analysis_req.crop,
            lat=analysis_req.lat,
            lon=analysis_req.lon,
            query_date=analysis_req.date,
        )
        analysis_data = raw.model_dump(mode="json")
    except Exception as exc:
        logger.exception("Analysis orchestrator failed during prediction")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to gather analysis data: {exc}",
        ) from exc

    # 2. Run the rule engine
    try:
        result = _engine.evaluate(request, analysis_data)
    except Exception as exc:
        logger.exception("Rule engine evaluation failed")
        raise HTTPException(
            status_code=500,
            detail=f"Prediction engine error: {exc}",
        ) from exc

    # 3. Auto-generate alerts from anomalies (async fire-and-forget)
    llm_client = None
    try:
        llm_client = get_llm_client()
    except Exception:
        pass  # LLM not configured — alerts use raw messages

    for anomaly in result.anomalies:
        if anomaly.severity in ("critical", "high"):
            try:
                async with async_session() as session:
                    svc = AlertService(session, llm_client=llm_client)
                    region_id = hash(request.lot_id) % 10000  # map lot_id to int
                    await svc.create(AlertCreate(
                        region_id=region_id,
                        alert_type=anomaly.type,
                        severity=anomaly.severity,
                        title=f"{anomaly.type.replace('_', ' ').title()} — {request.lot_id}",
                        message=anomaly.description,
                        status="active",
                        metadata_=anomaly.evidence,
                    ))
                    await session.commit()
            except Exception:
                logger.exception("Failed to auto-create alert for lot %s", request.lot_id)

    return result
