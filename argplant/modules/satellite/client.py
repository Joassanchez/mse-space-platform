"""HTTP clients for Earthdata (SMAP) and CDSE (Sentinel) catalog APIs.

Both clients use httpx.AsyncClient. CdseClient manages OAuth2 token refresh.
"""

import logging
import time
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from argplant.shared.config import settings

logger = logging.getLogger("argplant.satellite")

# ---------------------------------------------------------------------------
# Retry policy — reused across clients
# ---------------------------------------------------------------------------

_RETRY_POLICY = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=1, max=8),
    "retry": retry_if_exception_type(httpx.HTTPStatusError),
}

# ---------------------------------------------------------------------------
# Earthdata / CMR (SMAP)
# ---------------------------------------------------------------------------

_CMR_BASE = "https://cmr.earthdata.nasa.gov"
_EDL_TOKEN_URL = "https://urs.earthdata.nasa.gov/api/users/token"

# SMAP Level-3 Radiometer Global Daily 36 km EASE-Grid Soil Moisture
_SMAP_SHORT_NAME = "SPL3SMP_E"


class EarthdataClient:
    """Async HTTP client for the NASA CMR granules API (SMAP metadata search)."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None
        self._token: str | None = None
        self._token_expiry: float = 0.0

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    async def _fetch_edl_token(self) -> str:
        """Acquire an EDL bearer token using EARTHDATA_USERNAME/PASSWORD."""
        if not settings.EARTHDATA_USERNAME or not settings.EARTHDATA_PASSWORD:
            logger.warning("Earthdata credentials not configured — searching unauthenticated")
            return ""

        client = await self._ensure_client()
        resp = await client.post(
            _EDL_TOKEN_URL,
            auth=(settings.EARTHDATA_USERNAME, settings.EARTHDATA_PASSWORD),
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data.get("access_token", "")
        # Token typically expires in 1 hour; add a 60s buffer.
        self._token_expiry = time.monotonic() + 3600 - 60
        return self._token

    async def _get_token(self) -> str:
        """Return a valid EDL token, refreshing if expired."""
        if self._token and time.monotonic() < self._token_expiry:
            return self._token
        return await self._fetch_edl_token()

    # ------------------------------------------------------------------
    # SMAP search
    # ------------------------------------------------------------------

    @retry(**_RETRY_POLICY)
    async def search_smap(
        self,
        bbox: str,
        start_date: str,
        end_date: str,
        *,
        page_size: int = 50,
    ) -> list[dict[str, Any]]:
        """Search SMAP L3 soil moisture granules via the CMR API.

        Args:
            bbox: ``min_lon,min_lat,max_lon,max_lat`` string.
            start_date: ISO-8601 start (inclusive).
            end_date: ISO-8601 end (inclusive).
            page_size: Max granules per page.

        Returns a list of raw granule metadata dicts.
        """
        client = await self._ensure_client()

        headers: dict[str, str] = {"Accept": "application/json"}
        token = await self._get_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        params: dict[str, str | int] = {
            "short_name": _SMAP_SHORT_NAME,
            "bounding_box": bbox,
            "temporal": f"{start_date}T00:00:00Z,{end_date}T23:59:59Z",
            "page_size": page_size,
        }

        resp = await client.get(
            f"{_CMR_BASE}/search/granules.json",
            params=params,
            headers=headers,
        )
        resp.raise_for_status()
        body = resp.json()

        entries: list[dict[str, Any]] = body.get("feed", {}).get("entry", [])
        # Wrap single-entry responses
        if isinstance(entries, dict):
            entries = [entries]
        return entries


# ---------------------------------------------------------------------------
# CDSE (Sentinel)
# ---------------------------------------------------------------------------

_CDSE_TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
    "protocol/openid-connect/token"
)
_CDSE_STAC_URL = "https://catalogue.dataspace.copernicus.eu/stac/search"


class CdseClient:
    """Async HTTP client for Copernicus Data Space Ecosystem STAC API.

    Handles OAuth2 token refresh and Sentinel catalog search.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None
        self._token: str | None = None
        self._token_expiry: float = 0.0

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # OAuth2 token
    # ------------------------------------------------------------------

    async def _fetch_cdse_token(self) -> str:
        """Acquire an OAuth2 token via client-credentials grant."""
        if not settings.CDSE_USERNAME or not settings.CDSE_PASSWORD:
            logger.warning("CDSE credentials not configured")
            return ""

        client = await self._ensure_client()
        resp = await client.post(
            _CDSE_TOKEN_URL,
            data={
                "grant_type": "password",
                "username": settings.CDSE_USERNAME,
                "password": settings.CDSE_PASSWORD,
                "client_id": "cdse-public",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        # Token expires_in is in seconds; add a 60s buffer.
        expires_in = int(data.get("expires_in", 600))
        self._token_expiry = time.monotonic() + expires_in - 60
        return self._token

    async def _get_token(self) -> str:
        """Return a valid CDSE token, refreshing if expired."""
        if self._token and time.monotonic() < self._token_expiry:
            return self._token
        return await self._fetch_cdse_token()

    # ------------------------------------------------------------------
    # Sentinel catalog search
    # ------------------------------------------------------------------

    @retry(**_RETRY_POLICY)
    async def search_sentinel(
        self,
        bbox: str,
        start_date: str,
        end_date: str,
        platform: str,
        max_cloud: float | None = None,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search Sentinel-1/2 scenes via CDSE STAC API.

        Args:
            bbox: ``min_lon,min_lat,max_lon,max_lat`` string.
            start_date: ISO-8601 start (inclusive).
            end_date: ISO-8601 end (inclusive).
            platform: ``sentinel-1`` or ``sentinel-2``.
            max_cloud: Maximum cloud cover percentage (S2 only).
            limit: Max features per page.

        Returns a list of raw STAC Item dicts.
        """
        token = await self._get_token()
        if not token:
            raise RuntimeError("CDSE token not available — check CDSE_USERNAME/PASSWORD")

        client = await self._ensure_client()

        # Map platform to STAC collection
        collection_map = {
            "sentinel-1": "sentinel-1-grd",
            "sentinel-2": "sentinel-2-l2a",
        }
        collection = collection_map.get(platform, platform)

        # Parse bbox string → list
        coords = [float(x.strip()) for x in bbox.split(",")]
        if len(coords) != 4:
            raise ValueError("bbox must contain exactly 4 values: min_lon,min_lat,max_lon,max_lat")

        body: dict[str, Any] = {
            "collections": [collection],
            "bbox": coords,
            "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
            "limit": limit,
        }

        if max_cloud is not None and platform == "sentinel-2":
            body["query"] = {"eo:cloud_cover": {"lte": max_cloud}}

        resp = await client.post(
            _CDSE_STAC_URL,
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/geo+json",
            },
        )
        resp.raise_for_status()
        geojson = resp.json()
        return geojson.get("features", [])

    # ------------------------------------------------------------------
    # Download (placeholder — Phase 5 wires full pipeline)
    # ------------------------------------------------------------------

    async def download(
        self,
        scene_id: str,
        download_url: str,
    ) -> bytes:
        """Download a Sentinel scene file as raw bytes.

        In Phase 5 this integrates with the CDSE OData / download API.
        """
        token = await self._get_token()
        if not token:
            raise RuntimeError("CDSE token not available")

        client = await self._ensure_client()
        resp = await client.get(
            download_url,
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.content
