"""SoilMoistureAgent — AGENT-HYD-SM-001.

Stateless agent that analyzes soil moisture from SMAP satellite data.
Receives structured context from ContextEngine, extracts surface and
rootzone moisture indicators, classifies status with thresholds,
calculates confidence and data completeness, and produces a template-based
natural language summary. No LLM calls.
"""

from typing import Any

from src.ai.agents.soil_moisture.prompts.templates import (
    NL_TEMPLATE,
    RECOMMENDATIONS,
    UNAVAILABLE_MSG,
)
from src.ai.agents.soil_moisture.schemas import SoilMoistureOutputSchema
from src.ai.domain.models import SoilMoistureStatus


# Expected indicator codes for soil moisture analysis
_SM_CODES = {"SM_INDEX", "SM_SURFACE", "SM_ROOTZONE", "SOIL_MOISTURE"}

# Surface moisture thresholds (m3/m3, 0-5cm typical range)
_SURFACE_THRESHOLDS = [
    (0.15, SoilMoistureStatus.CRITICAL_DRY),
    (0.25, SoilMoistureStatus.DRY),
    (0.35, SoilMoistureStatus.NORMAL),
    (0.45, SoilMoistureStatus.WET),
]  # >= 0.45 → CRITICAL_WET

# Rootzone moisture thresholds (scaled for deeper soil)
_ROOTZONE_THRESHOLDS = [
    (0.20, SoilMoistureStatus.CRITICAL_DRY),
    (0.30, SoilMoistureStatus.DRY),
    (0.45, SoilMoistureStatus.NORMAL),
    (0.55, SoilMoistureStatus.WET),
]  # >= 0.55 → CRITICAL_WET

# Confidence weights
_W_DATA_COMPLETENESS = 0.3
_W_FRESHNESS = 0.3
_W_INDICATOR_QUALITY = 0.2
_W_INDICATOR_CONFIDENCE = 0.2


