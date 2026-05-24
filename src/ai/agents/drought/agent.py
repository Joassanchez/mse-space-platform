"""DroughtAgent — AGENT-HYD-DR-001.

Stateless agent that analyzes drought conditions using SPI (Standardized
Precipitation Index) indicators and soil moisture data. Receives structured
context from ContextEngine, extracts SPI values, classifies drought severity,
incorporates soil moisture for signal escalation, calculates confidence and
data completeness, and produces a template-based natural language summary.
No LLM calls.
"""

from typing import Any

from src.ai.agents.drought.prompts.templates import (
    NL_TEMPLATE,
    PROJECTIONS,
    UNAVAILABLE_MSG,
)
from src.ai.agents.drought.schemas import DroughtOutputSchema
from src.ai.domain.models import DroughtCategory, DroughtSignal, SoilMoistureStatus, SpiStatus


# Expected indicator codes for drought analysis
_DROUGHT_CODES = {"SPI_30D", "SPI_90D"}

# Soil moisture codes that affect drought classification
_SM_DROUGHT_CODES = {"SM_SURFACE", "SM_ROOTZONE", "SM_INDEX", "SOIL_MOISTURE"}

# Confidence weights (same pattern as other agents)
_W_DATA_COMPLETENESS = 0.3
_W_FRESHNESS = 0.3
_W_INDICATOR_QUALITY = 0.2
_W_INDICATOR_CONFIDENCE = 0.2


