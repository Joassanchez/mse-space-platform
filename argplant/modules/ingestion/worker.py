"""arq WorkerSettings — entry point for the background task worker.

Start with::

    arq argplant.modules.ingestion.worker.WorkerSettings

Registers:
- ``download_sentinel`` from satellite.tasks (async scene downloads)
- ``warmup_weather_cache``, ``refresh_prices``, ``scan_satellite_catalog``
  cron jobs for scheduled daily ingestion.
"""

from arq.connections import RedisSettings
from arq.cron import cron as arq_cron

from argplant.modules.ingestion.cron import (
    refresh_prices,
    scan_satellite_catalog,
    warmup_weather_cache,
)
from argplant.modules.satellite.tasks import download_sentinel
from argplant.shared.config import settings


class WorkerSettings:
    """arq worker configuration.

    Provides the Redis connection, function registry, and cron schedule.
    """

    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)

    functions = [download_sentinel]

    cron_jobs = [
        arq_cron(warmup_weather_cache, hour=6, minute=0),
        arq_cron(refresh_prices, hour=7, minute=0),
        arq_cron(scan_satellite_catalog, hour=3, minute=0),
    ]
