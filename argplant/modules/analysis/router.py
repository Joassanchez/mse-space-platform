"""FastAPI router for the analysis orchestrator module.

Exposes a unified endpoint that aggregates data from agroclimate, satellite,
agronomy, and economy modules into a single response. Results are cached in
Redis (TTL 30 min).
"""

import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response

from argplant.modules.analysis.models import AnalysisResponse
from argplant.modules.analysis.orchestrator import AnalysisOrchestrator
from argplant.shared.cache import _get_redis, get_json, set_json

logger = logging.getLogger("argplant.analysis")

router = APIRouter(tags=["analysis"])

# Cache TTL for full analysis responses
ANALYSIS_CACHE_TTL = 1800  # 30 minutes


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _analysis_cache_key(lot_id: str, crop: str, query_date: date) -> str:
    return f"analysis:{lot_id}:{crop}:{query_date.isoformat()}"


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


async def _get_orchestrator() -> AnalysisOrchestrator:
    redis = await _get_redis()
    return AnalysisOrchestrator(redis)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/analysis", response_model=AnalysisResponse)
async def get_analysis(
    response: Response,
    lot_id: str = Query(..., description="Lot identifier (e.g. lote-123)"),
    crop: str = Query(..., description="Crop ID: 'soy' or 'corn'"),
    lat: float = Query(..., description="Latitude", ge=-90, le=90),
    lon: float = Query(..., description="Longitude", ge=-180, le=180),
    date: date = Query(..., description="Query date (YYYY-MM-DD)"),
) -> AnalysisResponse:
    """Return a unified analysis with agroclimate, satellite, agronomy, and economy data.

    Results are cached in Redis for 30 minutes. The X-Cache header indicates
    whether the response was served from cache (HIT) or freshly computed (MISS).
    When one or more modules fail, X-Partial: true is added and the meta.status
    field is set to "partial" with the list of missing modules.
    """
    # Validate crop
    crop_lower = crop.lower()
    if crop_lower not in ("soy", "corn"):
        raise HTTPException(
            status_code=400,
            detail="crop must be 'soy' or 'corn'",
        )

    cache_key = _analysis_cache_key(lot_id, crop_lower, date)
    redis = await _get_redis()

    # 1. Try cache hit
    cached = await get_json(redis, cache_key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        cached_response = AnalysisResponse(**cached)
        if cached_response.meta.status == "partial":
            response.headers["X-Partial"] = "true"
        return cached_response

    # 2. Cache miss — compute fresh
    orchestrator = await _get_orchestrator()
    try:
        result = await orchestrator.gather(lot_id, crop_lower, lat, lon, date)
    except Exception as exc:
        logger.exception("Analysis gather failed for lot=%s crop=%s date=%s", lot_id, crop_lower, date)
        raise HTTPException(
            status_code=502,
            detail=f"Analysis pipeline failed: {exc}",
        ) from exc

    # Mark cached_at timestamp
    result.meta.cached_at = datetime.now(timezone.utc)

    # Generate cacheable dict
    result_dict = result.model_dump(mode="json")

    # 3. Store in cache
    await set_json(redis, cache_key, result_dict, ttl=ANALYSIS_CACHE_TTL)

    # 4. Set response headers
    response.headers["X-Cache"] = "MISS"
    if result.meta.status == "partial":
        response.headers["X-Partial"] = "true"

    return result
