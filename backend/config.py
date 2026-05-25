"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """FastAPI application settings from environment variables."""

    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/1"
    API_KEY: str
    ALLOWED_ORIGINS: str = "*"
    CACHE_TTL_DEFAULT: int = 300

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse comma-separated ALLOWED_ORIGINS into a list."""
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    def __repr__(self) -> str:
        return (
            f"Settings(DATABASE_URL={self.DATABASE_URL!r}, "
            f"REDIS_URL={self.REDIS_URL!r}, "
            f"API_KEY={'*' * 8}, "
            f"ALLOWED_ORIGINS={self.ALLOWED_ORIGINS!r}, "
            f"CACHE_TTL_DEFAULT={self.CACHE_TTL_DEFAULT})"
        )


config = Settings()
