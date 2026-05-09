from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str = ""
    owner_tg_id: int = 0
    base_currency: str = "USD"
    timezone: str = "UTC"
    db_url: str = "sqlite+aiosqlite:///./finance.db"
    public_https_url: str = ""
    log_level: str = "INFO"
    openrouter_api_key: str = ""

@lru_cache
def get_settings() -> Settings:
    return Settings()
