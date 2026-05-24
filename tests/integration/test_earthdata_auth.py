"""Integration tests for Earthdata authentication.

These tests require real EARTHDATA_USERNAME and EARTHDATA_PASSWORD
environment variables. They are skipped automatically if credentials
are not set.

Run with: pytest -m integration
"""

import os

import pytest

from src.ingestion.smap.smap_connector import AuthenticationError, SmapConnector
from tests.integration.conftest import skip_if_no_credentials


@pytest.mark.integration
class TestEarthdataAuth:
    """Test real Earthdata authentication."""

    def test_auth_with_valid_credentials(self):
        """Verify that valid credentials authenticate successfully."""
        skip_if_no_credentials()
        connector = SmapConnector()
        result = connector.authenticate()
        assert result is True

    def test_auth_with_invalid_credentials(self):
        """Verify that invalid credentials raise AuthenticationError."""
        import earthaccess as _ea

        # Reset earthaccess auth so it doesn't reuse previous session
        _ea._auth = _ea.Auth()

        old_user = os.environ.get("EARTHDATA_USERNAME")
        old_pass = os.environ.get("EARTHDATA_PASSWORD")
        try:
            os.environ["EARTHDATA_USERNAME"] = "invalid_user_12345"
            os.environ["EARTHDATA_PASSWORD"] = "invalid_pass_12345"
            connector = SmapConnector()
            with pytest.raises(AuthenticationError):
                connector.authenticate()
        finally:
            # Restore original credentials
            if old_user:
                os.environ["EARTHDATA_USERNAME"] = old_user
            else:
                os.environ.pop("EARTHDATA_USERNAME", None)
            if old_pass:
                os.environ["EARTHDATA_PASSWORD"] = old_pass
            else:
                os.environ.pop("EARTHDATA_PASSWORD", None)
