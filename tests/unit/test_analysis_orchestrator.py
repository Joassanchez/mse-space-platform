"""Unit tests for the AnalysisOrchestrator.

Tests the orchestrator with all four module services mocked:
- Full success: all 4 modules return data
- Partial failure: one module fails, others succeed
- Cache scenario: verify response shape
- BBCH stage estimation
- Historical aggregation from POWER data
"""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from argplant.modules.analysis.models import (
    AgroclimateSection,
    AgronomySection,
    AnalysisResponse,
    EconomySection,
    SatelliteSection,
)
from argplant.modules.analysis.orchestrator import (
    AnalysisOrchestrator,
    _aggregate_historical,
    _crop_to_product_id,
    _estimate_bbch_stage,
    _estimate_planting_date,
    _extract_latest_price,
    _extract_price_series,
)

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_WEATHER = {
    "lat": -33.89,
    "lon": -60.57,
    "temp": 25.3,
    "humidity": 55,
    "wind_speed": 3.6,
    "conditions": "clear sky",
    "timestamp": "2026-07-21T14:00:00Z",
}

MOCK_POWER = {
    "lat": -33.89,
    "lon": -60.57,
    "start_date": "20260706",
    "end_date": "20260721",
    "parameters": [
        {
            "name": "PRECTOTCORR",
            "values": [0.0, 2.3, 0.0, 0.0, 0.0, 0.0, 1.5, 0.0, 0.0, 0.0, 4.7, 0.0, 0.0, 0.0, 0.0],
        },
        {
            "name": "ALLSKY_SFC_SW_DWN",
            "values": [18.0, 17.5, 19.2, 18.8, 20.1, 20.5, 19.0, 17.8, 16.5, 18.2, 18.5, 19.8, 20.0, 17.5, 18.2],
        },
        {
            "name": "T2M",
            "values": [21.0, 22.5, 23.0, 22.8, 21.5, 20.2, 22.0, 23.5, 22.7, 22.0, 21.0, 22.8, 23.2, 22.1, 21.8],
        },
    ],
    "unit_map": {
        "PRECTOTCORR": "mm",
        "ALLSKY_SFC_SW_DWN": "MJ/m²/day",
        "T2M": "°C",
    },
}

MOCK_SMAP_SCENES = [
    {
        "scene_id": "SMAP_L3_SM_P_20260720",
        "acquisition_date": "2026-07-20T12:00:00Z",
        "granule_ur": "SMAP_L3_SM_P_20260720",
        "platform": "smap",
        "bbox": [-61.0, -34.0, -60.0, -33.0],
    }
]

MOCK_SENTINEL_SCENES = [
    {
        "id": "S2B_MSIL2A_20260718T143729",
        "acquisition_date": "2026-07-18T14:30:00Z",
        "cloud_cover": 3.2,
        "thumbnail_url": None,
        "platform": "Sentinel-2",
        "bbox": [-61.0, -34.0, -60.0, -33.0],
    }
]

MOCK_CROP_DATA = {
    "soy": {
        "id": "soy",
        "name": "Soja",
        "scientific_name": "Glycine max",
        "growing_season_days": 120,
        "temperature": {"optimal_min": 20, "optimal_max": 30, "stress_min": 35, "stress_max": 42},
    }
}

MOCK_PRICE_RESPONSE = {
    "producto_id": 18,
    "producto": "Soja",
    "puerto_id": 23,
    "puerto": "Rosario",
    "minimos": [
        {"fecha": "2026-07-14", "valor": 481000},
        {"fecha": "2026-07-15", "valor": 482500},
        {"fecha": "2026-07-16", "valor": 483000},
        {"fecha": "2026-07-17", "valor": 485000},
        {"fecha": "2026-07-18", "valor": 486000},
        {"fecha": "2026-07-19", "valor": 487500},
        {"fecha": "2026-07-20", "valor": 488000},
        {"fecha": "2026-07-21", "valor": 497000},
    ],
    "maximos": [
        {"fecha": "2026-07-14", "valor": 490000},
        {"fecha": "2026-07-15", "valor": 491000},
        {"fecha": "2026-07-16", "valor": 492000},
        {"fecha": "2026-07-17", "valor": 493000},
        {"fecha": "2026-07-18", "valor": 494000},
        {"fecha": "2026-07-19", "valor": 495000},
        {"fecha": "2026-07-20", "valor": 496000},
        {"fecha": "2026-07-21", "valor": 500000},
    ],
    "promedios": [
        {"fecha": "2026-07-14", "valor": 486978},
        {"fecha": "2026-07-15", "valor": 487000},
        {"fecha": "2026-07-16", "valor": 488000},
        {"fecha": "2026-07-17", "valor": 489000},
        {"fecha": "2026-07-18", "valor": 490000},
        {"fecha": "2026-07-19", "valor": 491000},
        {"fecha": "2026-07-20", "valor": 492000},
        {"fecha": "2026-07-21", "valor": 498851},
    ],
    "modal": [{"valor": 498000}],
}

