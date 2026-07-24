"""ARGPLANT Data Service API — FastAPI application entry point.

Aggregates agroclimatic, satellite, agronomic, and economic data
for Argentina's Pampa Húmeda agricultural region.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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

    # Placeholder: seed data loading is added as modules are implemented
    # from argplant.modules.agronomy.seed_data import load_agronomy_seeds
    # from argplant.modules.economy.seed_data import load_economy_seeds
    # load_agronomy_seeds()
    # load_economy_seeds()

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


# Router mounts — uncommented as modules are implemented
from argplant.modules.agroclimate.router import router as agroclimate_router

# from argplant.modules.satellite.router import router as satellite_router
# from argplant.modules.agronomy.router import router as agronomy_router
# from argplant.modules.economy.router import router as economy_router
# from argplant.modules.ingestion.router import router as ingestion_router

app.include_router(agroclimate_router, prefix="/api/v1/agroclimate")
# app.include_router(satellite_router, prefix="/api/v1/satellite")
# app.include_router(agronomy_router, prefix="/api/v1/agronomy")
# app.include_router(economy_router, prefix="/api/v1/economy")
# app.include_router(ingestion_router, prefix="/api/v1")
