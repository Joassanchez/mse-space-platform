"""WebSocket connection manager for real-time job updates.

Manages per-job channels. Each job gets its own channel keyed by job_id.
Supports broadcast_to_job() for the AI Core to push status updates.
"""

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("backend.ws")


class ConnectionManager:
    """Manages WebSocket connections grouped by job_id."""

    def __init__(self) -> None:
        self._channels: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, job_id: str) -> None:
        """Accept a WebSocket and register it on a job channel."""
        await websocket.accept()
        if job_id not in self._channels:
            self._channels[job_id] = []
        self._channels[job_id].append(websocket)
        logger.info("WS connected: job=%s, total=%d", job_id, len(self._channels[job_id]))

    def disconnect(self, websocket: WebSocket, job_id: str) -> None:
        """Remove a WebSocket from its job channel."""
        if job_id in self._channels:
            self._channels[job_id] = [
                ws for ws in self._channels[job_id] if ws != websocket
            ]
            if not self._channels[job_id]:
                del self._channels[job_id]
        logger.info("WS disconnected: job=%s", job_id)

    async def broadcast_to_job(self, job_id: str, event: str, data: dict[str, Any]) -> None:
        """Send an event to all connected clients for a specific job."""
        if job_id not in self._channels:
            return
        payload = json.dumps({"event": event, **data}, default=str)
        stale = []
        for ws in self._channels[job_id]:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws, job_id)

    @property
    def active_connections(self) -> int:
        """Return total active WebSocket connections across all channels."""
        return sum(len(ws_list) for ws_list in self._channels.values())


# Singleton
ws_manager = ConnectionManager()
