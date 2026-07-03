"""Конфигурация приложения и загрузка настроек окружения."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Хранит настройки приложения, загруженные из окружения и `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "payflow-p2p"
    app_env: str = "local"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://payflow:payflow@localhost:5432/payflow"
    jwt_secret_key: str = "change-me-in-environment-for-local-development-only"
    jwt_algorithm: str = "HS256"
    jwt_access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30


settings = Settings()
