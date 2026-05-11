from functools import lru_cache
from typing import Literal

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
    NOAA_CDO_BASE_URL: str = "https://www.ncei.noaa.gov/cdo-web/api/v2"
    NOAA_CDO_TOKEN: str | None = None
    GEOCODING_PROVIDER: str = "fixture"
    PAPER_RUNNER_ALLOW_INTERVAL_CONTRACTS: bool = False
    PAPER_RUNNER_MAX_PRICE_AGE_MINUTES: float = 120.0
    PAPER_RUNNER_MAX_FORECAST_AGE_HOURS: float = 12.0
    PAPER_RUNNER_MAX_OPEN_TRADES: int = 5
    PAPER_RUNNER_MAX_TOTAL_EXPOSURE: float = 25.0
    PAPER_RUNNER_MAX_MARKET_EXPOSURE: float = 5.0
    PAPER_RUNNER_MAX_LOCATION_EXPOSURE: float = 10.0
    PAPER_RUNNER_ENTRY_SLIPPAGE_RATE: float = 0.0
    PAPER_RUNNER_ALLOW_STALE_PRICE_FALLBACK: bool = False
    TRADING_MODE: Literal["paper", "read_only", "live"] = "paper"
    LIVE_TRADING_ENABLED: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def live_execution_allowed(self) -> bool:
        return self.TRADING_MODE == "live" and self.LIVE_TRADING_ENABLED


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
