"""Shared FastAPI dependency providers.

Re-exports database session and authentication dependencies
for convenient import in routers.
"""

from backend.core.auth import verify_api_key
from backend.db.session import get_db_session

__all__ = ["get_db_session", "verify_api_key"]
