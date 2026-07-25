"""ARGPLANT Data Service API — FastAPI application entry point.

Aggregates agroclimatic, satellite, agronomic, and economic data
for Argentina's Pampa Húmeda agricultural region.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from argplant.shared.config import settings
from argplant.shared.database import engine
from argplant.shared.middleware import RateLimiterMiddleware

logger = logging.getLogger("argplant")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle for the FastAPI application."""
    # Startup: verify DB connectivity, seed data loading will be added per module
    logger.info("ARGPLANT Data Service starting up")
    logger.info("Log level: %s", settings.LOG_LEVEL)

    # Load seed data for agronomy and economy modules
    from argplant.modules.agronomy.seed_data import load_agronomy_seeds
    from argplant.modules.economy.seed_data import load_economy_seeds

    load_agronomy_seeds()
    load_economy_seeds()

    yield

    # Shutdown: dispose engine and cleanup
    logger.info("ARGPLANT Data Service shutting down")
    await engine.dispose()


app = FastAPI(
    title="ARGPLANT Data Service API",
    description=(
        "Unified agroclimatic, satellite, and economic data API "
        "for Argentina's Pampa Húmeda. "
        "Serves as the data ingestion layer for the ARGPLANT AI pipeline."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiter
app.add_middleware(RateLimiterMiddleware)


@app.get("/health", tags=["system"])
async def health_check() -> JSONResponse:
    """Health check endpoint. Returns 200 when the service is running."""
    return JSONResponse(content={"status": "ok"})


@app.get("/", tags=["system"])
async def dashboard() -> FileResponse:
    """Serve the ARGPLANT AI dashboard."""
    return FileResponse("static/index.html")


# Static frontend — served at root
app.mount("/static", StaticFiles(directory="static"), name="static")

# Router mounts
from argplant.modules.agroclimate.router import router as agroclimate_router
from argplant.modules.agronomy.router import router as agronomy_router
from argplant.modules.economy.router import router as economy_router
from argplant.modules.satellite.router import router as satellite_router

from argplant.modules.ingestion.router import router as ingestion_router
from argplant.modules.analysis.router import router as analysis_router
from argplant.modules.model.router import router as model_router
from argplant.modules.communication.router import router as communication_router
from argplant.modules.communication.chat_router import router as chat_router

app.include_router(agroclimate_router, prefix="/api/v1/agroclimate")
app.include_router(agronomy_router, prefix="/api/v1/agronomy")
app.include_router(economy_router, prefix="/api/v1/economy")
app.include_router(satellite_router, prefix="/api/v1/satellite")
app.include_router(ingestion_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(model_router, prefix="/api/v1")
app.include_router(communication_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
