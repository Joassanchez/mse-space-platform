"""Rule engine for ARGPLANT anomaly detection and prediction.

Applies agronomic rules to the unified analysis data to detect crop stress,
estimate yield loss, calculate economic impact, and generate recommendations.

All rules are deterministic — no ML involved in this MVP. The agronomic
catalog (BBCH stages, Kc coefficients, crop thresholds) is the model.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from argplant.modules.model.models import (
    Alert,
    Anomaly,
    EconomicImpact,
    ImpactBreakdown,
    PredictRequest,
    PredictResponse,
    Recommendation,
    RiskAssessment,
    RiskFactor,
    YieldPrediction,
)

logger = logging.getLogger("argplant.model")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Crop-specific yield potential (kg/ha) for Pampa Húmeda — Pergamino region
_YIELD_POTENTIAL: dict[str, float] = {
    "soy": 4000.0,
    "corn": 10000.0,
}

# Price per ton in ARS (latest known for Pergamino area)
_DEFAULT_PRICE_ARS_PER_TON: dict[str, float] = {
    "soy": 490000.0,
    "corn": 220000.0,
}

# NDVI thresholds per water_stress_sensitivity
_NDVI_THRESHOLDS: dict[str, float] = {
    "low": 0.85,       # < 85% of expected → anomaly
    "medium": 0.88,
    "high": 0.92,
    "critical": 0.95,
}

# Soil moisture thresholds (m³/m³)
_SOIL_MOISTURE_CRITICAL: float = 0.15
_SOIL_MOISTURE_LOW: float = 0.22
_SOIL_MOISTURE_OK: float = 0.28

# Water deficit (mm) accumulated lookback
_WATER_DEFICIT_DAYS: int = 15
_WATER_DEFICIT_LOW: float = 10.0
_WATER_DEFICIT_MEDIUM: float = 25.0

# Temperature stress — days above threshold
_HEAT_STRESS_DAYS_THRESHOLD: int = 3


class RuleEngine:
    """Evaluate agronomic rules against analysis data and produce predictions."""

    def evaluate(
        self,
        request: PredictRequest,
        analysis_data: dict[str, Any],
    ) -> PredictResponse:
        """Run all rules and return a unified prediction response.

        Args:
            request: The prediction query (lot_id, crop, lat, lon, date).
            analysis_data: The raw dict from GET /api/v1/analysis response.

        Returns:
            PredictResponse with anomalies, risk, yield, economics, and actions.
        """
        crop = request.crop.lower()
        anomalies: list[Anomaly] = []
        now = datetime.now(timezone.utc).isoformat()

        # Extract sections from analysis
        agro = analysis_data.get("agroclimate") or {}
        sat = analysis_data.get("satellite") or {}
        agron = analysis_data.get("agronomy") or {}
        econ_section = analysis_data.get("economy") or {}
        econ_latest = econ_section.get("latest_price") if isinstance(econ_section, dict) else {}

        current_stage = (agron.get("current_stage") or {}) if agron else {}
        crop_info = agron.get("crop_info", {})

        # ── Rule 1: Water stress via soil moisture ──
        sm_value = (sat.get("soil_moisture_value") or {}) if sat else {}
        if sm_value.get("soil_moisture") is not None:
            sm = sm_value["soil_moisture"]
            if sm < _SOIL_MOISTURE_CRITICAL:
                anomalies.append(Anomaly(
                    type="water_stress",
                    severity="critical",
                    confidence=0.95,
                    description=(
                        f"Humedad del suelo crítica ({sm * 100:.0f}%). "
                        f"Riesgo severo de estrés hídrico en etapa {current_stage.get('bbch_code', '?')}."
                    ),
                    evidence={"soil_moisture": sm, "threshold": _SOIL_MOISTURE_CRITICAL},
                ))
            elif sm < _SOIL_MOISTURE_LOW:
                anomalies.append(Anomaly(
                    type="water_stress",
                    severity="high",
                    confidence=0.85,
                    description=f"Humedad del suelo baja ({sm * 100:.0f}%). Monitorear riego.",
                    evidence={"soil_moisture": sm, "threshold": _SOIL_MOISTURE_LOW},
                ))
            elif sm < _SOIL_MOISTURE_OK:
                anomalies.append(Anomaly(
                    type="water_stress",
                    severity="medium",
                    confidence=0.70,
                    description=f"Humedad del suelo por debajo del óptimo ({sm * 100:.0f}%).",
                    evidence={"soil_moisture": sm, "threshold": _SOIL_MOISTURE_OK},
                ))

        # ── Rule 2: Heat stress ──
        temp_thresholds = crop_info.get("temperature", {})
        stress_temp = temp_thresholds.get("stress_min", 35)
        current_agro = agro.get("current", {}) if agro else {}
        current_temp = current_agro.get("temp")
        if current_temp is not None and current_temp >= stress_temp:
            anomalies.append(Anomaly(
                type="heat_stress",
                severity="high" if current_temp >= stress_temp + 3 else "medium",
                confidence=0.82,
                description=(
                    f"Temperatura actual ({current_temp}°C) supera el umbral de estrés "
                    f"({stress_temp}°C). Riesgo de aborto floral y reducción de cuajado."
                ),
                evidence={"current_temp": current_temp, "threshold": stress_temp},
            ))

        # ── Rule 3: Water deficit from POWER data ──
        historical = agro.get("historical", {}) if agro else {}
        precip_15d = historical.get("precipitation_15d_mm", 0)
        if precip_15d < _WATER_DEFICIT_LOW:
            anomalies.append(Anomaly(
                type="water_stress",
                severity="critical" if precip_15d < 5 else "high",
                confidence=0.88,
                description=f"Déficit hídrico acumulado: {precip_15d}mm en 15 días.",
                evidence={"precipitation_15d_mm": precip_15d, "threshold_mm": _WATER_DEFICIT_LOW},
            ))
        elif precip_15d < _WATER_DEFICIT_MEDIUM:
            anomalies.append(Anomaly(
                type="water_stress",
                severity="medium",
                confidence=0.72,
                description=f"Precipitación por debajo de lo esperado: {precip_15d}mm en 15 días.",
                evidence={"precipitation_15d_mm": precip_15d},
            ))

        # ── Risk assessment ──
        risk_factors, overall_score = self._compute_risk(anomalies, current_stage, crop)
        risk = RiskAssessment(
            overall=self._score_to_label(overall_score),
            score=overall_score,
            factors=risk_factors,
        )

        # ── Yield prediction ──
        potential = _YIELD_POTENTIAL.get(crop, 4000.0)
        loss_pct = self._estimate_yield_loss(anomalies, current_stage)
        estimate = potential * (1 - loss_pct / 100)
        yield_pred = YieldPrediction(
            estimate_kg_ha=round(estimate, 0),
            potential_kg_ha=potential,
            loss_pct=round(loss_pct, 1),
        )

        # ── Economic impact ──
        price_per_ton = _DEFAULT_PRICE_ARS_PER_TON.get(crop, 300000.0)
        econ = self._compute_economic_impact(
            anomalies, yield_pred, price_per_ton
        )

        # ── Recommendations ──
        recs = self._generate_recommendations(anomalies, current_stage, crop)

        # ── Alerts ──
        alerts = self._generate_alerts(anomalies, risk, request)

        # Data sources used
        sources = ["agroclimate", "agronomy"]
        if sat and sat.get("soil_moisture_value"):
            sources.append("satellite_smap")
        if econ_latest:
            sources.append("economy")

        return PredictResponse(
            query=request,
            anomalies=anomalies,
            risk_assessment=risk,
            yield_prediction=yield_pred,
            economic_impact=econ,
            recommendations=recs,
            alerts=alerts,
            generated_at=now,
            data_sources=sources,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_risk(
        anomalies: list[Anomaly],
        current_stage: dict[str, Any],
        crop: str,
    ) -> tuple[list[RiskFactor], float]:
        """Weight anomalies by severity and stage sensitivity to produce risk score."""
        severity_weight: dict[str, float] = {
            "critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25,
        }
        stage_sensitivity = current_stage.get("water_stress_sensitivity", "medium")
        sensitivity_mult: dict[str, float] = {
            "high": 1.5, "medium": 1.0, "low": 0.5,
        }

        factors: list[RiskFactor] = []
        total_weight = 0.0
        weighted_sum = 0.0

        for a in anomalies:
            weight = severity_weight.get(a.severity, 0.5)
            if a.type == "water_stress":
                weight *= sensitivity_mult.get(stage_sensitivity, 1.0)
            raw_score = weight * 100
            raw_score = min(raw_score, 100.0)  # cap at 100 for Pydantic validation
            factors.append(RiskFactor(name=a.type, score=round(raw_score, 1), weight=round(weight, 2)))
            weighted_sum += raw_score * weight
            total_weight += weight

        if not factors:
            return [RiskFactor(name="no_anomalies", score=0.0, weight=1.0)], 0.0

        overall = min(100.0, weighted_sum / total_weight if total_weight > 0 else 0.0)
        return factors, round(overall, 1)

    @staticmethod
    def _score_to_label(score: float) -> str:
        if score >= 75:
            return "critical"
        if score >= 50:
            return "high"
        if score >= 25:
            return "medium"
        return "low"

    @staticmethod
    def _estimate_yield_loss(
        anomalies: list[Anomaly],
        current_stage: dict[str, Any],
    ) -> float:
        """Estimate yield loss percentage based on anomaly severity and crop stage."""
        severity_loss: dict[str, float] = {
            "critical": 25.0, "high": 15.0, "medium": 8.0, "low": 3.0,
        }
        stage = current_stage.get("name", "").lower()
        # Higher loss during reproductive stages
        reproductive_keywords = ["floración", "cuajado", "vainas", "llenado", "grano"]
        stage_mult = 1.3 if any(kw in stage for kw in reproductive_keywords) else 1.0

        total_loss = 0.0
        for a in anomalies:
            loss = severity_loss.get(a.severity, 5.0) * stage_mult
            total_loss = min(total_loss + loss * 0.5, 90.0)  # diminishing returns, cap at 90%

        return round(total_loss, 1)

    @staticmethod
    def _compute_economic_impact(
        anomalies: list[Anomaly],
        yield_pred: YieldPrediction,
        price_per_ton: float,
    ) -> EconomicImpact:
        """Estimate economic loss in ARS."""
        tons_lost = (yield_pred.potential_kg_ha - yield_pred.estimate_kg_ha) / 1000.0
        loss_ars = tons_lost * price_per_ton
        loss_pct = yield_pred.loss_pct

        breakdown: list[ImpactBreakdown] = []
        for a in anomalies:
            factor_weight = {"critical": 0.6, "high": 0.3, "medium": 0.1}.get(a.severity, 0.05)
            breakdown.append(ImpactBreakdown(
                factor=a.type,
                impact_ars=round(loss_ars * factor_weight),
            ))

        protected_value = yield_pred.potential_kg_ha / 1000.0 * price_per_ton * (loss_pct / 100)

        return EconomicImpact(
            estimated_loss_ars=round(loss_ars),
            loss_pct=loss_pct,
            protected_value_ars=round(protected_value),
            breakdown=breakdown,
        )

    @staticmethod
    def _generate_recommendations(
        anomalies: list[Anomaly],
        current_stage: dict[str, Any],
        crop: str,
    ) -> list[Recommendation]:
        """Generate actionable recommendations based on detected anomalies."""
        recs: list[Recommendation] = []
        priority = 0

        water_anomalies = [a for a in anomalies if a.type == "water_stress"]
        heat_anomalies = [a for a in anomalies if a.type == "heat_stress"]

        critical_water = any(a.severity == "critical" for a in water_anomalies)
        high_water = any(a.severity in ("critical", "high") for a in water_anomalies)
        high_heat = any(a.severity in ("critical", "high") for a in heat_anomalies)

        if critical_water:
            priority += 1
            recs.append(Recommendation(
                priority=priority,
                action="Riego suplementario urgente (25-30mm) en zona afectada del lote",
                urgency="immediate",
                expected_benefit_pct=12.0,
                audience=["productor", "ingeniero"],
            ))
        elif high_water:
            priority += 1
            recs.append(Recommendation(
                priority=priority,
                action="Programar riego suplementario (20mm) en próxima ventana disponible",
                urgency="short_term",
                expected_benefit_pct=8.0,
                audience=["productor"],
            ))

        if high_heat:
            priority += 1
            recs.append(Recommendation(
                priority=priority,
                action="Aplicar bioestimulante anti-estrés térmico. Monitorear evapotranspiración sector este",
                urgency="short_term",
                audience=["ingeniero", "contratista"],
            ))

        if not recs:
            recs.append(Recommendation(
                priority=1,
                action="Continuar monitoreo regular. Sin anomalías detectadas.",
                urgency="monitor",
                audience=["productor"],
            ))

        return recs

    @staticmethod
    def _generate_alerts(
        anomalies: list[Anomaly],
        risk: RiskAssessment,
        request: PredictRequest,
    ) -> list[Alert]:
        """Generate user-facing alerts from anomalies."""
        alerts: list[Alert] = []

        for a in anomalies:
            alert_type = "critical" if a.severity == "critical" else "warning" if a.severity == "high" else "info"
            alerts.append(Alert(
                type=alert_type,
                title=f"{a.type.replace('_', ' ').title()} — {request.lot_id}",
                message=a.description,
                audience=["productor", "ingeniero"],
            ))

        # Overall risk alert
        if risk.overall in ("critical", "high"):
            alerts.insert(0, Alert(
                type="critical",
                title=f"Riesgo {risk.overall.upper()} — {request.lot_id} ({request.crop})",
                message=(
                    f"Score de riesgo: {risk.score}/100. "
                    f"Se detectaron {len(anomalies)} anomalía(s). "
                    "Requiere atención inmediata."
                ),
                audience=["productor", "ingeniero"],
            ))

        return alerts
