"""Pydantic schemas for the model/prediction module.

Defines the contract between the rule engine and the API response.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Input (same as analysis request)
# ---------------------------------------------------------------------------


class PredictRequest(BaseModel):
    """Input for the prediction endpoint — mirrors analysis query."""

    lot_id: str
    crop: str  # "soy" | "corn"
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    date: str  # YYYY-MM-DD


# ---------------------------------------------------------------------------
# Anomalies
# ---------------------------------------------------------------------------


class Anomaly(BaseModel):
    """A single detected anomaly with evidence."""

    type: str  # water_stress | heat_stress | ndvi_drop | market_risk
    severity: str  # low | medium | high | critical
    confidence: float = Field(ge=0.0, le=1.0)
    description: str
    evidence: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------


class RiskFactor(BaseModel):
    """Weighted risk contributor."""

    name: str
    score: float = Field(ge=0, le=100)
    weight: float


class RiskAssessment(BaseModel):
    """Aggregated risk evaluation."""

    overall: str  # low | medium | high | critical
    score: float = Field(ge=0, le=100)
    factors: list[RiskFactor]


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------


class YieldPrediction(BaseModel):
    """Yield estimate and comparison to potential."""

    estimate_kg_ha: float
    potential_kg_ha: float
    loss_pct: float
    harvest_window_start: str | None = None
    harvest_window_end: str | None = None


# ---------------------------------------------------------------------------
# Economic impact
# ---------------------------------------------------------------------------


class ImpactBreakdown(BaseModel):
    """Per-factor economic loss estimate."""

    factor: str
    impact_ars: float


class EconomicImpact(BaseModel):
    """Estimated economic loss for the campaign."""

    estimated_loss_ars: float
    loss_pct: float
    protected_value_ars: float
    breakdown: list[ImpactBreakdown]


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


class Recommendation(BaseModel):
    """Actionable recommendation for the producer."""

    priority: int = Field(ge=1)
    action: str
    urgency: str  # immediate | short_term | monitor
    expected_benefit_pct: float | None = None
    audience: list[str] = Field(default_factory=list)  # productor | ingeniero | contratista


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


class Alert(BaseModel):
    """User-facing alert."""

    type: str  # critical | warning | info
    title: str
    message: str
    audience: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Unified response
# ---------------------------------------------------------------------------


class PredictResponse(BaseModel):
    """Complete prediction response — anomalies, risk, yield, economics, actions."""

    query: PredictRequest
    anomalies: list[Anomaly]
    risk_assessment: RiskAssessment
    yield_prediction: YieldPrediction | None = None
    economic_impact: EconomicImpact | None = None
    recommendations: list[Recommendation]
    alerts: list[Alert]
    generated_at: str
    data_sources: list[str] = Field(default_factory=list)
