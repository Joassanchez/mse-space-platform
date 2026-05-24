"""Shared PostgreSQL connection helper.

Centralizes database connection logic for all geospatial repositories.
Replaces the private _get_connection() in postgres_repositories.py.
"""

import os

try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


def get_connection():
    """Get a PostgreSQL connection from environment config.

    Returns:
        psycopg2 connection.

    Raises:
        RuntimeError: If psycopg2 is not installed.
        psycopg2.OperationalError: If connection fails.
    """
    if not HAS_PSYCOPG2:
        raise RuntimeError(
            "psycopg2 is required for PostgreSQL geospatial repositories. "
            "Install with: pip install psycopg2-binary"
        )
    return psycopg2.connect(
        dbname=os.getenv("PGDATABASE", "mse_platform"),
        user=os.getenv("PGUSER", "mse_user"),
        password=os.getenv("PGPASSWORD", "mse_pass"),
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
    )
