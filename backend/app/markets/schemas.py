from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modeling.schemas import PredictionRead
from app.strategy.schemas import EVRecommendationRead, PaperTradeRead
from app.weather.schemas import WeatherForecastSnapshotRead


class ParsedMarketResult(BaseModel):
    success: bool
    location_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    metric: str | None = None
    operator: str | None = None
    threshold_value: float | None = None
    interval_upper_value: float | None = None
    threshold_unit: str | None = None
    target_start: datetime | None = None
    target_end: datetime | None = None
    parser_version: str = "regex_precip_v1"
    parse_confidence: float = 0.0
    error: str | None = None


class MarketCreate(BaseModel):
    source: str = "manual"
    source_market_id: str
    condition_id: str | None = None
    question: str
    slug: str | None = None
    category: str | None = "weather"
    active: bool = True
    closed: bool = False
    end_time: datetime | None = None
    resolution_source: str | None = None
    raw_json: dict | None = None
    source_diagnostics: dict | None = None


class MarketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    source_market_id: str
    condition_id: str | None = None
    question: str
    slug: str | None = None
    category: str | None = None
    active: bool
    closed: bool
    end_time: datetime | None = None
    resolution_source: str | None = None
    source_diagnostics: dict | None = None
    created_at: datetime
    updated_at: datetime


class ParsedMarketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_id: int
    location_name: str
    latitude: float | None = None
    longitude: float | None = None
    metric: str
    operator: str
    threshold_value: float
    threshold_unit: str
    target_start: datetime | None = None
    target_end: datetime | None = None
    parse_confidence: float
    parser_version: str
    raw_parse_json: dict | None = None
    created_at: datetime
    updated_at: datetime


class MarketPriceSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_id: int
    yes_price: float | None = None
    no_price: float | None = None
    best_bid_yes: float | None = None
    best_ask_yes: float | None = None
    best_bid_no: float | None = None
    best_ask_no: float | None = None
    spread: float | None = None
    liquidity: float | None = None
    volume: float | None = None
    timestamp: datetime
    created_at: datetime


class MarketWorkflowStatus(BaseModel):
    has_price_snapshot: bool = False
    has_parsed_market: bool = False
    has_forecast_snapshot: bool = False
    has_prediction: bool = False
    has_ev_recommendation: bool = False
    has_paper_trade: bool = False
    next_action: str


class MarketDetailRead(MarketRead):
    latest_parsed_market: ParsedMarketRead | None = None
    latest_price_snapshot: MarketPriceSnapshotRead | None = None
    latest_forecast_snapshot: WeatherForecastSnapshotRead | None = None
    latest_prediction: PredictionRead | None = None
    latest_ev_recommendation: EVRecommendationRead | None = None
    latest_paper_trade: PaperTradeRead | None = None
    workflow_status: MarketWorkflowStatus


class MarketDiscoveryRequest(BaseModel):
    source: str = "polymarket"
    keywords: list[str] = Field(default_factory=lambda: ["weather", "rain", "snow", "temperature"])
    limit: int = Field(default=50, gt=0, le=200)


class MarketDiscoveryResponse(BaseModel):
    discovered: int
    created: int
    updated: int
    price_snapshots_created: int = 0