class DroughtAgent:
    """Stateless drought analysis agent.

    Receives structured context from ContextEngine and produces
    DroughtOutput with SPI values, drought category/signal, trend,
    confidence scores, and a template-based NL summary.
    """

    def __init__(self) -> None:
        """Initialize the agent with no state beyond its name."""
        self.name = "drought"

    def execute(self, context: dict, **kwargs: Any) -> dict:
        """Execute drought analysis.

        Args:
            context: Structured context from ContextEngine containing
                indicators, warnings, regions, etc.
            **kwargs: Additional runtime parameters (ignored).

        Returns:
            Dict matching DroughtOutput schema with all required fields.
        """
        indicators = context.get("indicators", [])
        warnings = context.get("warnings", [])

        # Extract SPI values from indicators
        spi_30d, spi_90d = self._extract_spi_values(indicators)

        # Classify drought category from SPI
        drought_category = self._classify_drought_category(spi_30d, spi_90d)

        # Calculate SPI status (PRD §5.4.3)
        spi_status = self._calculate_spi_status(spi_30d, spi_90d)

        # Extract soil moisture status for escalation
        soil_moisture_status = self._extract_soil_moisture_status(indicators)

        # Apply soil moisture escalation/de-escalation
        drought_category = self._apply_soil_moisture_adjustment(
            drought_category, soil_moisture_status
        )

        # Calculate drought signal (simplified category for orchestrator)
        drought_signal = self._calculate_drought_signal(drought_category)

        # Calculate data completeness
        found_codes = self._get_found_codes(indicators)
        data_completeness = self._calc_data_completeness(found_codes)

        # Calculate confidence
        confidence = self._calc_confidence(
            data_completeness, warnings, indicators, found_codes
        )

        # Determine trend from SPI comparison
        trend = self._determine_trend(spi_30d, spi_90d)

        # Extract optional metadata
        duration_weeks = self._extract_duration_weeks(indicators)
        spatial_extent_pct = self._extract_spatial_extent(indicators)

        # Generate natural language output with projection (PRD §5.4.3)
        natural_language = self._generate_nl_output(
            spi_30d,
            spi_90d,
            drought_category,
            drought_signal,
            spi_status,
            trend,
            confidence,
        )

        # Build raw output dict
        raw_output = {
            "spi_30d": spi_30d,
            "spi_90d": spi_90d,
            "spi_status": spi_status.value,
            "drought_category": drought_category.value,
            "drought_signal": drought_signal.value,
            "duration_weeks": duration_weeks,
            "spatial_extent_pct": spatial_extent_pct,
            "trend": trend,
            "confidence_score": round(confidence, 4),
            "data_completeness": round(data_completeness, 4),
            "natural_language_output": natural_language,
        }

        # Validate against Pydantic schema before returning (§9.3, §13.1.6)
        return DroughtOutputSchema(**raw_output).model_dump()

    # ============================================================
    # Extraction
    # ============================================================

    def _extract_spi_values(
        self, indicators: list[dict]
    ) -> tuple[float | None, float | None]:
        """Extract SPI_30D and SPI_90D values from indicators.

        Returns:
            Tuple of (spi_30d, spi_90d), each may be None.
        """
        spi_30d: float | None = None
        spi_90d: float | None = None

        for ind in indicators:
            code = ind.get("indicator_code", "").upper()
            if code not in _DROUGHT_CODES:
                continue

            value = ind.get("value")
            if value is None:
                continue

            if code == "SPI_30D":
                spi_30d = float(value)
            elif code == "SPI_90D":
                spi_90d = float(value)

        return spi_30d, spi_90d

    def _extract_soil_moisture_status(
        self, indicators: list[dict]
    ) -> SoilMoistureStatus | None:
        """Extract soil moisture status from indicators for drought adjustment.

        Looks for SM indicators and checks their classification field.
        Returns the most relevant soil moisture status, or None.
        """
        dry_statuses = {
            SoilMoistureStatus.DRY.value.lower(),
            SoilMoistureStatus.CRITICAL_DRY.value.lower(),
        }
        wet_statuses = {
            SoilMoistureStatus.WET.value.lower(),
            SoilMoistureStatus.CRITICAL_WET.value.lower(),
        }
        normal_statuses = {
            SoilMoistureStatus.NORMAL.value.lower(),
        }

        has_dry = False
        has_wet = False
        has_normal = False

        for ind in indicators:
            code = ind.get("indicator_code", "").upper()
            if code not in _SM_DROUGHT_CODES:
                continue

            classification = ind.get("classification", "").lower()
            if classification in dry_statuses:
                has_dry = True
            elif classification in wet_statuses:
                has_wet = True
            elif classification in normal_statuses:
                has_normal = True

        # Priority: dry > wet > normal (dry is most actionable for drought)
        if has_dry:
            return SoilMoistureStatus.DRY
        if has_wet:
            return SoilMoistureStatus.WET
        if has_normal:
            return SoilMoistureStatus.NORMAL

        return None

    def _calculate_spi_status(
        self, spi_30d: float | None, spi_90d: float | None
    ) -> SpiStatus:
        """Calculate SPI-based moisture status.

        SPI >= -1.0 → NORMAL
        -1.5 <= SPI < -1.0 → MODERATE_DROUGHT
        -2.0 <= SPI < -1.5 → SEVERE_DROUGHT
        SPI < -2.0 → EXTREME_DROUGHT

        Uses SPI_90d as primary (longer signal is more reliable).
        Maps to USDM D0-D4 categories per PRD §5.4.3.
        """
        primary = spi_90d if spi_90d is not None else spi_30d
        if primary is None:
            return SpiStatus.NORMAL

        if primary >= -1.0:
            return SpiStatus.NORMAL
        if primary >= -1.5:
            return SpiStatus.MODERATE_DROUGHT
        if primary >= -2.0:
            return SpiStatus.SEVERE_DROUGHT
        return SpiStatus.EXTREME_DROUGHT

    def _extract_duration_weeks(self, indicators: list[dict]) -> int | None:
        """Extract drought duration from indicator metadata."""
        for ind in indicators:
            code = ind.get("indicator_code", "").upper()
            if code not in _DROUGHT_CODES:
                continue
            duration = ind.get("duration_weeks")
            if duration is not None:
                return int(duration)
        return None

    def _extract_spatial_extent(self, indicators: list[dict]) -> float | None:
        """Extract spatial extent percentage from indicator metadata."""
        for ind in indicators:
            code = ind.get("indicator_code", "").upper()
            if code not in _DROUGHT_CODES:
                continue
            extent = ind.get("spatial_extent_pct")
            if extent is not None:
                return float(extent)
        return None

    def _get_found_codes(self, indicators: list[dict]) -> set[str]:
        """Return set of drought-related indicator codes found in context."""
        found: set[str] = set()
        for ind in indicators:
            code = ind.get("indicator_code", "").upper()
            if code in _DROUGHT_CODES:
                found.add(code)
        return found

    # ============================================================
    # Classification
    # ============================================================

    def _classify_drought_category(
        self, spi_30d: float | None, spi_90d: float | None
    ) -> DroughtCategory:
        """Classify drought category using SPI thresholds.

        SPI >= -1.0 → NONE
        -1.5 <= SPI < -1.0 → MILD
        -2.0 <= SPI < -1.5 → MODERATE
        SPI < -2.0 → SEVERE
        SPI < -2.5 → EXTREME (reserved, same as SEVERE for MVP)

        Prefers SPI_90D over SPI_30D (longer signal more reliable).
        If NO SPI data → NONE with low confidence.
        """
        # Prefer SPI_90d (longer-term signal is more reliable)
        primary_spi = spi_90d if spi_90d is not None else spi_30d

        if primary_spi is None:
            return DroughtCategory.NONE

        if primary_spi >= -1.0:
            return DroughtCategory.NONE
        if primary_spi >= -1.5:
            return DroughtCategory.MILD
        if primary_spi >= -2.0:
            return DroughtCategory.MODERATE
        if primary_spi >= -2.5:
            return DroughtCategory.SEVERE
        # SPI < -2.5 → EXTREME (reserved, use SEVERE for MVP)
        return DroughtCategory.SEVERE

    def _apply_soil_moisture_adjustment(
        self,
        category: DroughtCategory,
        soil_moisture_status: SoilMoistureStatus | None,
    ) -> DroughtCategory:
        """Adjust drought category based on soil moisture conditions.

        If soil moisture is DRY/CRITICAL_DRY AND SPI indicates MILD+ → escalate one level.
        If soil moisture is NORMAL/WET → de-escalate one level.
        """
        if soil_moisture_status is None:
            return category

        # Escalation: dry soil moisture pushes drought category worse
        if soil_moisture_status in (
            SoilMoistureStatus.DRY,
            SoilMoistureStatus.CRITICAL_DRY,
        ):
            if category == DroughtCategory.NONE:
                return DroughtCategory.MILD
            if category == DroughtCategory.MILD:
                return DroughtCategory.MODERATE
            if category == DroughtCategory.MODERATE:
                return DroughtCategory.SEVERE
            if category == DroughtCategory.SEVERE:
                return DroughtCategory.EXTREME
            # Already EXTREME — can't escalate further
            return DroughtCategory.EXTREME

        # De-escalation: wet/normal soil moisture reduces drought severity
        if soil_moisture_status in (
            SoilMoistureStatus.NORMAL,
            SoilMoistureStatus.WET,
            SoilMoistureStatus.CRITICAL_WET,
        ):
            if category == DroughtCategory.EXTREME:
                return DroughtCategory.SEVERE
            if category == DroughtCategory.SEVERE:
                return DroughtCategory.MODERATE
            if category == DroughtCategory.MODERATE:
                return DroughtCategory.MILD
            if category == DroughtCategory.MILD:
                return DroughtCategory.NONE
            # Already NONE — can't de-escalate further
            return DroughtCategory.NONE

        return category

    def _calculate_drought_signal(self, category: DroughtCategory) -> DroughtSignal:
        """Calculate simplified drought signal for the orchestrator.

        NONE → NONE, MILD → MILD, MODERATE → MODERATE, SEVERE/EXTREME → SEVERE.
        """
        signal_map = {
            DroughtCategory.NONE: DroughtSignal.NONE,
            DroughtCategory.MILD: DroughtSignal.MILD,
            DroughtCategory.MODERATE: DroughtSignal.MODERATE,
            DroughtCategory.SEVERE: DroughtSignal.SEVERE,
            DroughtCategory.EXTREME: DroughtSignal.SEVERE,
        }
        return signal_map[category]

    # ============================================================
    # Confidence & Completeness
    # ============================================================

    def _calc_data_completeness(self, found_codes: set[str]) -> float:
        """Calculate data completeness as found_indicators / expected_indicators.

        Expected indicators: SPI_30D and SPI_90D (2 primary).
        Each contributes 0.5.
        """
        if not found_codes:
            return 0.0

        has_spi_30d = bool(found_codes & {"SPI_30D"})
        has_spi_90d = bool(found_codes & {"SPI_90D"})

        score = 0.0
        if has_spi_30d:
            score += 0.5
        if has_spi_90d:
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
            if code not in _DROUGHT_CODES:
                continue
            classification = ind.get("classification", "").lower()
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
            if code not in _DROUGHT_CODES:
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
    # Trend
    # ============================================================

    def _determine_trend(
        self, spi_30d: float | None, spi_90d: float | None
    ) -> str:
        """Determine drought trend from SPI comparison.

        If SPI_30d > SPI_90d → "improving" (less negative = improving).
        If SPI_30d < SPI_90d → "worsening" (more negative = worsening).
        If equal or only one available → "stable".
        """
        if spi_30d is None or spi_90d is None:
            return "stable"

        if spi_30d > spi_90d:
            return "improving"
        if spi_30d < spi_90d:
            return "worsening"
        return "stable"

    # ============================================================
    # Natural Language Output
    # ============================================================

    def _generate_nl_output(
        self,
        spi_30d: float | None,
        spi_90d: float | None,
        category: DroughtCategory,
        signal: DroughtSignal,
        spi_status: SpiStatus,
        trend: str,
        confidence: float,
    ) -> str:
        """Generate template-based natural language summary with projection.

        Templates loaded from prompts/templates.py (PRD §4.2 plugin structure).
        Deterministic — no LLM calls.
        """
        if spi_30d is None and spi_90d is None:
            return UNAVAILABLE_MSG

        spi_30d_str = f"{spi_30d:+.2f}" if spi_30d is not None else "N/A"
        spi_90d_str = f"{spi_90d:+.2f}" if spi_90d is not None else "N/A"
        projection = PROJECTIONS.get(trend, "")

        return NL_TEMPLATE.format(
            category=category.value,
            signal=signal.value,
            spi_30d=spi_30d_str,
            spi_90d=spi_90d_str,
            trend=trend,
            projection=projection,
            confidence=confidence,
        )