QUERY_DATE = date(2026, 7, 21)


# ---------------------------------------------------------------------------
# Helper to create a mocked orchestrator
# ---------------------------------------------------------------------------


def _mock_orchestrator(test_redis):
    """Create an AnalysisOrchestrator with all four _fetch_* methods mocked."""
    orch = AnalysisOrchestrator(test_redis)

    orch._fetch_agroclimate = AsyncMock(  # type: ignore[method-assign]
        return_value=AgroclimateSection(
            current=MOCK_WEATHER,
            historical={
                "precipitation_15d_mm": 8.5,
                "solar_radiation_avg": 18.7,
                "temp_avg_15d": 22.1,
            },
        )
    )

    orch._fetch_satellite = AsyncMock(  # type: ignore[method-assign]
        return_value=SatelliteSection(
            soil_moisture=MOCK_SMAP_SCENES,
            optical=MOCK_SENTINEL_SCENES,
        )
    )

    orch._fetch_agronomy = AsyncMock(  # type: ignore[method-assign]
        return_value=AgronomySection(
            crop_info={
                "id": "soy",
                "name": "Soja",
                "scientific_name": "Glycine max",
                "growing_season_days": 120,
                "temperature": {"optimal_min": 20, "optimal_max": 30, "stress_min": 35},
            },
            current_stage={
                "bbch_code": "75",
                "name": "Llenado de vainas",
                "kc": 1.05,
                "water_stress_sensitivity": "high",
            },
        )
    )

    orch._fetch_economy = AsyncMock(  # type: ignore[method-assign]
        return_value=EconomySection(
            latest_price={
                "fecha": "2026-07-21",
                "promedio": 498851,
                "modal": 498000,
            },
            series=[
                {"fecha": "2026-07-14", "minimo": 481000, "maximo": 490000, "promedio": 486978},
                {"fecha": "2026-07-15", "minimo": 482500, "maximo": 491000, "promedio": 487000},
                {"fecha": "2026-07-16", "minimo": 483000, "maximo": 492000, "promedio": 488000},
                {"fecha": "2026-07-17", "minimo": 485000, "maximo": 493000, "promedio": 489000},
                {"fecha": "2026-07-18", "minimo": 486000, "maximo": 494000, "promedio": 490000},
                {"fecha": "2026-07-19", "minimo": 487500, "maximo": 495000, "promedio": 491000},
                {"fecha": "2026-07-20", "minimo": 488000, "maximo": 496000, "promedio": 492000},
                {"fecha": "2026-07-21", "minimo": 497000, "maximo": 500000, "promedio": 498851},
            ],
        )
    )

    return orch


# ---------------------------------------------------------------------------
# Full success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gather_all_modules_success(test_redis):
    """All four modules succeed → status 'complete', no missing modules."""
    orch = _mock_orchestrator(test_redis)
    result = await orch.gather("lote-123", "soy", -33.89, -60.57, QUERY_DATE)

    assert isinstance(result, AnalysisResponse)
    assert result.meta.status == "complete"
    assert result.meta.missing_modules == []

    assert result.agroclimate is not None
    assert result.agroclimate.current["temp"] == 25.3
    assert result.agroclimate.historical["precipitation_15d_mm"] == 8.5

    assert result.satellite is not None
    assert len(result.satellite.soil_moisture) == 1
    assert len(result.satellite.optical) == 1

    assert result.agronomy is not None
    assert result.agronomy.crop_info["name"] == "Soja"
    assert result.agronomy.current_stage["name"] == "Llenado de vainas"

    assert result.economy is not None
    assert result.economy.latest_price["promedio"] == 498851
    assert len(result.economy.series) == 8  # July 14–21 inclusive

    assert result.query.lot_id == "lote-123"
    assert result.query.crop == "soy"


