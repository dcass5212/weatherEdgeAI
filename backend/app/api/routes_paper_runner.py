"""Paper runner API routes.

These endpoints expose the public-market paper runner as an auditable one-shot
workflow. They create simulated paper trades only; live execution remains out
of scope for this API.
"""

from collections import Counter
from typing import Any

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Market, PaperRunnerRun
from app.db.session import get_db
from app.modeling.model_registry import DEFAULT_MODEL_VERSION, available_model_versions
from app.strategy.paper_market_runner import PaperMarketRunnerConfig, run_paper_market_once_recorded


router = APIRouter(prefix="/paper-runner", tags=["paper-runner"])


class PaperRunnerRunRequest(BaseModel):
    source: str = "polymarket"
    keywords: list[str] = Field(default_factory=lambda: ["rain", "weather", "precipitation"])
    discovery_limit: int = Field(default=25, gt=0, le=100)
    process_limit: int = Field(default=10, gt=0, le=100)
    max_trades: int = Field(default=3, ge=0, le=25)
    quantity: float = Field(default=1.0, gt=0)
    min_liquidity: float = Field(default=0.0, ge=0)
    max_spread: float = Field(default=0.15, ge=0)
    refresh_prices: bool = True
    dry_run: bool = False
    allow_interval_contracts: bool = settings.PAPER_RUNNER_ALLOW_INTERVAL_CONTRACTS
    max_price_age_minutes: float | None = Field(default=settings.PAPER_RUNNER_MAX_PRICE_AGE_MINUTES, ge=0)
    max_forecast_age_hours: float | None = Field(default=settings.PAPER_RUNNER_MAX_FORECAST_AGE_HOURS, ge=0)
    max_open_trades: int | None = Field(default=settings.PAPER_RUNNER_MAX_OPEN_TRADES, ge=0)
    max_total_exposure: float | None = Field(default=settings.PAPER_RUNNER_MAX_TOTAL_EXPOSURE, ge=0)
    max_market_exposure: float | None = Field(default=settings.PAPER_RUNNER_MAX_MARKET_EXPOSURE, ge=0)
    max_location_exposure: float | None = Field(default=settings.PAPER_RUNNER_MAX_LOCATION_EXPOSURE, ge=0)
    entry_slippage_rate: float = Field(default=settings.PAPER_RUNNER_ENTRY_SLIPPAGE_RATE, ge=0, le=1)
    allow_stale_price_fallback: bool = settings.PAPER_RUNNER_ALLOW_STALE_PRICE_FALLBACK
    model_version: str = DEFAULT_MODEL_VERSION


class PaperRunnerRehearsalRequest(PaperRunnerRunRequest):
    dry_run: bool = True


class PaperRunnerRunRead(BaseModel):
    id: int
    status: str
    source: str
    started_at: str
    completed_at: str | None
    config: dict
    discovered: int
    created: int
    updated: int
    price_snapshots_created: int
    processed: int
    parsed: int
    forecasts_created: int
    predictions_created: int
    recommendations_created: int
    actionable_recommendations: int
    expected_paper_trades: int
    paper_trades_created: int
    skipped: dict
    errors: list[str]
    report: dict | None


class PaperRunnerSkipReasonSummary(BaseModel):
    reason: str
    count: int
    category: str
    label: str


class PaperRunnerUnsupportedPriceReasonSummary(BaseModel):
    reason: str
    count: int


class PaperRunnerRecentError(BaseModel):
    run_id: int
    message: str


class PaperRunnerDiagnosticsRead(BaseModel):
    source: str | None
    run_count: int
    latest_run_ids: list[int]
    discovered: int
    processed: int
    parsed: int
    forecasts_created: int
    predictions_created: int
    recommendations_created: int
    paper_trades_created: int
    stale_price_fallbacks_used: int
    skip_reasons: list[PaperRunnerSkipReasonSummary]
    price_status_counts: dict[str, int]
    unsupported_price_reasons: list[PaperRunnerUnsupportedPriceReasonSummary]
    error_count: int
    recent_errors: list[PaperRunnerRecentError]


