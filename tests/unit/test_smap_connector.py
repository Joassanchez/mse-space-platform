"""Unit tests for SMAP connector with mocked earthaccess.

No network calls — all earthaccess interactions are mocked.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.smap.smap_connector import (
    AuthenticationError,
    BboxError,
    DateRangeError,
    SearchError,
    SmapConnector,
)


class TestSmapConnectorAuth:
    """Test authentication logic."""

    def test_auth_missing_credentials(self):
        connector = SmapConnector()
        # Ensure no credentials in environment
        old_user = os.environ.pop("EARTHDATA_USERNAME", None)
        old_pass = os.environ.pop("EARTHDATA_PASSWORD", None)
        try:
            with pytest.raises(AuthenticationError, match="environment variables are required"):
                connector.authenticate()
        finally:
            if old_user:
                os.environ["EARTHDATA_USERNAME"] = old_user
            if old_pass:
                os.environ["EARTHDATA_PASSWORD"] = old_pass

    @patch("earthaccess.login")
    def test_auth_success(self, mock_login):
        mock_login.return_value = True
        connector = SmapConnector()
        os.environ["EARTHDATA_USERNAME"] = "test_user"
        os.environ["EARTHDATA_PASSWORD"] = "test_pass"
        try:
            result = connector.authenticate()
            assert result is True
            mock_login.assert_called_once_with(strategy="environment")
        finally:
            os.environ.pop("EARTHDATA_USERNAME", None)
            os.environ.pop("EARTHDATA_PASSWORD", None)

    @patch("earthaccess.login")
    def test_auth_failure(self, mock_login):
        mock_login.return_value = False
        connector = SmapConnector()
        os.environ["EARTHDATA_USERNAME"] = "test_user"
        os.environ["EARTHDATA_PASSWORD"] = "wrong_pass"
        try:
            with pytest.raises(AuthenticationError, match="authentication failed"):
                connector.authenticate()
        finally:
            os.environ.pop("EARTHDATA_USERNAME", None)
            os.environ.pop("EARTHDATA_PASSWORD", None)

    @patch("earthaccess.login")
    def test_auth_exception(self, mock_login):
        mock_login.side_effect = Exception("Network error")
        connector = SmapConnector()
        os.environ["EARTHDATA_USERNAME"] = "test_user"
        os.environ["EARTHDATA_PASSWORD"] = "test_pass"
        try:
            with pytest.raises(AuthenticationError, match="Network error"):
                connector.authenticate()
        finally:
            os.environ.pop("EARTHDATA_USERNAME", None)
            os.environ.pop("EARTHDATA_PASSWORD", None)


class TestSmapConnectorSearch:
    """Test search logic with mocked earthaccess."""

    @patch("earthaccess.search_data")
    def test_search_returns_results(self, mock_search):
        mock_search.return_value = [{"umm": {"GranuleUR": "test_granule"}}]
        connector = SmapConnector()
        results = connector.search(
            bbox=[-58.5, -35.0, -58.0, -34.5],
            start_date="2024-01-01",
            end_date="2024-01-07",
        )
        assert len(results) == 1
        mock_search.assert_called_once()

    @patch("earthaccess.search_data")
    def test_search_empty_results(self, mock_search):
        mock_search.return_value = []
        connector = SmapConnector()
        results = connector.search(
            bbox=[-58.5, -35.0, -58.0, -34.5],
            start_date="2024-01-01",
            end_date="2024-01-07",
        )
        assert results == []

    @patch("earthaccess.search_data")
    def test_search_uses_correct_product(self, mock_search):
        mock_search.return_value = []
        connector = SmapConnector()
        connector.search(
            bbox=[-58.5, -35.0, -58.0, -34.5],
            start_date="2024-01-01",
            end_date="2024-01-07",
        )
        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["short_name"] == "SPL4SMGP"
        assert call_kwargs["version"] == "008"

    def test_search_invalid_bbox(self):
        connector = SmapConnector()
        with pytest.raises(BboxError):
            connector.search(
                bbox=[-200.0, -35.0, -58.0, -34.5],
                start_date="2024-01-01",
                end_date="2024-01-07",
            )

    def test_search_date_range_exceeded(self):
        connector = SmapConnector(max_days_range=7)
        with pytest.raises(DateRangeError):
            connector.search(
                bbox=[-58.5, -35.0, -58.0, -34.5],
                start_date="2024-01-01",
                end_date="2024-01-15",
            )

    @patch("earthaccess.search_data")
    def test_search_exception_wrapped(self, mock_search):
        mock_search.side_effect = Exception("API timeout")
        connector = SmapConnector()
        with pytest.raises(SearchError, match="API timeout"):
            connector.search(
                bbox=[-58.5, -35.0, -58.0, -34.5],
                start_date="2024-01-01",
                end_date="2024-01-07",
            )


class TestSmapConnectorMetadata:
    """Test metadata extraction."""

    def test_extract_metadata_from_dict(self):
        connector = SmapConnector()
        product = {
            "umm": {
                "GranuleUR": "SPL4SMGP.008:2024.01.01T000000",
                "RelatedUrls": [
                    {
                        "Type": "GET DATA",
                        "URL": "https://example.com/data/SPL4SMGP.008_test.h5",
                    }
                ],
                "TemporalExtent": {
                    "RangeDateTime": {
                        "BeginningDateTime": "2024-01-01T12:00:00.000Z"
                    }
                },
                "DataGranule": {
                    "ArchiveAndDistributionInformation": [
                        {"Size": 50000000}
                    ]
                },
            }
        }
        metadata = connector.extract_metadata(product)
        assert metadata["granule_id"] == "SPL4SMGP.008:2024.01.01T000000"
        assert metadata["remote_url"] == "https://example.com/data/SPL4SMGP.008_test.h5"
        assert metadata["acquisition_date"] == "2024-01-01"
        assert metadata["file_name"] == "SPL4SMGP.008_test.h5"
        assert metadata["size_bytes"] == 50000000

    def test_extract_metadata_from_granule_object(self):
        connector = SmapConnector()
        # Simulate earthaccess Granule object
        mock_granule = MagicMock()
        mock_granule.umm = {
            "GranuleUR": "SPL4SMGP.008:2024.02.15T000000",
            "RelatedUrls": [
                {
                    "Type": "GET DATA",
                    "URL": "https://example.com/data/SPL4SMGP.008_feb.h5",
                }
            ],
            "TemporalExtent": {
                "RangeDateTime": {
                    "BeginningDateTime": "2024-02-15T06:30:00.000Z"
                }
            },
            "DataGranule": {
                "ArchiveAndDistributionInformation": [
                    {"Size": 75000000}
                ]
            },
        }
        metadata = connector.extract_metadata(mock_granule)
        assert metadata["granule_id"] == "SPL4SMGP.008:2024.02.15T000000"
        assert metadata["acquisition_date"] == "2024-02-15"
        assert metadata["file_name"] == "SPL4SMGP.008_feb.h5"

    def test_extract_metadata_empty_product(self):
        connector = SmapConnector()
        metadata = connector.extract_metadata({})
        assert metadata["granule_id"] == ""
        assert metadata["remote_url"] == ""
        assert metadata["acquisition_date"] == ""
        assert metadata["file_name"] == ""
        assert metadata["size_bytes"] == 0


class TestSmapConnectorValidate:
    """Test file validation."""

    def test_valid_hdf5_file(self, tmp_path):
        connector = SmapConnector()
        valid_file = tmp_path / "test.h5"
        valid_file.write_bytes(b"fake hdf5 content")
        assert connector.validate(str(valid_file)) is True

    def test_valid_hdf5_extension(self, tmp_path):
        connector = SmapConnector()
        valid_file = tmp_path / "test.hdf5"
        valid_file.write_bytes(b"fake hdf5 content")
        assert connector.validate(str(valid_file)) is True

    def test_empty_file_invalid(self, tmp_path):
        connector = SmapConnector()
        empty_file = tmp_path / "empty.h5"
        empty_file.write_bytes(b"")
        assert connector.validate(str(empty_file)) is False

    def test_nonexistent_file_invalid(self):
        connector = SmapConnector()
        assert connector.validate("/nonexistent/file.h5") is False

    def test_wrong_extension_invalid(self, tmp_path):
        connector = SmapConnector()
        wrong_file = tmp_path / "test.txt"
        wrong_file.write_bytes(b"some content")
        assert connector.validate(str(wrong_file)) is False
