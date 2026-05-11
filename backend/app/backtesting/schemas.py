from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class BacktestRunRequest(BaseModel):
    start_date: date
    end_date: date
    model_version: str = "baseline_precip_v1"
    seed_fixtures: bool = False
    paper_fee_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    paper_slippage_rate: float = Field(default=0.0, ge=0.0, le=1.0)


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
    resolution_provider: str = Field(default="open_meteo_archive", pattern="^(open_meteo_archive|noaa_cdo_daily)$")
    settle_open_trades: bool = True


class WeatherOutcomeBatchResolveRequest(BaseModel):
    resolution_provider: str = Field(default="open_meteo_archive", pattern="^(open_meteo_archive|noaa_cdo_daily)$")
    limit: int = Field(default=50, gt=0, le=200)
    settle_open_trades: bool = True
    skip_existing_outcomes: bool = True


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


class PaperTradeSettlementSummaryRead(BaseModel):
    market_id: int
    outcome_id: int
    settled_trade_ids: list[int] = Field(default_factory=list)
    settled_count: int = 0


class WeatherOutcomeResolveResult(BaseModel):
    outcome: ResolvedOutcomeRead
    settlement: PaperTradeSettlementSummaryRead | None = None


class WeatherOutcomeBatchItem(BaseModel):
    market_id: int
    parsed_market_id: int | None = None
    status: str
    outcome_id: int | None = None
    settled_count: int = 0
    reason: str | None = None


class WeatherOutcomeBatchResolveResponse(BaseModel):
    resolution_provider: str
    requested_limit: int
    scanned: int
    resolved: int
    skipped: int
    errors: int
    settled_trades: int
    results: list[WeatherOutcomeBatchItem] = Field(default_factory=list)


class OutcomeEligibilityPreviewItem(BaseModel):
    market_id: int
    parsed_market_id: int | None = None
    question: str
    location_name: str | None = None
    target_start: datetime | None = None
    target_end: datetime | None = None
    status: str
    reason: str | None = None
    latest_outcome_id: int | None = None
    latest_outcome_source: str | None = None


class OutcomeEligibilityPreviewResponse(BaseModel):
    resolution_provider: str
    limit: int
    counts: dict[str, int] = Field(default_factory=dict)
    results: list[OutcomeEligibilityPreviewItem] = Field(default_factory=list)


class CalibrationBucket(BaseModel):
    lower_bound: float
    upper_bound: float
    count: int
    average_predicted_probability: float | None = None
    observed_yes_rate: float | None = None
    calibration_gap: float | None = None


class BacktestCoverageDiagnostics(BaseModel):
    candidate_prediction_count: int = 0
    evaluated_prediction_count: int = 0
    missing_outcome_count: int = 0
    resolved_outcome_count_in_window: int = 0
    unmatched_resolved_outcome_count: int = 0
    excluded_prediction_model_version_count: int = 0


class BaselineComparison(BaseModel):
    name: str
    prediction_count: int
    brier_score: float | None = None
    log_loss: float | None = None
    win_rate: float | None = None


class BacktestRunResponse(BaseModel):
    model_version: str
    num_predictions: int
    num_resolved_outcomes: int = 0
    coverage_diagnostics: BacktestCoverageDiagnostics = Field(default_factory=BacktestCoverageDiagnostics)
    ev_recommendation_count: int = 0
    paper_trade_count: int = 0
    win_rate: float | None = None
    brier_score: float | None = None
    log_loss: float | None = None
    calibration_buckets: list[CalibrationBucket] = Field(default_factory=list)
    sample_size_note: str | None = None
    sample_size_gate: str | None = None
    baseline_comparisons: list[BaselineComparison] = Field(default_factory=list)
    paper_gross_pnl: float | None = None
    paper_fee_cost: float | None = None
    paper_slippage_cost: float | None = None
    paper_total_pnl: float | None = None
    paper_roi: float | None = None
    max_drawdown: float | None = None
    paper_settlement_note: str | None = None
    status: str
    source: str = "persisted_records"