class SoilMoistureAgent:
    """Stateless soil moisture analysis agent.

    Receives structured context from ContextEngine and produces
    SoilMoistureOutput with surface/rootzone moisture values, status
    classifications, confidence scores, and a template-based NL summary.
    """

    def __init__(self) -> None:
        """Initialize the agent with no state beyond its name."""
        self.name = "soil-moisture"

    def execute(self, context: dict, **kwargs: Any) -> dict:
        """Execute soil moisture analysis.

        Args:
            context: Structured context from ContextEngine containing
                indicators, warnings, regions, etc.
            **kwargs: Additional runtime parameters (ignored).

        Returns:
            Dict matching SoilMoistureOutput schema with all required fields.
        """
        indicators = context.get("indicators", [])
        warnings = context.get("warnings", [])

        # Extract moisture values from indicators
        surface_value, rootzone_value = self._extract_moisture_values(indicators)

        # Classify status
        surface_status = self._classify_surface(surface_value)
        rootzone_status = self._classify_rootzone(rootzone_value)

        # Calculate data completeness
        found_codes = self._get_found_codes(indicators)
        data_completeness = self._calc_data_completeness(found_codes)

        # Calculate confidence
        confidence = self._calc_confidence(
            data_completeness, warnings, indicators, found_codes
        )

        # Determine trend and anomaly (derived from available data)
        trend_7d = self._determine_trend(indicators)
        anomaly_pct = self._calc_anomaly(surface_value, rootzone_value)

        # Generate natural language output + recommendation
        natural_language = self._generate_nl_output(
            surface_value,
            rootzone_value,
            surface_status,
            rootzone_status,
            trend_7d,
            confidence,
        )

        # Build raw output dict
        raw_output = {
            "surface_moisture": surface_value,
            "rootzone_moisture": rootzone_value,
            "sm_surface_status": surface_status.value,
            "sm_rootzone_status": rootzone_status.value,
            "trend_7d": trend_7d,
            "anomaly_pct": anomaly_pct,
            "confidence_score": round(confidence, 4),
            "data_completeness": round(data_completeness, 4),
            "natural_language_output": natural_language,
        }

        # Validate against Pydantic schema before returning (§9.3, §13.1.6)
        return SoilMoistureOutputSchema(**raw_output).model_dump()

    # ============================================================
    # Extraction
    # ============================================================

    def _extract_moisture_values(
        self, indicators: list[dict]
    ) -> tuple[float | None, float | None]:
        """Extract surface and rootzone moisture values from indicators.

        Searches for indicators with SM-related codes. Surface value comes
        from SM_SURFACE or SOIL_MOISTURE; rootzone from SM_ROOTZONE.
        SM_INDEX is used as a fallback for surface if no specific code found.

        Returns:
            Tuple of (surface_moisture, rootzone_moisture), each may be None.
        """
        surface_value: float | None = None
        rootzone_value: float | None = None
        fallback_value: float | None = None

        for ind in indicators:
            code = ind.get("indicator_code", "").upper()
            if code not in _SM_CODES:
                continue

            value = ind.get("value")
            if value is None:
                continue

            if code == "SM_SURFACE":
                surface_value = float(value)
            elif code == "SM_ROOTZONE":
                rootzone_value = float(value)
            elif code == "SOIL_MOISTURE":
                # Generic code — treat as surface
                if surface_value is None:
                    surface_value = float(value)
            elif code == "SM_INDEX":
                # Index — use as fallback for surface
                if surface_value is None:
                    fallback_value = float(value)

        # Use fallback if no explicit surface value found
        if surface_value is None and fallback_value is not None:
            surface_value = fallback_value

        return surface_value, rootzone_value

    def _get_found_codes(self, indicators: list[dict]) -> set[str]:
        """Return set of SM-related indicator codes found in context."""
        found: set[str] = set()
        for ind in indicators:
            code = ind.get("indicator_code", "").upper()
            if code in _SM_CODES:
                found.add(code)
        return found

    # ============================================================
    # Classification
    # ============================================================

    def _classify_surface(self, value: float | None) -> SoilMoistureStatus:
        """Classify surface moisture status using thresholds."""
        if value is None:
            return SoilMoistureStatus.UNAVAILABLE

        for threshold, status in _SURFACE_THRESHOLDS:
            if value < threshold:
                return status

        return SoilMoistureStatus.CRITICAL_WET

    def _classify_rootzone(self, value: float | None) -> SoilMoistureStatus:
        """Classify rootzone moisture status using thresholds."""
        if value is None:
            return SoilMoistureStatus.UNAVAILABLE

        for threshold, status in _ROOTZONE_THRESHOLDS:
            if value < threshold:
                return status

        return SoilMoistureStatus.CRITICAL_WET

    # ============================================================
    # Confidence & Completeness
    # ============================================================

    def _calc_data_completeness(self, found_codes: set[str]) -> float:
        """Calculate data completeness as found_indicators / expected_indicators.

        Expected indicators: SM_SURFACE and SM_ROOTZONE (2 total).
        SM_INDEX and SOIL_MOISTURE count as partial (surface-level only).
        """
        if not found_codes:
            return 0.0

        # Count how many of the two primary indicators we have
        has_surface = bool(
            found_codes & {"SM_SURFACE", "SOIL_MOISTURE", "SM_INDEX"}
        )
        has_rootzone = bool(found_codes & {"SM_ROOTZONE"})

        score = 0.0
        if has_surface:
            score += 0.5
        if has_rootzone:
            score += 0.5

        return score

    def _calc_confidence(
        self,
        data_completeness: float,
        warnings: list[str],
        indicators: list[dict],
        found_codes: set[str],
    ) -> float:
        """Calculate confidence as weighted combo of four factors.

        Weights:
        - data_completeness: 0.3
        - freshness: 0.3 (penalized if stale_data warning present)
        - indicator_quality: 0.2 (from classification field)
        - indicator_confidence: 0.2 (from confidence field)
        """
        if data_completeness == 0.0:
            return 0.0

        # Freshness: check for stale_data warning
        freshness = 1.0
        for warning in warnings:
            if "stale_data" in warning.lower():
                freshness = 0.5  # penalty for stale data
                break

        # Indicator quality: average of classification-based quality scores
        quality_scores = []
        for ind in indicators:
            code = ind.get("indicator_code", "").upper()
            if code not in _SM_CODES:
                continue
            classification = ind.get("classification", "").lower()
            # Map classification to a quality score
            quality_map = {
                "high": 1.0,
                "good": 0.9,
                "adequate": 0.7,
                "moderate": 0.6,
                "low": 0.4,
                "poor": 0.2,
            }
            quality_scores.append(quality_map.get(classification, 0.5))

        indicator_quality = (
            sum(quality_scores) / len(quality_scores) if quality_scores else 0.5
        )

        # Indicator confidence: average of confidence fields
        conf_scores = []
        for ind in indicators:
            code = ind.get("indicator_code", "").upper()
            if code not in _SM_CODES:
                continue
            conf = ind.get("confidence")
            if conf is not None:
                conf_scores.append(float(conf))

        indicator_confidence = (
            sum(conf_scores) / len(conf_scores) if conf_scores else 0.5
        )

        # Weighted combination
        confidence = (
            _W_DATA_COMPLETENESS * data_completeness
            + _W_FRESHNESS * freshness
            + _W_INDICATOR_QUALITY * indicator_quality
            + _W_INDICATOR_CONFIDENCE * indicator_confidence
        )

        return max(0.0, min(1.0, confidence))

    # ============================================================
    # Trend & Anomaly
    # ============================================================

    def _determine_trend(self, indicators: list[dict]) -> str:
        """Determine 7-day trend from indicator metadata.

        Uses temporal_end vs temporal_start to infer direction if
        multiple readings exist. Defaults to "stable" for MVP.
        """
        # For MVP: check if any indicator has trend metadata
        for ind in indicators:
            code = ind.get("indicator_code", "").upper()
            if code not in _SM_CODES:
                continue
            # Check for explicit trend field (future extension)
            trend = ind.get("trend")
            if trend:
                return str(trend).lower()

        # Default: stable (no trend data available in MVP)
        return "stable"

    def _calc_anomaly(
        self, surface: float | None, rootzone: float | None
    ) -> float | None:
        """Calculate anomaly percentage from moisture values.

        Uses a simple heuristic: deviation from the NORMAL midpoint.
        Surface normal midpoint ≈ 0.30, rootzone ≈ 0.375.
        Returns None if no data available.
        """
        if surface is None and rootzone is None:
            return None

        # Use surface as primary, rootzone as secondary
        primary = surface if surface is not None else rootzone
        if primary is None:
            return None

        # Normal midpoint reference
        normal_midpoint = 0.30
        anomaly = ((primary - normal_midpoint) / normal_midpoint) * 100

        return round(anomaly, 2)

    # ============================================================
    # Natural Language Output
    # ============================================================

    def _generate_nl_output(
        self,
        surface: float | None,
        rootzone: float | None,
        surface_status: SoilMoistureStatus,
        rootzone_status: SoilMoistureStatus,
        trend: str,
        confidence: float,
    ) -> str:
        """Generate template-based natural language summary with recommendation.

        Templates loaded from prompts/templates.py (PRD §4.2 plugin structure).
        Deterministic — no LLM calls.
        """
        if surface_status == SoilMoistureStatus.UNAVAILABLE and rootzone_status == SoilMoistureStatus.UNAVAILABLE:
            return UNAVAILABLE_MSG

        surface_str = f"{surface:.2f}" if surface is not None else "N/A"
        rootzone_str = f"{rootzone:.2f}" if rootzone is not None else "N/A"

        # Worst status drives recommendation (PRD §5.4.1)
        worst = surface_status if surface_status.value > rootzone_status.value else rootzone_status
        recommendation = RECOMMENDATIONS.get(worst, "")

        return NL_TEMPLATE.format(
            status=surface_status.value,
            surface=surface_str,
            surface_status=surface_status.value,
            rootzone=rootzone_str,
            rootzone_status=rootzone_status.value,
            trend=trend,
            confidence=confidence,
            recommendation=recommendation,
        )
