from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "WeatherEdge AI"
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "postgresql+psycopg2://weatheredge:weatheredge@localhost:5432/weatheredge"
    POLYMARKET_GAMMA_BASE_URL: str = "https://gamma-api.polymarket.com"
    POLYMARKET_CLOB_BASE_URL: str = "https://clob.polymarket.com"
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com/v1"
    OPEN_METEO_ARCHIVE_BASE_URL: str = "https://archive-api.open-meteo.com/v1"
    OPEN_METEO_GEOCODING_BASE_URL: str = "https://geocoding-api.open-meteo.com/v1"
    GEOCODING_PROVIDER: str = "fixture"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