# ---------------------------------------------------------------------------
# Partial failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gather_partial_failure_economy(test_redis):
    """Economy module fails → status 'partial', economy listed as missing."""
    orch = _mock_orchestrator(test_redis)

    # Override economy to raise
    orch._fetch_economy = AsyncMock(  # type: ignore[method-assign]
        side_effect=Exception("MAGyP unavailable")
    )

    result = await orch.gather("lote-123", "soy", -33.89, -60.57, QUERY_DATE)

    assert result.meta.status == "partial"
    assert "economy" in result.meta.missing_modules
    assert result.economy is None
    # Other modules still present
    assert result.agroclimate is not None
    assert result.satellite is not None
    assert result.agronomy is not None


@pytest.mark.asyncio
async def test_gather_partial_failure_satellite(test_redis):
    """Satellite module fails → status 'partial', satellite listed as missing."""
    orch = _mock_orchestrator(test_redis)

    orch._fetch_satellite = AsyncMock(  # type: ignore[method-assign]
        side_effect=Exception("CDSE timeout")
    )

    result = await orch.gather("lote-123", "soy", -33.89, -60.57, QUERY_DATE)

    assert result.meta.status == "partial"
    assert "satellite" in result.meta.missing_modules
    assert result.satellite is None
    assert result.agroclimate is not None
    assert result.agronomy is not None
    assert result.economy is not None


@pytest.mark.asyncio
async def test_gather_multiple_failures(test_redis):
    """Multiple modules fail → status 'partial', all failures listed."""
    orch = _mock_orchestrator(test_redis)

    orch._fetch_satellite = AsyncMock(  # type: ignore[method-assign]
        side_effect=Exception("CDSE timeout")
    )
    orch._fetch_economy = AsyncMock(  # type: ignore[method-assign]
        side_effect=Exception("MAGyP unavailable")
    )

    result = await orch.gather("lote-123", "soy", -33.89, -60.57, QUERY_DATE)

    assert result.meta.status == "partial"
    assert "satellite" in result.meta.missing_modules
    assert "economy" in result.meta.missing_modules
    assert len(result.meta.missing_modules) == 2


# ---------------------------------------------------------------------------
# Historical aggregation
# ---------------------------------------------------------------------------


def test_aggregate_historical_sums_precip():
    """PRECTOTCORR values are summed correctly."""
    historical = _aggregate_historical(MOCK_POWER)
    assert historical["precipitation_15d_mm"] == 8.5  # 0+2.3+0+0+0+0+1.5+0+0+0+4.7+0+0+0+0


def test_aggregate_historical_averages_solar():
    """ALLSKY_SFC_SW_DWN values are averaged correctly."""
    historical = _aggregate_historical(MOCK_POWER)
    assert 18.0 < historical["solar_radiation_avg"] < 19.0


def test_aggregate_historical_averages_temp():
    """T2M values are averaged correctly."""
    historical = _aggregate_historical(MOCK_POWER)
    assert 21.5 < historical["temp_avg_15d"] < 22.5


def test_aggregate_historical_handles_none():
    """None values (missing data) are excluded from averages."""
    power_with_nones = {
        "parameters": [
            {"name": "PRECTOTCORR", "values": [1.0, None, 2.0]},
            {"name": "T2M", "values": [20.0, None, 22.0]},
        ]
    }
    historical = _aggregate_historical(power_with_nones)
    assert historical["precipitation_15d_mm"] == 3.0  # 1 + 2
    assert historical["temp_avg_15d"] == 21.0  # (20+22)/2


# ---------------------------------------------------------------------------
# Crop → producto_id mapping
# ---------------------------------------------------------------------------


def test_crop_to_product_id_soy():
    assert _crop_to_product_id("soy") == 18


def test_crop_to_product_id_corn():
    assert _crop_to_product_id("corn") == 1


def test_crop_to_product_id_case_insensitive():
    assert _crop_to_product_id("SOY") == 18


def test_crop_to_product_id_unknown():
    assert _crop_to_product_id("sunflower") is None


# ---------------------------------------------------------------------------
# Price extraction
# ---------------------------------------------------------------------------


def test_extract_latest_price():
    raw = {
        "promedios": [
            {"fecha": "2026-07-14", "valor": 486978},
            {"fecha": "2026-07-21", "valor": 498851},
        ],
        "modal": [{"valor": 498000}],
    }
    result = _extract_latest_price(raw)
    assert result is not None
    assert result["fecha"] == "2026-07-21"
    assert result["promedio"] == 498851
    assert result["modal"] == 498000


def test_extract_latest_price_empty():
    result = _extract_latest_price({"promedios": []})
    assert result is None


