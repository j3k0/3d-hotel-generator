"""Environment-based configuration via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Server and generation settings, configurable via HOTEL_* env vars."""

    model_config = {"env_prefix": "HOTEL_"}

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["*"]
    log_level: str = "INFO"
    max_triangles: int = 200_000
