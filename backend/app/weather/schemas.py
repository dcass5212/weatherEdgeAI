from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WeatherForecastSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parsed_market_id: int
    forecast_source: str
    forecast_timestamp: datetime
    target_start: datetime | None = None
    target_end: datetime | None = None
    forecast_precip_total: float | None = None
    forecast_precip_unit: str | None = None
    forecast_temp_max: float | None = None
    forecast_temp_min: float | None = None
    forecast_temp_unit: str | None = None
    raw_json: dict | None = None
    created_at: datetime
