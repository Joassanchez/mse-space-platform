"""Analysis orchestrator — aggregates all four data modules into a unified response.

Runs agroclimate, satellite, agronomy, and economy data fetches in parallel
via asyncio.gather(return_exceptions=True). Handles partial failures
gracefully by returning available data and flagging missing modules.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import redis.asyncio as aioredis

from argplant.modules.agroclimate.service import PowerService, WeatherService
from argplant.modules.agronomy.models import GrowthStage
from argplant.modules.agronomy.seed_data import get_crops, get_stages
from argplant.modules.agronomy.service import CropCatalogService
from argplant.modules.analysis.models import (
    AgroclimateSection,
    AgronomySection,
    AnalysisMeta,
    AnalysisRequest,
    AnalysisResponse,
    EconomySection,
    SatelliteSection,
)
from argplant.modules.economy.service import PriceService
from argplant.modules.satellite.service import SentinelService, SmapService
from argplant.modules.satellite.smap_reader import SmapPixel, read_smap_pixel

logger = logging.getLogger("argplant.analysis")

# ---------------------------------------------------------------------------
# Crop → MAGyP producto_id mapping
# ---------------------------------------------------------------------------

_CROP_PRODUCT_MAP: dict[str, int] = {
    "soy": 18,
    "corn": 1,
}

# Default port for grain prices (Rosario — main grain port in Argentina)
_DEFAULT_PORT = 23

# POWER parameters needed for historical aggregation
_POWER_HISTORICAL_PARAMS = ["precip", "solar", "temp"]

# Lookback window for satellite data (days)
_SATELLITE_LOOKBACK_DAYS = 30

# Price series lookback (days)
_PRICE_LOOKBACK_DAYS = 7


# ---------------------------------------------------------------------------
# BBCH stage estimation
# ---------------------------------------------------------------------------


def _estimate_planting_date(crop_id: str, query_date: date) -> date | None:
    """Estimate a plausible planting date for the given crop and query date.

    Uses typical planting windows for Argentina's Pampa Húmeda:
      - Soy: mid-October
      - Corn: mid-September

    Returns None if the crop is not recognised.
    """
    if crop_id == "soy":
        # Soy planting: Oct 15. If query is before Aug, use previous year's season.
        season_year = query_date.year if query_date.month >= 8 else query_date.year - 1
        return date(season_year, 10, 15)
    if crop_id == "corn":
        # Corn planting: Sep 15. Similar season logic.
        season_year = query_date.year if query_date.month >= 8 else query_date.year - 1
        return date(season_year, 9, 15)
    return None


def _estimate_bbch_stage(
    crop_id: str, query_date: date, stages: list[GrowthStage], growing_season_days: int
) -> dict | None:
    """Estimate the current BBCH growth stage based on estimated planting date.

    Uses a proportional heuristic: days since estimated planting / growing_season_days
    maps to a stage index in the ordered stage list.
    """
    planting_date = _estimate_planting_date(crop_id, query_date)
    if planting_date is None or not stages:
        return None

    days_since_planting = (query_date - planting_date).days

    # Clamp to the valid growing season window
    if days_since_planting < 0:
        # Before planting — return the first (seed) stage
        return _stage_to_dict(stages[0])
    if days_since_planting >= growing_season_days:
        # Past maturity — return the last stage
        return _stage_to_dict(stages[-1])

    # Proportional: pick the stage at fraction * len(stages)
    fraction = days_since_planting / growing_season_days
    stage_index = int(fraction * len(stages))
    stage_index = min(stage_index, len(stages) - 1)

    return _stage_to_dict(stages[stage_index])


def _stage_to_dict(stage: GrowthStage) -> dict:
    """Convert a GrowthStage to the public dict shape for the analysis response."""
    return {
        "bbch_code": stage.bbch_code,
        "name": stage.name,
        "kc": stage.kc,
        "water_stress_sensitivity": stage.water_stress_sensitivity,
    }


# ---------------------------------------------------------------------------
# Historical aggregation (POWER → summary)
# ---------------------------------------------------------------------------


def _aggregate_historical(power_data: dict) -> dict:
    """Compute precipitation sum, solar avg, and temp avg from POWER daily series.

    Expects the raw POWER response dict (already normalised), not a PowerResponse model.
    Handles None values (missing data) by skipping them in averages.
    """
    parameters: list[dict] = power_data.get("parameters", [])

    result: dict = {
        "precipitation_15d_mm": 0.0,
        "solar_radiation_avg": 0.0,
        "temp_avg_15d": 0.0,
    }

    for param in parameters:
        name = param.get("name", "")
        values: list = param.get("values", [])
        # Filter out None
        clean = [v for v in values if v is not None]

        if not clean:
            continue

        if name == "PRECTOTCORR":
            result["precipitation_15d_mm"] = round(sum(clean), 1)
        elif name == "ALLSKY_SFC_SW_DWN":
            result["solar_radiation_avg"] = round(sum(clean) / len(clean), 1)
        elif name == "T2M":
            result["temp_avg_15d"] = round(sum(clean) / len(clean), 1)

    return result


# ---------------------------------------------------------------------------
# Economy helpers
# ---------------------------------------------------------------------------


def _crop_to_product_id(crop: str) -> int | None:
    """Map a crop ID string to MAGyP numeric product ID.

    Returns None for unknown crops (caller decides whether to skip the module).
    """
    return _CROP_PRODUCT_MAP.get(crop.lower())


def _extract_latest_price(raw: dict) -> dict | None:
    """Extract the most recent price entry from a PriceSeriesResponse dict."""
    promedios = raw.get("promedios", [])
    if not promedios:
        return None
    latest = promedios[-1]
    modal_list = raw.get("modal", [])
    return {
        "fecha": latest.get("fecha"),
        "promedio": latest.get("valor"),
        "modal": modal_list[0].get("valor") if modal_list else None,
    }


def _extract_price_series(raw: dict) -> list[dict]:
    """Extract weekly price series (last 7 days) from a PriceSeriesResponse dict."""
    minimos = raw.get("minimos", [])[-_PRICE_LOOKBACK_DAYS:]
    maximos = raw.get("maximos", [])[-_PRICE_LOOKBACK_DAYS:]
    promedios = raw.get("promedios", [])[-_PRICE_LOOKBACK_DAYS:]

    # Build date-indexed dict
    date_map: dict[str, dict] = {}
    for entry in promedios:
        fecha = entry.get("fecha", "")
        if fecha:
            date_map[fecha] = {"fecha": fecha, "promedio": entry.get("valor")}

    for entry in minimos:
        fecha = entry.get("fecha", "")
        if fecha in date_map:
            date_map[fecha]["minimo"] = entry.get("valor")

    for entry in maximos:
        fecha = entry.get("fecha", "")
        if fecha in date_map:
            date_map[fecha]["maximo"] = entry.get("valor")

    return sorted(date_map.values(), key=lambda x: x.get("fecha", ""))


# ---------------------------------------------------------------------------
# AnalysisOrchestrator
# ---------------------------------------------------------------------------


class AnalysisOrchestrator:
    """Orchestrates parallel data fetches across all four modules.

    Each module fetch is independent — failures in one module do not block others.
    The response meta reflects which modules contributed data and which failed.
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------

    async def gather(
        self,
        lot_id: str,
        crop: str,
        lat: float,
        lon: float,
        query_date: date,
    ) -> AnalysisResponse:
        """Execute all four module fetches in parallel and assemble the response.

        Partial failures are reflected in meta.status and meta.missing_modules.
        """
        query = AnalysisRequest(lot_id=lot_id, crop=crop, lat=lat, lon=lon, date=query_date)

        # Launch all four fetches in parallel
        agroclimate_task = self._fetch_agroclimate(lat, lon, query_date)
        satellite_task = self._fetch_satellite(lat, lon, query_date)
        agronomy_task = self._fetch_agronomy(crop, query_date)
        economy_task = self._fetch_economy(crop, query_date)

        results = await asyncio.gather(
            agroclimate_task,
            satellite_task,
            agronomy_task,
            economy_task,
            return_exceptions=True,
        )

        agroclimate, satellite, agronomy, economy = results

        # Build response sections, tracking which modules failed
        missing: list[str] = []

        agro_section = self._unwrap_or_none(agroclimate, "agroclimate", missing)
        sat_section = self._unwrap_or_none(satellite, "satellite", missing)
        agro_section_obj = self._unwrap_or_none(agronomy, "agronomy", missing)
        econ_section = self._unwrap_or_none(economy, "economy", missing)

        status = "complete" if not missing else "partial"

        return AnalysisResponse(
            query=query,
            agroclimate=agro_section,
            satellite=sat_section,
            agronomy=agro_section_obj,
            economy=econ_section,
            meta=AnalysisMeta(
                status=status,
                missing_modules=missing,
                cached_at=None,
            ),
        )

    # -----------------------------------------------------------------------
    # Module fetchers
    # -----------------------------------------------------------------------

    async def _fetch_agroclimate(
        self, lat: float, lon: float, query_date: date
    ) -> AgroclimateSection:
        """Fetch current weather and 15-day historical POWER data."""
        weather_service = WeatherService(self._redis)
        power_service = PowerService(self._redis)

        start = (query_date - timedelta(days=15)).strftime("%Y%m%d")
        end = query_date.strftime("%Y%m%d")

        weather_result, _ = await weather_service.get(lat, lon)
        power_result, _ = await power_service.get(
            lat, lon, start, end, _POWER_HISTORICAL_PARAMS
        )

        current = weather_result.model_dump(mode="json")
        historical = _aggregate_historical(power_result.model_dump(mode="json"))

        return AgroclimateSection(current=current, historical=historical)

    async def _fetch_satellite(
        self, lat: float, lon: float, query_date: date
    ) -> SatelliteSection:
        """Fetch SMAP soil moisture and Sentinel-2 optical scenes for the area.

        Uses the configured ingestion bounding box as a reasonable search window
        (1° × 1° around the point). Constructs a bbox from lat/lon with a 0.5°
        buffer in each direction.
        """
        bbox = f"{lon - 0.5},{lat - 0.5},{lon + 0.5},{lat + 0.5}"
        start_date = (query_date - timedelta(days=_SATELLITE_LOOKBACK_DAYS)).isoformat()
        end_date = query_date.isoformat()

        smap_service = SmapService()
        sentinel_service = SentinelService()

        # SMAP: use a fresh async session via the shared engine
        from argplant.shared.database import async_session

        soil_moisture: list[dict] = []
        soil_moisture_value: dict | None = None
        optical: list[dict] = []

        async with async_session() as session:
            try:
                smap_results = await smap_service.search(session, bbox, start_date, end_date)
                await session.commit()
                soil_moisture = [
                    r.model_dump(mode="json") for r in smap_results
                ]

                # Try to extract actual soil moisture value from the most recent scene
                if smap_results and settings.SATELLITE_STORAGE_PATH:
                    latest = smap_results[0]
                    filepath = (
                        Path(settings.SATELLITE_STORAGE_PATH)
                        / "smap"
                        / latest.scene_id
                    )
                    if filepath.exists():
                        pixel = read_smap_pixel(
                            str(filepath),
                            lat=lat,
                            lon=lon,
                            scene_id=latest.scene_id,
                            acquisition_date=latest.acquisition_date.isoformat(),
                        )
                        soil_moisture_value = pixel.to_dict()
                    else:
                        soil_moisture_value = {
                            "status": "not_downloaded",
                            "scene_id": latest.scene_id,
                            "message": (
                                "SMAP scene metadata available but file not downloaded. "
                                "Use POST /api/v1/satellite/sentinel/{id}/download "
                                "with the scene_id to retrieve and extract the value."
                            ),
                        }
            except Exception:
                logger.exception("SMAP search failed during analysis gather")

        async with async_session() as session:
            try:
                sentinel_results = await sentinel_service.search_catalog(
                    session,
                    platform="sentinel-2",
                    bbox=bbox,
                    start_date=start_date,
                    end_date=end_date,
                    max_cloud=20.0,
                )
                await session.commit()
                optical = [
                    r.model_dump(mode="json") for r in sentinel_results
                ]
            except Exception:
                logger.exception("Sentinel search failed during analysis gather")

        return SatelliteSection(
            soil_moisture=soil_moisture,
            soil_moisture_value=soil_moisture_value,
            optical=optical,
        )

    async def _fetch_agronomy(
        self, crop: str, query_date: date
    ) -> AgronomySection:
        """Fetch crop catalog info and estimate current BBCH stage."""
        crop_id = crop.lower()

        # Get full crop info from seed data
        crops = get_crops()
        crop_data = crops.get(crop_id)
        if crop_data is None:
            raise ValueError(f"Unknown crop: {crop}")

        # Get growth stages
        stage_list = CropCatalogService.get_stages(crop_id) or []
        growing_season_days = crop_data.get("growing_season_days", 120)

        current_stage = _estimate_bbch_stage(
            crop_id, query_date, stage_list, growing_season_days
        )

        return AgronomySection(
            crop_info={
                "id": crop_id,
                "name": crop_data["name"],
                "scientific_name": crop_data["scientific_name"],
                "growing_season_days": growing_season_days,
                "temperature": crop_data.get("temperature", {}),
            },
            current_stage=current_stage,
        )

    async def _fetch_economy(
        self, crop: str, query_date: date
    ) -> EconomySection:
        """Fetch latest grain price and 7-day series for the crop."""
        producto_id = _crop_to_product_id(crop)
        if producto_id is None:
            raise ValueError(f"No MAGyP product mapping for crop: {crop}")

        desde = query_date - timedelta(days=_PRICE_LOOKBACK_DAYS)

        price_service = PriceService(self._redis)
        result, _ = await price_service.get(producto_id, _DEFAULT_PORT, desde, query_date)
        raw = result.model_dump(mode="json")

        latest = _extract_latest_price(raw)
        series = _extract_price_series(raw)

        return EconomySection(latest_price=latest, series=series)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _unwrap_or_none(result, module_name: str, missing: list):
        """Unwrap a gather result: return value if success, None + log if exception."""
        if isinstance(result, Exception):
            logger.warning(
                "Module '%s' failed during analysis gather: %s", module_name, result
            )
            missing.append(module_name)
            return None
        return result