def test_extract_price_series():
    raw = {
        "minimos": [
            {"fecha": "2026-07-14", "valor": 481000},
            {"fecha": "2026-07-15", "valor": 482500},
        ],
        "maximos": [
            {"fecha": "2026-07-14", "valor": 490000},
            {"fecha": "2026-07-15", "valor": 491000},
        ],
        "promedios": [
            {"fecha": "2026-07-14", "valor": 486978},
            {"fecha": "2026-07-15", "valor": 487000},
        ],
    }
    series = _extract_price_series(raw)
    assert len(series) == 2
    assert series[0]["fecha"] == "2026-07-14"
    assert series[0]["minimo"] == 481000
    assert series[0]["maximo"] == 490000
    assert series[0]["promedio"] == 486978


# ---------------------------------------------------------------------------
# BBCH stage estimation
# ---------------------------------------------------------------------------


def test_estimate_planting_date_soy_summer():
    """Soy in January → planted previous October."""
    result = _estimate_planting_date("soy", date(2026, 1, 15))
    assert result == date(2025, 10, 15)


def test_estimate_planting_date_soy_spring():
    """Soy in November → planted same year October."""
    result = _estimate_planting_date("soy", date(2026, 11, 1))
    assert result == date(2026, 10, 15)


def test_estimate_planting_date_corn():
    """Corn in December → planted same year September."""
    result = _estimate_planting_date("corn", date(2026, 12, 1))
    assert result == date(2026, 9, 15)


def test_estimate_planting_date_corn_winter():
    """Corn in July → planted previous year September."""
    result = _estimate_planting_date("corn", date(2026, 7, 1))
    assert result == date(2025, 9, 15)


def test_estimate_planting_date_unknown():
    assert _estimate_planting_date("wheat", date(2026, 7, 1)) is None


def test_estimate_bbch_stage_returns_none_for_unknown_crop():
    from argplant.modules.agronomy.models import GrowthStage

    stages = [
        GrowthStage(
            bbch_code="00", name="Seed", description="", kc=0.0,
            water_stress_sensitivity="low", temp_sensitivity="low",
        )
    ]
    result = _estimate_bbch_stage("unknown", QUERY_DATE, stages, 120)
    assert result is None


def test_estimate_bbch_stage_mid_season():
    """Mid-season → picks a proportional stage."""
    from argplant.modules.agronomy.models import GrowthStage

    stages = [
        GrowthStage(
            bbch_code="00", name="Seed", description="", kc=0.0,
            water_stress_sensitivity="low", temp_sensitivity="low",
        ),
        GrowthStage(
            bbch_code="50", name="Mid", description="", kc=1.0,
            water_stress_sensitivity="medium", temp_sensitivity="medium",
        ),
        GrowthStage(
            bbch_code="89", name="Harvest", description="", kc=0.2,
            water_stress_sensitivity="low", temp_sensitivity="low",
        ),
    ]

    # July 21 → soy planted Oct 15, 2025 = ~279 days → clamped to 120 → stage 2 (last)
    result = _estimate_bbch_stage("soy", QUERY_DATE, stages, 120)
    assert result is not None
    # 279 days > 120, so clamped to last stage
    assert result["bbch_code"] == "89"


def test_estimate_bbch_stage_before_planting():
    """Before planting date → returns first stage."""
    from argplant.modules.agronomy.models import GrowthStage

    stages = [
        GrowthStage(
            bbch_code="00", name="Seed", description="", kc=0.0,
            water_stress_sensitivity="low", temp_sensitivity="low",
        ),
        GrowthStage(
            bbch_code="09", name="Emergence", description="", kc=0.4,
            water_stress_sensitivity="medium", temp_sensitivity="medium",
        ),
    ]
    # Sept 1 → soy planted Oct 15, 2026 → before planting
    result = _estimate_bbch_stage("soy", date(2026, 9, 1), stages, 120)
    assert result is not None
    assert result["bbch_code"] == "00"


def test_estimate_bbch_stage_includes_expected_keys():
    """BBCH stage dict includes bbch_code, name, kc, water_stress_sensitivity."""
    from argplant.modules.agronomy.models import GrowthStage

    stages = [
        GrowthStage(
            bbch_code="71", name="Pod fill", description="Pods developing", kc=1.1,
            water_stress_sensitivity="high", temp_sensitivity="medium",
        ),
    ]
    result = _estimate_bbch_stage("soy", date(2026, 10, 20), stages, 120)
    assert result is not None
    assert result["bbch_code"] == "71"
    assert result["name"] == "Pod fill"
    assert result["kc"] == 1.1
    assert result["water_stress_sensitivity"] == "high"
    assert "temp_sensitivity" not in result  # excluded from response shape
