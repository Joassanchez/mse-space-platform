"""Unit tests for WeatherSnapshotRepo domain model."""

from src.weather.domain.models import WeatherSnapshot


class TestWeatherSnapshot:
    def test_create_minimal(self):
        snap = WeatherSnapshot(region_id=1, observed_at="2026-05-24T12:00:00Z")
        assert snap.region_id == 1
        assert snap.temp_celsius is None
        assert snap.source == "openweather"

    def test_create_full(self):
        snap = WeatherSnapshot(
            region_id=1,
            observed_at="2026-05-24T12:00:00Z",
            temp_celsius=25.0,
            humidity_pct=60,
            wind_speed_ms=4.0,
            rainfall_mm=0.0,
            pressure_hpa=1013,
            weather_condition="clear",
            source="openweather",
            metadata={"lat": -31.4},
        )
        assert snap.temp_celsius == 25.0
        assert snap.humidity_pct == 60
        assert snap.weather_condition == "clear"
