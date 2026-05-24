"""Geospatial integration test configuration.

Provides helpers to skip integration tests when PostgreSQL is not available.
"""

import os

import pytest


def skip_if_no_postgres():
    """Skip the test if PostgreSQL connection is not configured.

    Usage:
        @pytest.mark.integration
        def test_something():
            skip_if_no_postgres()
            # ... test code
    """
    pg_host = os.getenv("PGHOST", "localhost")
    pg_port = os.getenv("PGPORT", "5432")

    # Try to connect to verify PostgreSQL is available
    try:
        import psycopg2
        conn = psycopg2.connect(
            dbname=os.getenv("PGDATABASE", "mse_platform"),
            user=os.getenv("PGUSER", "mse_user"),
            password=os.getenv("PGPASSWORD", "mse_pass"),
            host=pg_host,
            port=int(pg_port),
            connect_timeout=5,
        )
        conn.close()
    except Exception:
        pytest.skip(
            "Integration test skipped: PostgreSQL not available. "
            "Set PGHOST, PGDATABASE, PGUSER, PGPASSWORD environment variables."
        )


def skip_if_no_hdf5():
    """Skip the test if the real HDF5 file is not available."""
    hdf5_path = "data/raw/smap/2023/12/SMAP_L4_SM_gph_20231231T223000_Vv8010_001.h5"
    if not os.path.exists(hdf5_path):
        pytest.skip(
            f"Integration test skipped: HDF5 file not found at {hdf5_path}"
        )
