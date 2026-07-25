"""Integration tests for SMAP search functionality.

These tests require real EARTHDATA_USERNAME and EARTHDATA_PASSWORD
environment variables. They are skipped automatically if credentials
are not set.

Run with: pytest -m integration
"""

import pytest

from src.ingestion.smap.smap_connector import SmapConnector, SearchError
from tests.integration.conftest import skip_if_no_credentials


@pytest.mark.integration
class TestSmapSearch:
    """Test real SMAP search against NASA Earthdata."""

    def test_search_returns_results_for_valid_bbox(self):
        """Search for SMAP data in a known region should return results."""
        skip_if_no_credentials()
        connector = SmapConnector()
        connector.authenticate()

        # Use a small bbox and date range to limit results
        results = connector.search(
            bbox=[-58.5, -35.0, -58.0, -34.5],  # Buenos Aires region
            start_date="2024-01-01",
            end_date="2024-01-02",
        )

        # Results may be empty if no data exists for that date/region
        # but the search should not raise an error
        assert isinstance(results, list)

    def test_search_only_lists_results(self):
        """Search should return product metadata without downloading."""
        skip_if_no_credentials()
        connector = SmapConnector()
        connector.authenticate()

        results = connector.search(
            bbox=[-58.5, -35.0, -58.0, -34.5],
            start_date="2024-01-01",
            end_date="2024-01-02",
        )

        # Verify results have expected metadata structure
        for product in results[:1]:  # Check only first result
            metadata = connector.extract_metadata(product)
            assert "granule_id" in metadata
            assert "remote_url" in metadata
            assert "acquisition_date" in metadata
            assert "file_name" in metadata

    def test_search_with_invalid_bbox_raises_error(self):
        """Invalid bbox should raise BboxError before making network calls."""
        skip_if_no_credentials()
        connector = SmapConnector()
        from src.ingestion.smap.smap_connector import BboxError
        with pytest.raises(BboxError):
            connector.search(
                bbox=[-200.0, -35.0, -58.0, -34.5],
                start_date="2024-01-01",
                end_date="2024-01-02",
            )

    def test_search_date_range_exceeded_raises_error(self):
        """Date range exceeding max should raise DateRangeError."""
        skip_if_no_credentials()
        connector = SmapConnector(max_days_range=7)
        from src.ingestion.smap.smap_connector import DateRangeError
        with pytest.raises(DateRangeError):
            connector.search(
                bbox=[-58.5, -35.0, -58.0, -34.5],
                start_date="2024-01-01",
                end_date="2024-01-15",
            )
