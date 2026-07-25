"""arq background job for async Sentinel scene downloads.

This module provides the ``download_sentinel`` job function. It will be
registered in the arq WorkerSettings during Phase 5 (ingestion pipeline).
"""

import logging
from pathlib import Path
from typing import Any

from argplant.modules.satellite.client import CdseClient
from argplant.modules.satellite.repository import SatelliteSceneRepo
from argplant.shared.config import settings
from argplant.shared.database import async_session
from argplant.shared.storage import LocalStorage

logger = logging.getLogger("argplant.satellite.tasks")

# CDSE OData download endpoint template
_ODATA_DOWNLOAD = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products({scene_id})/$value"

# Maximum retries handled by arq (configured in WorkerSettings at Phase 5)
_MAX_RETRIES = 3


async def download_sentinel(ctx: dict[str, Any], scene_id: str) -> dict[str, Any]:
    """Download a Sentinel scene file and persist to local storage.

    This function is invoked by arq when a download job is picked up.
    The ``ctx`` dict provides arq context (e.g. ``ctx["redis"]``).

    Lifecycle:
    1. Look up scene metadata from the DB.
    2. Construct the CDSE OData download URL.
    3. Stream the product archive via CdseClient.
    4. Save to ``data/satellite/{platform}/{scene_id}/`` via StorageBackend.
    5. Update the scene's ``file_path`` in the DB.
    6. Return result dict.

    On failure, arq retries up to ``_MAX_RETRIES`` times. After that the
    job moves to the dead-letter queue (configured in Phase 5 WorkerSettings).
    """
    cdse = CdseClient()
    storage = LocalStorage(settings.SATELLITE_STORAGE_PATH)
    repo = SatelliteSceneRepo()

    # 1. Look up scene
    async with async_session() as session:
        try:
            scene = await repo.find_by_scene_id(session, scene_id)
            if scene is None:
                return {"status": "failed", "error": f"Scene {scene_id} not found"}

            # 2. Construct download URL
            download_url = _ODATA_DOWNLOAD.format(scene_id=scene_id)

            # 3. Download raw bytes
            logger.info("Downloading %s from CDSE …", scene_id)
            data = await cdse.download(scene_id, download_url)

            # 4. Save to local storage
            dest_path = f"{scene.platform}/{scene_id}/product.zip"
            saved = await storage.save(dest_path, data)
            logger.info("Saved %s → %s", scene_id, saved)

            # 5. Update file_path in DB
            await repo.update_file_path(session, scene_id, str(saved))
            await session.commit()

            return {
                "status": "completed",
                "file_path": str(saved),
                "size_bytes": len(data),
            }
        except Exception as exc:
            logger.exception("Download failed for scene %s: %s", scene_id, exc)
            raise
        finally:
            await cdse.close()
