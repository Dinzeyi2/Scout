from functools import lru_cache
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Scout Backend"
    database_url: str = Field("sqlite:///./scout.db", validation_alias=AliasChoices("SCOUT_DATABASE_URL", "DATABASE_URL"))
    api_key_prefix: str = "scout_live_"
    github_timeout_seconds: float = 10.0
    model_config = SettingsConfigDict(env_prefix="SCOUT_", env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
