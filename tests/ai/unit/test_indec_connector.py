"""Unit tests for IndecConnector design contract."""

import pytest

from src.weather.connectors.indec_connector import IndecConnector
from src.geospatial.domain.models import Indicator


class TestContract:
    def test_fetch_raises_not_implemented(self):
        c = IndecConnector()
        with pytest.raises(NotImplementedError):
            c.fetch(region_id=1, dataset="crop_yields")

    def test_parse_csv_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            IndecConnector.parse_csv("/fake/path.csv")

    def test_to_indicator_demo(self):
        raw = {
            "region_id": 1,
            "indicator_code": "ECO_CROP_YIELD",
            "value": 4500.0,
            "unit": "kg/ha",
        }
        indicator = IndecConnector.to_indicator(raw, is_demo=True)
        assert isinstance(indicator, Indicator)
        assert indicator.indicator_code == "ECO_CROP_YIELD"
        assert indicator.value == 4500.0
        assert indicator.metadata["is_demo"] is True
        assert "DEMO" in indicator.metadata["note"]

    def test_to_indicator_real(self):
        raw = {
            "region_id": 1,
            "indicator_code": "ECO_CROP_YIELD",
            "indicator_name": "Crop Yield",
            "value": 4500.0,
            "unit": "kg/ha",
        }
        indicator = IndecConnector.to_indicator(raw, is_demo=False)
        assert indicator.metadata["is_demo"] is False
        assert indicator.metadata["note"] == ""
        assert indicator.classification == "official"
