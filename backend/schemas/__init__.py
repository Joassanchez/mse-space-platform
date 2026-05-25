"""Re-export all Pydantic schemas for convenient imports."""

from backend.schemas.analysis import (
    AnalysisSummary,
    AnalysisListResponse,
    AnalysisDetailResponse,
    AnalysisLatestResponse,
    AnalysisSummaryResponse,
)
from backend.schemas.regions import (
    RegionListItem,
    RegionDetail,
    RegionListResponse,
)
from backend.schemas.geo import GeoJSONFeature, GeoJSONFeatureCollection
from backend.schemas.alerts import (
    AlertItem,
    AlertListResponse,
    AlertDetailResponse,
    ActiveAlertCountResponse,
)
from backend.schemas.jobs import (
    JobItem,
    JobListResponse,
    JobDetailResponse,
    JobTriggerRequest,
    JobTriggerResponse,
)

__all__ = [
    "AnalysisSummary",
    "AnalysisListResponse",
    "AnalysisDetailResponse",
    "AnalysisLatestResponse",
    "AnalysisSummaryResponse",
    "RegionListItem",
    "RegionDetail",
    "RegionListResponse",
    "GeoJSONFeature",
    "GeoJSONFeatureCollection",
    "AlertItem",
    "AlertListResponse",
    "AlertDetailResponse",
    "ActiveAlertCountResponse",
    "JobItem",
    "JobListResponse",
    "JobDetailResponse",
    "JobTriggerRequest",
    "JobTriggerResponse",
]
