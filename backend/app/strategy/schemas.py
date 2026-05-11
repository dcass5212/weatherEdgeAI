from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EVRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prediction_id: int
    price_snapshot_id: int | None = None
    market_price_yes: float | None = None
    market_price_no: float | None = None
    edge_yes: float | None = None
    edge_no: float | None = None
    ev_yes: float | None = None
    ev_no: float | None = None
    recommendation: str
    paper_position_size: float | None = None
    reason: str | None = None
    created_at: datetime


class StrategyEvaluationRead(EVRecommendationRead):
    market_id: int
    parsed_market_id: int | None = None
    forecast_snapshot_id: int | None = None
    model_probability_yes: float


class OpportunityRead(BaseModel):
    market_id: int
    prediction_id: int
    price_snapshot_id: int | None = None
    question: str
    model_probability_yes: float
    market_price_yes: float | None = None
    edge_yes: float | None = None
    recommendation: str
    created_at: datetime


class PaperTradeCreate(BaseModel):
    recommendation_id: int
    quantity: float = Field(gt=0)


class PaperTradeClose(BaseModel):
    exit_price: float = Field(ge=0, le=1)


class PaperTradeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_id: int
    recommendation_id: int | None = None
    side: str
    entry_price: float
    quantity: float
    entry_time: datetime
    exit_price: float | None = None
    exit_time: datetime | None = None
    pnl: float | None = None
    status: str
    signal_snapshot_json: dict | None = None
    created_at: datetime
    updated_at: datetime
