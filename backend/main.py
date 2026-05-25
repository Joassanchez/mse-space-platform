"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.config import config
from backend.db.session import async_engine, close_engine
from backend.api.v1.router import v1_router
from backend.core.ws_manager import ws_manager

logger = logging.getLogger("backend")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    # Startup
    logger.info("Backend starting up — connecting to PostgreSQL and Redis")
    # Connections are established lazily by SQLAlchemy/redis-py.
    # Eager health checks can be added here when needed.
    yield
    # Shutdown
    logger.info("Backend shutting down — disconnecting from PostgreSQL and Redis")
    await close_engine()
    from backend.core.cache import close_cache
    await close_cache()


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI app."""
    app = FastAPI(
        title="MSE Space Platform — Backend API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoints (exempt from auth)
    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness probe — returns OK if the app is running."""
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        """Readiness probe — verifies DB connectivity."""
        try:
            from backend.db.session import async_engine
            conn = await async_engine.connect()
            await conn.close()
            return {"status": "ready", "database": "connected"}
        except Exception as e:
            from fastapi import Response
            return Response(
                content=f'{{"status":"unavailable","database":"{e}"}}',
                status_code=503,
                media_type="application/json",
            )

    # Include v1 API router (auth enforced at router level)
    app.include_router(v1_router)

    # WebSocket endpoint for real-time job updates (no auth — WS uses path-based routing)
    @app.websocket("/ws/jobs/{job_id}")
    async def job_websocket(websocket: WebSocket, job_id: str):
        """Real-time job progress via WebSocket."""
        await ws_manager.connect(websocket, job_id)
        try:
            await websocket.send_json({"event": "connected", "job_id": job_id})
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_json({"event": "pong"})
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket, job_id)
        except Exception:
            ws_manager.disconnect(websocket, job_id)

    return app


app = create_app()
