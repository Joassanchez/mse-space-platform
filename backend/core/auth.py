"""API Key authentication dependency."""

from fastapi import Header, HTTPException, status

from backend.config import config


async def verify_api_key(x_api_key: str | None = Header(None)) -> str:
    """FastAPI dependency that validates the X-API-Key header.

    Returns the API key if valid. Raises 401 if missing or invalid.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )
    if x_api_key != config.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return x_api_key
