"""Geospatial tools for the AI ecosystem (Módulo 4).

Read-only wrappers over existing M3 repositories. These tools expose
geospatial data to AI agents WITHOUT modifying any M1-M3 state.

Tools:
- RegionQueryTool: wraps RegionRepository
- IndicatorLookupTool: wraps IndicatorRepository
- RiskAssessmentTool: wraps RiskAssessmentRepository
"""

import logging
from typing import Any

from src.geospatial.domain.interfaces import (
    IndicatorRepository,
    RegionRepository,
    RiskAssessmentRepository,
)

from src.ai.domain.interfaces import Tool
from src.ai.domain.models import ToolResult

logger = logging.getLogger(__name__)


class RegionQueryTool(Tool):
    """Read-only wrapper over RegionRepository.

    Allows agents to query region data by ID or find regions
    intersecting a geometry.
    """

    @property
    def name(self) -> str:
        """Tool identifier."""
        return "geospatial_query"

    def __init__(self, region_repo: RegionRepository):
        """Initialize the Region Query Tool.

        Args:
            region_repo: RegionRepository instance (from M3).
        """
        self._repo = region_repo

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a region query.

        Supported operations:
        - get_by_id: region_id (int) → single region
        - find_intersecting: wkt (str) → list of intersecting regions

        Args:
            **kwargs: Operation-specific parameters.

        Returns:
            ToolResult with region data or error.
        """
        try:
            if "region_id" in kwargs:
                region = self._repo.get_by_id(kwargs["region_id"])
                if region is None:
                    return ToolResult(
                        tool_name=self.name,
                        success=False,
                        error=f"Region {kwargs['region_id']} not found",
                    )
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    data=self._serialize_region(region),
                )

            if "wkt" in kwargs:
                regions = self._repo.find_intersecting_geometry(kwargs["wkt"])
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    data=[self._serialize_region(r) for r in regions],
                )

            return ToolResult(
                tool_name=self.name,
                success=False,
                error="Unknown operation. Use region_id or wkt parameter.",
            )

        except Exception as e:
            logger.error(f"RegionQueryTool failed: {e}")
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(e),
            )

    @staticmethod
    def _serialize_region(region: Any) -> dict:
        """Serialize a region object to a dict for AI consumption.

        Args:
            region: Region model from M3.

        Returns:
            Dict with relevant region fields.
        """
        return {
            "id": getattr(region, "id", None),
            "name": getattr(region, "name", ""),
            "region_type": getattr(region, "region_type", ""),
            "country": getattr(region, "country", ""),
            "province": getattr(region, "province", ""),
            "area_km2": getattr(region, "area_km2", None),
        }


class IndicatorLookupTool(Tool):
    """Read-only wrapper over IndicatorRepository.

    Allows agents to look up indicators by region.
    """

    @property
    def name(self) -> str:
        """Tool identifier."""
        return "indicator_lookup"

    def __init__(self, indicator_repo: IndicatorRepository):
        """Initialize the Indicator Lookup Tool.

        Args:
            indicator_repo: IndicatorRepository instance (from M3).
        """
        self._repo = indicator_repo

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute an indicator lookup.

        Supported operations:
        - find_by_region: region_id (int) → list of indicators

        Args:
            **kwargs: Operation-specific parameters.

        Returns:
            ToolResult with indicator data or error.
        """
        try:
            if "region_id" in kwargs:
                indicators = self._repo.find_by_region(kwargs["region_id"])
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    data=[self._serialize_indicator(i) for i in indicators],
                )

            return ToolResult(
                tool_name=self.name,
                success=False,
                error="Unknown operation. Use region_id parameter.",
            )

        except Exception as e:
            logger.error(f"IndicatorLookupTool failed: {e}")
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(e),
            )

    @staticmethod
    def _serialize_indicator(indicator: Any) -> dict:
        """Serialize an indicator to a dict for AI consumption.

        Args:
            indicator: Indicator model from M3.

        Returns:
            Dict with relevant indicator fields.
        """
        return {
            "id": getattr(indicator, "id", None),
            "region_id": getattr(indicator, "region_id", None),
            "indicator_code": getattr(indicator, "indicator_code", ""),
            "indicator_name": getattr(indicator, "indicator_name", ""),
            "value": getattr(indicator, "value", None),
            "unit": getattr(indicator, "unit", ""),
            "classification": getattr(indicator, "classification", ""),
            "confidence": getattr(indicator, "confidence", None),
            "temporal_start": getattr(indicator, "temporal_start", ""),
            "temporal_end": getattr(indicator, "temporal_end", ""),
        }


class RiskAssessmentTool(Tool):
    """Read-only wrapper over RiskAssessmentRepository.

    Allows agents to query risk assessments by region.
    """

    @property
    def name(self) -> str:
        """Tool identifier."""
        return "risk_assessment"

    def __init__(self, risk_repo: RiskAssessmentRepository):
        """Initialize the Risk Assessment Tool.

        Args:
            risk_repo: RiskAssessmentRepository instance (from M3).
        """
        self._repo = risk_repo

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a risk assessment query.

        Supported operations:
        - find_by_region: region_id (int), date_from, date_to → list of risks

        Args:
            **kwargs: Operation-specific parameters.

        Returns:
            ToolResult with risk assessment data or error.
        """
        try:
            if "region_id" in kwargs:
                risks = self._repo.find_by_region_and_date(
                    region_id=kwargs["region_id"],
                    date_from=kwargs.get("date_from"),
                    date_to=kwargs.get("date_to"),
                )
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    data=[self._serialize_risk(r) for r in risks],
                )

            return ToolResult(
                tool_name=self.name,
                success=False,
                error="Unknown operation. Use region_id parameter.",
            )

        except Exception as e:
            logger.error(f"RiskAssessmentTool failed: {e}")
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(e),
            )

    @staticmethod
    def _serialize_risk(risk: Any) -> dict:
        """Serialize a risk assessment to a dict for AI consumption.

        Args:
            risk: RiskAssessment model from M3.

        Returns:
            Dict with relevant risk fields.
        """
        return {
            "id": getattr(risk, "id", None),
            "region_id": getattr(risk, "region_id", None),
            "risk_type": getattr(risk, "risk_type", ""),
            "risk_level": getattr(risk, "risk_level", ""),
            "risk_score": getattr(risk, "risk_score", None),
            "confidence": getattr(risk, "confidence", None),
            "explanation": getattr(risk, "explanation", ""),
            "temporal_start": getattr(risk, "temporal_start", ""),
            "temporal_end": getattr(risk, "temporal_end", ""),
        }
