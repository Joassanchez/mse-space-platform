"""Unit tests for date range validation."""

import pytest

from src.ingestion.smap.smap_connector import DateRangeError, SmapConnector


class TestDateRangeValidation:
    """Test _validate_date_range method."""

    def test_valid_range_within_default(self):
        connector = SmapConnector(max_days_range=7)
        # 5 days — within default 7
        connector._validate_date_range("2024-01-01", "2024-01-06")
        # No exception raised

    def test_valid_range_exactly_at_limit(self):
        connector = SmapConnector(max_days_range=7)
        connector._validate_date_range("2024-01-01", "2024-01-08")
        # 7 days — exactly at limit, should pass

    def test_range_exceeds_limit(self):
        connector = SmapConnector(max_days_range=7)
        with pytest.raises(DateRangeError) as exc_info:
            connector._validate_date_range("2024-01-01", "2024-01-15")
        assert "14 days exceeds maximum of 7 days" in str(exc_info.value)

    def test_custom_max_days_range(self):
        connector = SmapConnector(max_days_range=14)
        # 10 days — within custom 14
        connector._validate_date_range("2024-01-01", "2024-01-11")

    def test_custom_max_days_range_exceeded(self):
        connector = SmapConnector(max_days_range=14)
        with pytest.raises(DateRangeError) as exc_info:
            connector._validate_date_range("2024-01-01", "2024-01-20")
        assert "19 days exceeds maximum of 14 days" in str(exc_info.value)

    def test_end_date_before_start_date(self):
        connector = SmapConnector(max_days_range=7)
        with pytest.raises(DateRangeError) as exc_info:
            connector._validate_date_range("2024-01-10", "2024-01-01")
        assert "must be after" in str(exc_info.value)

    def test_same_day_range(self):
        connector = SmapConnector(max_days_range=7)
        connector._validate_date_range("2024-01-01", "2024-01-01")
        # 0 days — valid

    def test_error_includes_configured_limit(self):
        """Error message must include the current configured limit value."""
        connector = SmapConnector(max_days_range=30)
        with pytest.raises(DateRangeError) as exc_info:
            connector._validate_date_range("2024-01-01", "2024-02-01")
        assert "30 days" in str(exc_info.value)


class TestBboxValidation:
    """Test _validate_bbox method."""

    def test_valid_bbox(self):
        connector = SmapConnector()
        connector._validate_bbox([-58.5, -35.0, -58.0, -34.5])

    def test_invalid_bbox_wrong_length(self):
        connector = SmapConnector()
        from src.ingestion.smap.smap_connector import BboxError
        with pytest.raises(BboxError, match="4 values"):
            connector._validate_bbox([-58.5, -35.0])

    def test_invalid_bbox_lon_range(self):
        connector = SmapConnector()
        from src.ingestion.smap.smap_connector import BboxError
        with pytest.raises(BboxError, match="min_lon"):
            connector._validate_bbox([-200.0, -35.0, -58.0, -34.5])

    def test_invalid_bbox_lat_range(self):
        connector = SmapConnector()
        from src.ingestion.smap.smap_connector import BboxError
        with pytest.raises(BboxError, match="min_lat"):
            connector._validate_bbox([-58.5, -100.0, -58.0, -34.5])

    def test_valid_bbox_full_globe(self):
        connector = SmapConnector()
        connector._validate_bbox([-180.0, -90.0, 180.0, 90.0])
