"""Unit tests for OpenWeatherConnector."""

from unittest.mock import MagicMock, patch

import pytest

from src.weather.connectors.openweather_connector import OpenWeatherConnector
from src.weather.domain.models import WeatherSnapshot


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.save.return_value = 1
    return repo


@pytest.fixture
def connector(mock_repo):
    return OpenWeatherConnector(repo=mock_repo)


class TestAuthentication:
    def test_authenticate_with_key(self, connector):
        with patch.dict("os.environ", {"OPENWEATHER_API_KEY": "test-key-123"}):
            assert connector.authenticate() is True
            assert connector._api_key == "test-key-123"

    def test_authenticate_without_key(self, connector):
        with patch.dict("os.environ", {}, clear=True):
            assert connector.authenticate() is False
            assert connector._api_key == ""

    def test_authenticate_empty_key(self, connector):
        with patch.dict("os.environ", {"OPENWEATHER_API_KEY": ""}):
            assert connector.authenticate() is False


class TestFetch:
    def test_fetch_without_key_returns_none(self, connector):
        with patch.dict("os.environ", {}, clear=True):
            result = connector.fetch(lat=-31.4, lon=-64.2, region_id=1)
            assert result is None

    def test_fetch_mocked_api(self, connector, mock_repo):
        """Mock _call_api to return fake response."""
        with patch.dict("os.environ", {"OPENWEATHER_API_KEY": "test-key"}):
            connector._api_key = "test-key"

            fake_response = {
                "current": {
                    "temp": 22.5,
                    "humidity": 65,
                    "wind_speed": 3.2,
                    "pressure": 1013,
                    "weather": [{"main": "Clear", "description": "clear sky"}],
                }
            }

            with patch.object(connector, "_call_api", return_value=fake_response):
                result = connector.fetch(lat=-31.4, lon=-64.2, region_id=1)

                assert result is not None
                assert result.temp_celsius == 22.5
                assert result.humidity_pct == 65
                assert result.wind_speed_ms == 3.2
                assert result.pressure_hpa == 1013
                assert result.weather_condition == "clear"
                assert result.source == "openweather"
                assert result.region_id == 1
                mock_repo.save.assert_called_once()

    def test_fetch_handles_missing_weather_field(self, connector, mock_repo):
        """_call_api returns dict without 'current' key."""
        with patch.dict("os.environ", {"OPENWEATHER_API_KEY": "test-key"}):
            connector._api_key = "test-key"

            with patch.object(connector, "_call_api", return_value={}):
                result = connector.fetch(lat=-31.4, lon=-64.2, region_id=1)

                assert result is not None
                assert result.temp_celsius is None
                assert result.weather_condition == ""


class TestResponseParsing:
    def test_parse_full_response(self, connector):
        raw = {
            "current": {
                "temp": 30.0,
                "humidity": 50,
                "wind_speed": 5.0,
                "pressure": 1008,
                "weather": [{"main": "Rain", "description": "moderate rain"}],
            }
        }
        snap = connector._parse_response(raw, region_id=1, lat=-31.4, lon=-64.2)
        assert snap.temp_celsius == 30.0
        assert snap.humidity_pct == 50
        assert snap.wind_speed_ms == 5.0
        assert snap.pressure_hpa == 1008
        assert snap.weather_condition == "rain"
        assert snap.source == "openweather"
        assert snap.metadata["lat"] == -31.4

    def test_parse_empty_current(self, connector):
        raw = {"current": {}}
        snap = connector._parse_response(raw, region_id=1)
        assert snap.temp_celsius is None
        assert snap.humidity_pct is None
        assert snap.weather_condition == ""


class TestContract:
    def test_connector_name(self, connector):
        assert hasattr(connector, "authenticate")
        assert hasattr(connector, "fetch")
        assert callable(connector.authenticate)
        assert callable(connector.fetch)
