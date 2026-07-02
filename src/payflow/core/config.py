from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "payflow-p2p"
    app_env: str = "local"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://payflow:payflow@localhost:5432/payflow"


settings = Settings()
