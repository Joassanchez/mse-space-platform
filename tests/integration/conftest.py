"""Integration test configuration.

Provides helpers to skip integration tests when Earthdata credentials are missing.
"""

import os

import pytest


def skip_if_no_credentials():
    """Skip the test if EARTHDATA_USERNAME or EARTHDATA_PASSWORD is not set.

    Usage:
        @pytest.mark.integration
        def test_something():
            skip_if_no_credentials()
            # ... test code
    """
    username = os.getenv("EARTHDATA_USERNAME")
    password = os.getenv("EARTHDATA_PASSWORD")
    if not username or not password:
        pytest.skip(
            "Integration test skipped: EARTHDATA_USERNAME and EARTHDATA_PASSWORD "
            "environment variables are not set"
        )


def pytest_configure(config):
    """Register the integration marker."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (require Earthdata credentials)",
    )
