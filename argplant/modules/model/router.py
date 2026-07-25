"""FastAPI router for model/prediction module.

POST /api/v1/predict — runs the rule engine on analysis data and returns
anomalies, risk assessment, yield prediction, economic impact, and recommendations.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from argplant.modules.analysis.orchestrator import AnalysisOrchestrator
from argplant.modules.analysis.models import AnalysisRequest
from argplant.modules.model.engine import RuleEngine
from argplant.modules.model.models import PredictRequest, PredictResponse

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
    orchestrator = AnalysisOrchestrator()
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

    return result
