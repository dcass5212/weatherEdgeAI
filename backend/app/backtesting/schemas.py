from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class BacktestRunRequest(BaseModel):
    start_date: date
    end_date: date
    model_version: str = "baseline_precip_v1"
    seed_fixtures: bool = False


class ResolvedOutcomeCreate(BaseModel):
    market_id: int
    actual_outcome: str = Field(pattern="^(YES|NO)$")
    actual_value: float | None = None
    actual_unit: str | None = None
    resolution_source: str | None = None
    resolved_at: datetime | None = None
    raw_json: dict | None = None


class WeatherOutcomeResolveRequest(BaseModel):
    market_id: int


class ResolvedOutcomeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_id: int
    actual_outcome: str
    actual_value: float | None = None
    actual_unit: str | None = None
    resolution_source: str | None = None
    resolved_at: datetime | None = None
    raw_json: dict | None = None
    created_at: datetime


class CalibrationBucket(BaseModel):
    lower_bound: float
    upper_bound: float
    count: int
    average_predicted_probability: float | None = None
    observed_yes_rate: float | None = None
    calibration_gap: float | None = None


class BacktestRunResponse(BaseModel):
    model_version: str
    num_predictions: int
    num_resolved_outcomes: int = 0
    ev_recommendation_count: int = 0
    paper_trade_count: int = 0
    win_rate: float | None = None
    brier_score: float | None = None
    log_loss: float | None = None
    calibration_buckets: list[CalibrationBucket] = Field(default_factory=list)
    sample_size_note: str | None = None
    paper_total_pnl: float | None = None
    paper_roi: float | None = None
    max_drawdown: float | None = None
    status: str
    source: str = "persisted_records"
