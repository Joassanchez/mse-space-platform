"""Context Engine implementation for the AI ecosystem.

Reads from existing M3 geospatial tables (processed_geospatial_layers, regions,
indicators, risk_assessments) via repository interfaces — read-only access.
Produces structured JSON context payloads with field selection, per-entity
limits, and staleness warnings.
"""

import json
from datetime import datetime, timezone
from typing import Any

from src.geospatial.domain.interfaces import (
    IndicatorRepository,
    ProcessedLayerRepository,
    RegionRepository,
    RiskAssessmentRepository,
)
from src.geospatial.domain.models import Indicator, ProcessedLayer, Region, RiskAssessment

from src.weather.domain.interfaces import WeatherSnapshotRepository

from src.ai.domain.errors import ContextError
from src.ai.domain.interfaces import ContextEngine


# Default per-entity limits for context summarization
DEFAULT_MAX_LAYERS = 5
DEFAULT_MAX_INDICATORS = 10
DEFAULT_MAX_RISKS = 5
DEFAULT_MAX_AGE_HOURS = 720  # 30 days

# Approximate tokens per JSON character (rough heuristic)
TOKENS_PER_CHAR = 0.25


class ContextEngineImpl(ContextEngine):
    """Concrete ContextEngine that reads M3 data via repositories.

    All repository reads are read-only — no modifications to M3 tables.
    Context output is a structured dict with field selection and limits.
    """

    def __init__(
        self,
        region_repo: RegionRepository,
        layer_repo: ProcessedLayerRepository,
        indicator_repo: IndicatorRepository,
        risk_repo: RiskAssessmentRepository,
        weather_repo: WeatherSnapshotRepository | None = None,
        max_layers: int = DEFAULT_MAX_LAYERS,
        max_indicators: int = DEFAULT_MAX_INDICATORS,
        max_risks: int = DEFAULT_MAX_RISKS,
    ):
        """Initialize the Context Engine with repository dependencies.

        Args:
            region_repo: Repository for reading region data.
            layer_repo: Repository for reading processed geospatial layers.
            indicator_repo: Repository for reading indicator data.
            risk_repo: Repository for reading risk assessments.
            weather_repo: Optional repository for weather snapshots (Módulo 6).
            max_layers: Maximum layers to include per region.
            max_indicators: Maximum indicators to include per region.
            max_risks: Maximum risk assessments to include per region.
        """
        self._region_repo = region_repo
        self._layer_repo = layer_repo
        self._indicator_repo = indicator_repo
        self._risk_repo = risk_repo
        self._weather_repo = weather_repo
        self._max_layers = max_layers
        self._max_indicators = max_indicators
        self._max_risks = max_risks

    def build_context(
        self,
        region_ids: list[int],
        indicator_codes: list[str] | None = None,
        max_age_hours: int | None = None,
    ) -> dict:
        """Build structured JSON context from M3 tables (read-only).

        Reads regions, processed layers, indicators, and risk assessments
        for the specified region IDs. Applies field selection to include
        only relevant data for AI consumption.

        Args:
            region_ids: List of region IDs to include in context.
            indicator_codes: Optional filter by indicator codes.
            max_age_hours: Optional staleness threshold. If latest data exceeds
                this age, stale_data warning is included.

        Returns:
            Structured dict with:
                - regions: List of region summaries
                - layers: List of processed layer summaries
                - indicators: List of indicator values
                - risk_assessments: List of active risk assessments
                - metadata: Context generation metadata
                - warnings: List of warnings (stale_data, truncated, etc.)
        """
        if not region_ids:
            raise ContextError("region_ids cannot be empty")

        regions_data = []
        layers_data = []
        indicators_data = []
        risks_data = []
        warnings: list[str] = []
        latest_date: datetime | None = None

        for region_id in region_ids:
            # Read region
            region = self._region_repo.get_by_id(region_id)
            if region is None:
                warnings.append(f"Region {region_id} not found — skipped")
                continue

            regions_data.append(self._summarize_region(region))

            # Read indicators for this region
            indicators = self._indicator_repo.find_by_region(region_id)
            if indicator_codes:
                indicators = [
                    i for i in indicators if i.indicator_code in indicator_codes
                ]
            indicators_data.extend(
                [self._summarize_indicator(i) for i in indicators[: self._max_indicators]]
            )

            # Read risk assessments for this region
            risks = self._risk_repo.find_by_region_and_date(region_id)
            risks_data.extend(
                [self._summarize_risk(r) for r in risks[: self._max_risks]]
            )

            # Track latest date for staleness check
            region_latest = self._get_latest_date(region, indicators, risks)
            if region_latest and (latest_date is None or region_latest > latest_date):
                latest_date = region_latest

        # Check for stale data
        max_age = max_age_hours if max_age_hours is not None else DEFAULT_MAX_AGE_HOURS
        if latest_date:
            age_hours = (datetime.now(timezone.utc) - latest_date).total_seconds() / 3600
            if age_hours > max_age:
                warnings.append(
                    f"stale_data: true — latest data is {age_hours:.0f} hours old "
                    f"(threshold: {max_age} hours)"
                )

        metadata = {
            "entity_counts": {
                "regions": len(regions_data),
                "layers": len(layers_data),
                "indicators": len(indicators_data),
                "risk_assessments": len(risks_data),
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        return {
            "regions": regions_data,
            "layers": layers_data,
            "indicators": indicators_data,
            "risk_assessments": risks_data,
            "metadata": metadata,
            "warnings": warnings,
        }

    def summarize_context(self, context: dict, max_tokens: int) -> dict:
        """Summarize context to fit token window.

        Uses field selection and per-entity limits rather than raw truncation.
        Includes metadata about what was reduced.

        Args:
            context: Full context dict from build_context().
            max_tokens: Maximum token budget for the summarized output.

        Returns:
            Summarized context dict with truncated flag if data was reduced.
        """
        # Estimate current token count
        context_json = json.dumps(context)
        estimated_tokens = int(len(context_json) * TOKENS_PER_CHAR)

        if estimated_tokens <= max_tokens:
            return {**context, "truncated": False}

        summarized: dict[str, Any] = {
            "truncated": True,
            "warnings": list(context.get("warnings", [])),
        }

        # Keep metadata
        summarized["metadata"] = context.get("metadata", {})

        # Summarize regions (keep essential fields only)
        regions = context.get("regions", [])
        summarized["regions"] = [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "country": r.get("country"),
                "region_type": r.get("region_type"),
            }
            for r in regions
        ]

        # Limit and summarize indicators
        indicators = context.get("indicators", [])
        max_ind = max(1, len(indicators) // 2)
        summarized["indicators"] = indicators[:max_ind]
        if len(indicators) > max_ind:
            summarized["warnings"].append(
                f"indicators truncated: {len(indicators)} -> {max_ind}"
            )

        # Limit and summarize risk assessments
        risks = context.get("risk_assessments", [])
        max_risk = max(1, len(risks) // 2)
        summarized["risk_assessments"] = risks[:max_risk]
        if len(risks) > max_risk:
            summarized["warnings"].append(
                f"risk_assessments truncated: {len(risks)} -> {max_risk}"
            )

        # Layers are not included in build_context output (read-only summary),
        # but if present, limit them too
        layers = context.get("layers", [])
        if layers:
            max_layer = max(1, len(layers) // 2)
            summarized["layers"] = layers[:max_layer]

        return summarized

    # ============================================================
    # Enriched Context (Módulo 6 — Data Connectors)
    # ============================================================

    def build_enriched_context(
        self,
        region_ids: list[int],
        indicator_codes: list[str] | None = None,
        max_age_hours: int | None = None,
        include_weather: bool = True,
        include_socioeconomic: bool = True,
    ) -> dict:
        """Build enriched context with weather and socioeconomic data.

        Extends build_context() with optional weather snapshots and
        socioeconomic demo/reference indicators. All data is read-only
        via repository interfaces.

        Args:
            region_ids: Regions to include.
            indicator_codes: Optional filter for indicators.
            max_age_hours: Optional staleness threshold.
            include_weather: If True, attach latest weather per region.
            include_socioeconomic: If True, attach ECO_* indicators.

        Returns:
            Enriched context dict with optional "weather" and
            "socioeconomic" keys alongside standard context fields.
        """
        ctx = self.build_context(region_ids, indicator_codes, max_age_hours)

        # Attach weather data per region
        if include_weather and self._weather_repo:
            weather_data = []
            for rid in region_ids:
                snap = self._weather_repo.find_latest_by_region(rid)
                if snap:
                    weather_data.append({
                        "region_id": snap.region_id,
                        "observed_at": snap.observed_at,
                        "temp_celsius": snap.temp_celsius,
                        "humidity_pct": snap.humidity_pct,
                        "wind_speed_ms": snap.wind_speed_ms,
                        "rainfall_mm": snap.rainfall_mm,
                        "pressure_hpa": snap.pressure_hpa,
                        "condition": snap.weather_condition,
                        "source": snap.source,
                    })
            ctx["weather"] = weather_data
            if not weather_data:
                ctx.setdefault("warnings", []).append(
                    "weather_data: no snapshots found for requested regions"
                )

        # Attach socioeconomic demo/reference indicators
        if include_socioeconomic:
            eco_codes = {
                "ECO_CROP_YIELD", "ECO_AFFECTED_AREA", "ECO_ESTIMATED_LOSS",
                "ECO_COMMODITY_PRICE", "ECO_POP_DENSITY",
            }
            all_indicators = ctx.get("indicators", [])
            socioeconomic = [
                ind for ind in all_indicators
                if ind.get("indicator_code", "").upper() in eco_codes
            ]
            if socioeconomic:
                ctx["socioeconomic"] = socioeconomic
                ctx.setdefault("warnings", []).append(
                    "socioeconomic_data: includes DEMO/reference indicators — "
                    "not actual INDEC data"
                )

        return ctx

    # ============================================================
    # Private helpers
    # ============================================================

    def _summarize_region(self, region: Region) -> dict:
        """Extract relevant fields from a region for context.

        Includes metadata JSONB for territorial variables (land_use,
        population_density, critical_infrastructure) consumed by
        the Risk Orchestrator (§6).
        """
        return {
            "id": region.id,
            "name": region.name,
            "region_type": region.region_type,
            "country": region.country,
            "province": region.province,
            "bbox": region.bbox,
            "area_km2": region.area_km2,
            "metadata": region.metadata,
        }

    def _summarize_indicator(self, indicator: Indicator) -> dict:
        """Extract relevant fields from an indicator for context."""
        return {
            "id": indicator.id,
            "region_id": indicator.region_id,
            "indicator_code": indicator.indicator_code,
            "indicator_name": indicator.indicator_name,
            "value": indicator.value,
            "unit": indicator.unit,
            "classification": indicator.classification,
            "confidence": indicator.confidence,
            "temporal_start": indicator.temporal_start,
            "temporal_end": indicator.temporal_end,
        }

    def _summarize_risk(self, risk: RiskAssessment) -> dict:
        """Extract relevant fields from a risk assessment for context."""
        return {
            "id": risk.id,
            "region_id": risk.region_id,
            "risk_type": risk.risk_type,
            "risk_level": risk.risk_level,
            "risk_score": risk.risk_score,
            "confidence": risk.confidence,
            "explanation": risk.explanation,
            "temporal_start": risk.temporal_start,
            "temporal_end": risk.temporal_end,
        }

    def _get_latest_date(
        self,
        region: Region,
        indicators: list[Indicator],
        risks: list[RiskAssessment],
    ) -> datetime | None:
        """Find the latest date across region data for staleness check.

        All parsed datetimes are normalized to timezone-aware (UTC) to allow
        safe comparison with ``datetime.now(timezone.utc)``.
        """
        dates: list[datetime] = []

        for indicator in indicators:
            if indicator.temporal_end:
                try:
                    dt = datetime.fromisoformat(indicator.temporal_end)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    dates.append(dt)
                except (ValueError, TypeError):
                    pass

        for risk in risks:
            if risk.temporal_end:
                try:
                    dt = datetime.fromisoformat(risk.temporal_end)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    dates.append(dt)
                except (ValueError, TypeError):
                    pass

        if region.updated_at:
            try:
                dt = datetime.fromisoformat(region.updated_at)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                dates.append(dt)
            except (ValueError, TypeError):
                pass

        return max(dates) if dates else None
