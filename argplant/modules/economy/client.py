"""HTTP client for MAGyP Monitor de Granos price API."""

import json
import logging
from datetime import date

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger("argplant.economy")

MAGYP_PRICES_URL = (
    "https://monitorsiogranos.magyp.gob.ar/v5_ajax/cuadrosCotizaciones_min.php"
)
TIMEOUT_SECONDS = 10
RETRY_ATTEMPTS = 3


def _is_retryable(exception: BaseException) -> bool:
    """Only retry on 5xx and network errors, not on 4xx."""
    if isinstance(exception, httpx.HTTPStatusError):
        return 500 <= exception.response.status_code < 600
    return isinstance(exception, httpx.NetworkError)


class MagypClient:
    """Fetches daily grain price series from MAGyP Monitor de Granos.

    Uses httpx.AsyncClient with tenacity retry on transient errors.
    """

    def __init__(self, timeout: int = TIMEOUT_SECONDS) -> None:
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    async def fetch(
        self, producto_id: int, puerto_id: int, desde: date, hasta: date
    ) -> dict:
        """Fetch price series from MAGyP and return the raw JSON response.

        Args:
            producto_id: Numeric MAGyP product code (e.g. 18 = soy).
            puerto_id: Numeric MAGyP port code (e.g. 23 = Rosario).
            desde: Start date (inclusive).
            hasta: End date (inclusive).

        Returns:
            Raw dict with 'minimos', 'maximos', 'promedios', 'modal' keys.
        """
        payload = {
            "fechaDesde": desde.strftime("%d/%m/%Y"),
            "fechaHasta": hasta.strftime("%d/%m/%Y"),
            "producto": str(producto_id),
            "puerto": str(puerto_id),
        }
        form_data = {"cosas": json.dumps(payload)}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(MAGYP_PRICES_URL, data=form_data)
            response.raise_for_status()

        data = response.json()
        logger.info(
            "MAGyP: fetched prices for producto=%d puerto=%d range=%s-%s (%d records)",
            producto_id,
            puerto_id,
            desde.isoformat(),
            hasta.isoformat(),
            len(data.get("minimos", [])),
        )
        return data