SKIP_REASON_CATEGORIES = {
    "missing_price_snapshot": ("price_data", "No price snapshot"),
    "missing_binary_prices": ("price_data", "Missing binary YES/NO prices"),
    "price_refresh_failed": ("price_data", "Public price refresh failed"),
    "price_refresh_failed_used_stored_snapshot": ("price_data", "Used stored price after refresh failure"),
    "price_refresh_failed_fresh_price_required": ("price_data", "Fresh price required after refresh failure"),
    "price_refresh_unsupported": ("price_data", "Unsupported fresh price payload"),
    "liquidity_below_min": ("eligibility_filter", "Liquidity below configured minimum"),
    "spread_above_max": ("eligibility_filter", "Spread above configured maximum"),
    "price_snapshot_stale": ("freshness", "Price snapshot is stale"),
    "forecast_snapshot_stale": ("freshness", "Forecast snapshot is stale"),
    "target_window_started": ("freshness", "Target weather window already started"),
    "target_window_elapsed": ("freshness", "Target weather window already elapsed"),
    "parse_failed": ("parser", "Parser could not structure question"),
    "parse_failed_not_precipitation": ("parser", "Question was not a precipitation market"),
    "parse_failed_missing_threshold": ("parser", "Question had no numeric threshold"),
    "parse_failed_unsupported_unit": ("parser", "Question used an unsupported precipitation unit"),
    "parse_failed_interval_contract": ("parser", "Question used an interval contract that needs interval probability modeling"),
    "parse_failed_unsupported_wording": ("parser", "Question used unsupported precipitation wording"),
    "parse_failed_unknown": ("parser", "Parser failed for an uncategorized reason"),
    "missing_coordinates": ("geocoding", "Parsed location has no coordinates"),
    "workflow_error": ("provider_or_workflow_error", "Workflow/provider error"),
    "trade_creation_disabled": ("paper_trading", "Dry run disabled trade creation"),
    "not_actionable": ("paper_trading", "Recommendation was not actionable"),
    "open_trade_exists": ("paper_trading", "Open paper trade already exists"),
    "max_trades_reached": ("paper_trading", "Max paper-trade cap reached"),
    "portfolio_open_trade_limit": ("paper_portfolio", "Max open paper trades reached"),
    "portfolio_total_exposure_limit": ("paper_portfolio", "Max total paper exposure reached"),
    "portfolio_market_exposure_limit": ("paper_portfolio", "Max per-market paper exposure reached"),
    "portfolio_location_exposure_limit": ("paper_portfolio", "Max per-location paper exposure reached"),
}


def _skip_reason_summary(reason: str, count: int) -> PaperRunnerSkipReasonSummary:
    category, label = SKIP_REASON_CATEGORIES.get(reason, ("other", reason.replace("_", " ").title()))
    return PaperRunnerSkipReasonSummary(reason=reason, count=count, category=category, label=label)


def _json_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _json_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _config_from_request(payload: PaperRunnerRunRequest) -> PaperMarketRunnerConfig:
    if payload.model_version not in available_model_versions():
        supported = ", ".join(available_model_versions())
        raise HTTPException(status_code=422, detail=f"Unsupported model_version '{payload.model_version}'. Supported versions: {supported}")
    return PaperMarketRunnerConfig(
        source=payload.source,
        keywords=payload.keywords,
        discovery_limit=payload.discovery_limit,
        process_limit=payload.process_limit,
        max_trades=payload.max_trades,
        quantity=payload.quantity,
        min_liquidity=payload.min_liquidity,
        max_spread=payload.max_spread,
        refresh_prices=payload.refresh_prices,
        create_trades=not payload.dry_run,
        allow_interval_contracts=payload.allow_interval_contracts,
        max_price_age_minutes=payload.max_price_age_minutes,
        max_forecast_age_hours=payload.max_forecast_age_hours,
        max_open_trades=payload.max_open_trades,
        max_total_exposure=payload.max_total_exposure,
        max_market_exposure=payload.max_market_exposure,
        max_location_exposure=payload.max_location_exposure,
        entry_slippage_rate=payload.entry_slippage_rate,
        allow_stale_price_fallback=payload.allow_stale_price_fallback,
        model_version=payload.model_version,
    )


def _read_model(run: PaperRunnerRun) -> PaperRunnerRunRead:
    return PaperRunnerRunRead(
        id=run.id,
        status=run.status,
        source=run.source,
        started_at=run.started_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        config=run.config_json,
        discovered=run.discovered,
        created=run.created,
        updated=run.updated,
        price_snapshots_created=run.price_snapshots_created,
        processed=run.processed,
        parsed=run.parsed,
        forecasts_created=run.forecasts_created,
        predictions_created=run.predictions_created,
        recommendations_created=run.recommendations_created,
        actionable_recommendations=int(_json_dict(run.report_json).get("actionable_recommendations", 0)),
        expected_paper_trades=int(_json_dict(run.report_json).get("expected_paper_trades", 0)),
        paper_trades_created=run.paper_trades_created,
        skipped=run.skipped_json,
        errors=run.errors_json,
        report=run.report_json,
    )


