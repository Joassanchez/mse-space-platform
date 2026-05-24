"""WeatherAgent — AGENT-HYD-MET-001.

Stateless agent that analyzes climate and weather data for hydric-environmental
assessment. Receives structured context from ContextEngine, extracts rainfall
and anomaly indicators, classifies weather condition, calculates confidence
and data completeness, and produces a template-based natural language summary.
No LLM calls.
"""

from typing import Any

from src.ai.agents.weather.prompts.templates import NL_TEMPLATE, UNAVAILABLE_MSG
from src.ai.agents.weather.schemas import WeatherOutputSchema
from src.ai.domain.models import WeatherCondition


# Expected indicator codes for weather analysis
_WEATHER_CODES = {
    "RAINFALL_30D",
    "RAINFALL_7D",
    "RAINFALL_ANOMALY",
    "TEMPERATURE_ANOMALY",
    "TEMP_AVG",
    "HUMIDITY",
    "WIND_SPEED",
    "FORECAST_RELEVANCE",
}

# Confidence weights (same pattern as SoilMoistureAgent)
_W_DATA_COMPLETENESS = 0.3
_W_FRESHNESS = 0.3
_W_INDICATOR_QUALITY = 0.2
_W_INDICATOR_CONFIDENCE = 0.2


class WeatherAgent:
    """Stateless weather analysis agent.

    Receives structured context from ContextEngine and produces
    WeatherOutput with rainfall values, condition classification,
    confidence scores, and a template-based NL summary.
    """

    def __init__(self) -> None:
        """Initialize the agent with no state beyond its name."""
        self.name = "weather"

    def execute(self, context: dict, **kwargs: Any) -> dict:
        """Execute weather analysis.

        Args:
            context: Structured context from ContextEngine containing
                indicators, warnings, regions, etc.
            **kwargs: Additional runtime parameters (ignored).

        Returns:
            Dict matching WeatherOutput schema with all required fields.
        """
        indicators = context.get("indicators", [])
        warnings = context.get("warnings", [])

        # Extract rainfall, anomaly, and additional weather values
        rainfall_30d, rainfall_7d, anomaly_pct = self._extract_rainfall_values(indicators)

        # Classify condition based on anomaly
        condition = self._classify_condition(anomaly_pct)

        # Extract optional fields
        temperature_anomaly = self._extract_temperature_anomaly(indicators)
        temp_avg = self._extract_value(indicators, "TEMP_AVG")
        humidity = self._extract_value(indicators, "HUMIDITY")
        wind_speed = self._extract_value(indicators, "WIND_SPEED")
        forecast_relevance = self._extract_forecast_relevance(indicators)

        # Calculate data completeness
        found_codes = self._get_found_codes(indicators)
        data_completeness = self._calc_data_completeness(found_codes)

        # Calculate confidence
        confidence = self._calc_confidence(
            data_completeness, warnings, indicators, found_codes
        )

        # Generate natural language output
        natural_language = self._generate_nl_output(
            rainfall_30d,
            rainfall_7d,
            anomaly_pct,
            condition,
            temperature_anomaly,
            temp_avg,
            humidity,
            wind_speed,
            confidence,
        )

        # Build raw output dict
        raw_output = {
            "rainfall_30d_mm": rainfall_30d,
            "rainfall_7d_mm": rainfall_7d,
            "rainfall_anomaly_pct": anomaly_pct,
            "condition": condition.value,
            "temperature_anomaly": temperature_anomaly,
            "temp_avg": temp_avg,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "forecast_relevance": forecast_relevance,
            "confidence_score": round(confidence, 4),
            "data_completeness": round(data_completeness, 4),
            "natural_language_output": natural_language,
        }

        # Validate against Pydantic schema before returning (§9.3, §13.1.6)
        return WeatherOutputSchema(**raw_output).model_dump()

    # ============================================================
    # Extraction
    # ============================================================

    @staticmethod
    def _extract_value(indicators: list[dict], code: str) -> float | None:
        """Extract a single indicator value by code."""
        for ind in indicators:
            if ind.get("indicator_code", "").upper() == code:
                val = ind.get("value")
                return float(val) if val is not None else None
        return None

    def _extract_rainfall_values(
        self, indicators: list[dict]
    ) -> tuple[float | None, float | None, float | None]:
        """Extract rainfall and anomaly values from indicators.

        Searches for indicators with RAINFALL_30D, RAINFALL_7D and RAINFALL_ANOMALY codes.

        Returns:
            Tuple of (rainfall_30d_mm, rainfall_7d_mm, rainfall_anomaly_pct), each may be None.
        """
        rainfall_30d = self._extract_value(indicators, "RAINFALL_30D")
        rainfall_7d = self._extract_value(indicators, "RAINFALL_7D")
        anomaly_pct = self._extract_value(indicators, "RAINFALL_ANOMALY")

        return rainfall_30d, rainfall_7d, anomaly_pct

    def _extract_temperature_anomaly(self, indicators: list[dict]) -> float | None:
        """Extract temperature anomaly from indicators."""
        return self._extract_value(indicators, "TEMPERATURE_ANOMALY")

    def _extract_forecast_relevance(self, indicators: list[dict]) -> float | None:
        """Extract forecast relevance from indicators."""
        return self._extract_value(indicators, "FORECAST_RELEVANCE")

    def _get_found_codes(self, indicators: list[dict]) -> set[str]:
        """Return set of weather-related indicator codes found in context."""
        found: set[str] = set()
        for ind in indicators:
            code = ind.get("indicator_code", "").upper()
            if code in _WEATHER_CODES:
                found.add(code)
        return found

    # ============================================================
    # Classification
    # ============================================================

    def _classify_condition(self, anomaly_pct: float | None) -> WeatherCondition:
        """Classify rainfall condition using anomaly percentage thresholds.

        Thresholds:
            anomaly_pct < -50 → FAR_BELOW
            anomaly_pct < -20 → BELOW_AVERAGE
            -20 <= anomaly_pct <= 20 → AVERAGE
            anomaly_pct > 20 → ABOVE_AVERAGE
            anomaly_pct > 50 → FAR_ABOVE
            None → AVERAGE (default, no data means normal assumption)
        """
        if anomaly_pct is None:
            return WeatherCondition.AVERAGE

        if anomaly_pct < -50:
            return WeatherCondition.FAR_BELOW
        if anomaly_pct < -20:
            return WeatherCondition.BELOW_AVERAGE
        if anomaly_pct > 50:
            return WeatherCondition.FAR_ABOVE
        if anomaly_pct > 20:
            return WeatherCondition.ABOVE_AVERAGE
        return WeatherCondition.AVERAGE

    # ============================================================
    # Confidence & Completeness
    # ============================================================

    def _calc_data_completeness(self, found_codes: set[str]) -> float:
        """Calculate data completeness as found_indicators / expected_indicators.

        Primary indicators: RAINFALL_30D and RAINFALL_ANOMALY.
        RAINFALL_7D, TEMP_AVG, HUMIDITY, WIND_SPEED are bonuses.
        TEMPERATURE_ANOMALY and FORECAST_RELEVANCE are optional bonuses.
        """
        if not found_codes:
            return 0.0

        # Core: 2 primary indicators (0.5 each)
        has_rainfall = bool(found_codes & {"RAINFALL_30D"})
        has_anomaly = bool(found_codes & {"RAINFALL_ANOMALY"})

        score = 0.0
        if has_rainfall:
            score += 0.4
        if has_anomaly:
            score += 0.4

        # Bonus: additional indicators (0.2 total for extras)
        extras = found_codes & {"RAINFALL_7D", "TEMP_AVG", "HUMIDITY", "WIND_SPEED"}
        score += min(len(extras) * 0.05, 0.2)

        return min(score, 1.0)

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
            if code not in _WEATHER_CODES:
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
            if code not in _WEATHER_CODES:
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
    # Natural Language Output
    # ============================================================

    def _generate_nl_output(
        self,
        rainfall_30d: float | None,
        rainfall_7d: float | None,
        anomaly_pct: float | None,
        condition: WeatherCondition,
        temperature_anomaly: float | None,
        temp_avg: float | None,
        humidity: float | None,
        wind_speed: float | None,
        confidence: float,
    ) -> str:
        """Generate template-based natural language summary.

        Templates loaded from prompts/templates.py (PRD §4.2 plugin structure).
        Deterministic — no LLM calls.
        """
        if rainfall_30d is None and anomaly_pct is None:
            return UNAVAILABLE_MSG

        rainfall_30d_str = f"{rainfall_30d:.1f} mm" if rainfall_30d is not None else "N/A"
        rainfall_7d_str = f"{rainfall_7d:.1f} mm" if rainfall_7d is not None else "N/A"
        anomaly_str = (
            f"{anomaly_pct:+.1f}%" if anomaly_pct is not None else "N/A"
        )
        temp_anom_str = (
            f"{temperature_anomaly:+.1f}°C"
            if temperature_anomaly is not None
            else "N/A"
        )
        temp_str = f"{temp_avg:.1f}°C" if temp_avg is not None else "N/A"
        humid_str = f"{humidity:.0f}%" if humidity is not None else "N/A"
        wind_str = f"{wind_speed:.1f} m/s" if wind_speed is not None else "N/A"

        return NL_TEMPLATE.format(
            rainfall_30d=rainfall_30d_str,
            anomaly=anomaly_str,
            condition=condition.value,
            rainfall_7d=rainfall_7d_str,
            temp_avg=temp_str,
            temp_anom=temp_anom_str,
            humidity=humid_str,
            wind=wind_str,
            confidence=confidence,
        )
