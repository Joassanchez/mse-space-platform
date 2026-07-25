"""Centralized configuration via Pydantic Settings.

All values can be overridden via environment variables or a .env file.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://argplant:argplant@localhost:5432/argplant"
    )

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # OpenWeather
    OPENWEATHER_API_KEY: str = ""
    OPENWEATHER_TIMEOUT: int = 10

    # NASA POWER
    POWER_TIMEOUT: int = 15

    # Earthdata (SMAP)
    EARTHDATA_USERNAME: str = ""
    EARTHDATA_PASSWORD: str = ""

    # CDSE (Sentinel)
    CDSE_USERNAME: str = ""
    CDSE_PASSWORD: str = ""

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Storage
    SATELLITE_STORAGE_PATH: Path = Path("data/satellite")

    # Ingestion (Pergamino, Buenos Aires)
    INGESTION_COORDS_LAT: float = -33.89
    INGESTION_COORDS_LON: float = -60.57
    INGESTION_BBOX: str = "-61,-34,-60,-33"

    # Logging
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # ------------------------------------------------------------------
    # Feature flags — disable sources you don't have credentials for yet
    # ------------------------------------------------------------------
    ENABLE_OPENWEATHER: bool = True
    ENABLE_NASA_POWER: bool = True
    ENABLE_SMAP: bool = True
    ENABLE_SENTINEL: bool = True
    ENABLE_MAGYP: bool = True

    # ------------------------------------------------------------------
    # LLM / AI Provider
    # ------------------------------------------------------------------
    LLM_PROVIDER: str = "openai"  # gemini | openai | anthropic | ollama
    LLM_MODEL: str = "gpt-4o-mini"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""


# Singleton
settings = Settings()
