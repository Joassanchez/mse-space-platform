"""OpenWeather API Connector.

Fetches current weather data from OpenWeather One Call API,
normalises into WeatherSnapshot, and persists via repository.

API key comes from OPENWEATHER_API_KEY env var (never hardcoded).
Follows the same desacoplado connector pattern as SmapConnector
but as a standalone class (weather is REST API, not file download).

Flows: OpenWeather API → fetch() → parse() → store() → PostgreSQL
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from src.weather.domain.models import WeatherSnapshot
from src.weather.infrastructure.weather_repo import WeatherSnapshotRepo

logger = logging.getLogger(__name__)

# Default API endpoint
DEFAULT_API_URL = "https://api.openweathermap.org/data/3.0/onecall"


class OpenWeatherConnector:
    """Connector for OpenWeather One Call API 3.0.

    Stateless: each fetch() call is independent.
    API key sourced from OPENWEATHER_API_KEY env var.
    All units are metric (Celsius, m/s, mm).
    """

    def __init__(
        self,
        repo: Optional[WeatherSnapshotRepo] = None,
        api_url: str = DEFAULT_API_URL,
    ):
        self._repo = repo or WeatherSnapshotRepo()
        self._api_url = api_url
        self._api_key: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def authenticate(self) -> bool:
        """Check that OPENWEATHER_API_KEY is set and non-empty.

        Returns:
            True if key is present, False otherwise.
        """
        self._api_key = os.getenv("OPENWEATHER_API_KEY", "").strip()
        if not self._api_key:
            logger.warning("OPENWEATHER_API_KEY not set — authentication failed")
            return False
        return True

    def fetch(
        self,
        lat: float,
        lon: float,
        region_id: int,
    ) -> Optional[WeatherSnapshot]:
        """Fetch current weather and persist as WeatherSnapshot.

        For MVP: attempts API call if key is available.
        Falls back to returning None (caller should handle gracefully).
        Tests MUST mock this method — never depend on real API.

        Args:
            lat: Latitude in decimal degrees.
            lon: Longitude in decimal degrees.
            region_id: The regions.id to associate.

        Returns:
            WeatherSnapshot if successful, None otherwise.
        """
        if not self._api_key and not self.authenticate():
            logger.warning("Cannot fetch weather: no API key configured")
            return None

        raw = self._call_api(lat, lon)
        if raw is None:
            return None

        snapshot = self._parse_response(raw, region_id, lat, lon)
        snap_id = self._repo.save(snapshot)
        snapshot.id = snap_id
        logger.info(
            f"Weather fetched and stored: region={region_id}, "
            f"temp={snapshot.temp_celsius}°C, source=openweather"
        )
        return snapshot

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call_api(self, lat: float, lon: float) -> Optional[dict[str, Any]]:
        """Execute the HTTP request to OpenWeather API.

        Uses httpx or urllib. For MVP this is a shell that raises
        NotImplementedError when called without mocking.
        Subclasses or test fixtures override this for testing.
        """
        # For MVP: this method is designed to be mocked in tests.
        # The real implementation will use:
        #   import httpx
        #   params = {"lat": lat, "lon": lon, "appid": self._api_key, "units": "metric"}
        #   resp = httpx.get(self._api_url, params=params, timeout=10)
        #   resp.raise_for_status()
        #   return resp.json()
        raise NotImplementedError(
            "OpenWeatherConnector._call_api() is not implemented for MVP. "
            "Mock this method in tests. Set OPENWEATHER_API_KEY and "
            "install httpx for real API calls."
        )

    def _parse_response(
        self, raw: dict[str, Any], region_id: int, lat: float = 0.0, lon: float = 0.0
    ) -> WeatherSnapshot:
        """Parse OpenWeather API response into a WeatherSnapshot.

        Args:
            raw: Parsed JSON response from OpenWeather One Call API.
            region_id: The regions.id to associate.
            lat: Latitude of the request (for metadata).
            lon: Longitude of the request (for metadata).

        Returns:
            Normalised WeatherSnapshot.
        """
        current = raw.get("current", {})

        return WeatherSnapshot(
            region_id=region_id,
            observed_at=datetime.now(timezone.utc).isoformat(),
            temp_celsius=current.get("temp"),
            humidity_pct=current.get("humidity"),
            wind_speed_ms=current.get("wind_speed"),
            pressure_hpa=current.get("pressure"),
            weather_condition=(
                current.get("weather", [{}])[0].get("main", "").lower()
                if current.get("weather")
                else ""
            ),
            source="openweather",
            metadata={
                "lat": lat,
                "lon": lon,
                "api_version": "3.0",
                "raw_condition": current.get("weather", [{}])[0].get("description", ""),
            },
        )