def _diagnostics_model(runs: list[PaperRunnerRun], markets: list[Market], source: str | None) -> PaperRunnerDiagnosticsRead:
    skipped = Counter()
    price_statuses = Counter()
    unsupported_price_reasons = Counter()
    stale_price_fallbacks_used = 0
    recent_errors: list[PaperRunnerRecentError] = []

    for run in runs:
        skipped.update({str(reason): int(count) for reason, count in _json_dict(run.skipped_json).items()})
        stale_price_fallbacks_used += int(_json_dict(run.report_json).get("stale_price_fallbacks_used", 0))
        for message in _json_list(run.errors_json):
            if isinstance(message, str):
                recent_errors.append(PaperRunnerRecentError(run_id=run.id, message=message))

    for market in markets:
        diagnostics = _json_dict(market.source_diagnostics)
        price_status = diagnostics.get("price_status")
        if isinstance(price_status, str):
            price_statuses[price_status] += 1
        for reason in _json_list(diagnostics.get("unsupported_reasons")):
            if isinstance(reason, str):
                unsupported_price_reasons[reason] += 1

    return PaperRunnerDiagnosticsRead(
        source=source,
        run_count=len(runs),
        latest_run_ids=[run.id for run in runs[:10]],
        discovered=sum(run.discovered for run in runs),
        processed=sum(run.processed for run in runs),
        parsed=sum(run.parsed for run in runs),
        forecasts_created=sum(run.forecasts_created for run in runs),
        predictions_created=sum(run.predictions_created for run in runs),
        recommendations_created=sum(run.recommendations_created for run in runs),
        paper_trades_created=sum(run.paper_trades_created for run in runs),
        stale_price_fallbacks_used=stale_price_fallbacks_used,
        skip_reasons=[
            _skip_reason_summary(reason, count)
            for reason, count in sorted(skipped.items(), key=lambda item: (-item[1], item[0]))
        ],
        price_status_counts=dict(sorted(price_statuses.items())),
        unsupported_price_reasons=[
            PaperRunnerUnsupportedPriceReasonSummary(reason=reason, count=count)
            for reason, count in sorted(unsupported_price_reasons.items(), key=lambda item: (-item[1], item[0]))
        ],
        error_count=len(recent_errors),
        recent_errors=recent_errors[:10],
    )


@router.post("/run-once", response_model=PaperRunnerRunRead, status_code=201)
async def run_paper_runner_once(payload: PaperRunnerRunRequest, db: Session = Depends(get_db)) -> PaperRunnerRunRead:
    try:
        run = await run_paper_market_once_recorded(db, _config_from_request(payload))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Paper runner failed: {exc}") from exc
    return _read_model(run)


@router.post("/rehearsal", response_model=PaperRunnerRunRead, status_code=201)
async def rehearse_paper_runner(payload: PaperRunnerRehearsalRequest, db: Session = Depends(get_db)) -> PaperRunnerRunRead:
    config = _config_from_request(payload)
    config = PaperMarketRunnerConfig(**{**config.__dict__, "create_trades": False})
    try:
        run = await run_paper_market_once_recorded(db, config)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Paper runner rehearsal failed: {exc}") from exc
    return _read_model(run)


@router.get("/runs", response_model=list[PaperRunnerRunRead])
def list_paper_runner_runs(
    limit: int = Query(default=20, gt=0, le=100),
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[PaperRunnerRunRead]:
    query = select(PaperRunnerRun)
    if status is not None:
        query = query.where(PaperRunnerRun.status == status)
    query = query.order_by(PaperRunnerRun.started_at.desc(), PaperRunnerRun.id.desc()).limit(limit)
    return [_read_model(run) for run in db.scalars(query)]


@router.get("/diagnostics", response_model=PaperRunnerDiagnosticsRead)
def get_paper_runner_diagnostics(
    limit: int = Query(default=20, gt=0, le=100),
    source: str | None = "polymarket",
    db: Session = Depends(get_db),
) -> PaperRunnerDiagnosticsRead:
    run_query = select(PaperRunnerRun)
    market_query = select(Market)
    if source is not None:
        run_query = run_query.where(PaperRunnerRun.source == source)
        market_query = market_query.where(Market.source == source)
    run_query = run_query.order_by(PaperRunnerRun.started_at.desc(), PaperRunnerRun.id.desc()).limit(limit)
    runs = list(db.scalars(run_query))
    markets = list(db.scalars(market_query))
    return _diagnostics_model(runs, markets, source)


@router.get("/runs/{run_id}", response_model=PaperRunnerRunRead)
def get_paper_runner_run(run_id: int, db: Session = Depends(get_db)) -> PaperRunnerRunRead:
    run = db.get(PaperRunnerRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Paper runner run not found")
    return _read_model(run)
