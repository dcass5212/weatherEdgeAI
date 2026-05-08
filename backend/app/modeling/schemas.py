from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_id: int
    parsed_market_id: int | None = None
    forecast_snapshot_id: int | None = None
    model_version: str
    p_yes: float
    p_no: float
    confidence: str | None = None
    features_json: dict | None = None
    created_at: datetime
