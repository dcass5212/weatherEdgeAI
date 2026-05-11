"""Evidence reporting routes for multi-day paper runs.

The evidence report composes persisted runner, prediction, outcome, and paper
trade records into one read-only summary for post-run interpretation.
"""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.backtesting.backtest_runner import BacktestRunner
from app.backtesting.schemas import BacktestRunRequest, BacktestRunResponse
from app.db.models import EVRecommendation, Market, PaperRunnerRun, PaperTrade, Prediction, ResolvedOutcome
from app.db.session import get_db


router = APIRouter(prefix="/evaluation", tags=["evaluation"])


class EvidenceRecordCounts(BaseModel):
    markets: int
    predictions: int
    resolved_outcomes: int
    open_paper_trades: int
    resolved_paper_trades: int
    closed_paper_trades: int
    unresolved_paper_trades: int


class EvidenceRunnerSummary(BaseModel):
    run_count: int
    latest_run_ids: list[int] = Field(default_factory=list)
    discovered: int
    processed: int
    parsed: int
    forecasts_created: int
    predictions_created: int
    recommendations_created: int
    paper_trades_created: int
    skipped: dict[str, int] = Field(default_factory=dict)
    error_count: int


class PaperTradeLifecycleCounts(BaseModel):
    recommended_buy_signals: int = 0
    recommended_but_not_traded: int = 0
    open: int = 0
    resolved: int = 0
    manually_closed: int = 0
    unresolved: int = 0
    unresolved_past_target_window: int = 0


class MarketImpliedCoverageDiagnostics(BaseModel):
    evaluated_prediction_count: int = 0
    with_market_implied_count: int = 0
    missing_market_implied_count: int = 0
    coverage_ratio: float | None = None
    missing_reason: str | None = None


class EvidenceReport(BaseModel):
    model_version: str
    start_date: date
    end_date: date
    source: str
    status: str
    sample_size_gate: str | None = None
    sample_size_note: str | None = None
    counts: EvidenceRecordCounts
    paper_trade_lifecycle: PaperTradeLifecycleCounts
    market_implied_coverage: MarketImpliedCoverageDiagnostics
    runner_summary: EvidenceRunnerSummary
    backtest: BacktestRunResponse
    interpretation_limits: list[str] = Field(default_factory=list)


def _count_scalar(db: Session, statement) -> int:
    return int(db.scalar(statement) or 0)


def _runner_summary(db: Session, limit: int) -> EvidenceRunnerSummary:
    runs = list(
        db.scalars(select(PaperRunnerRun).order_by(PaperRunnerRun.started_at.desc(), PaperRunnerRun.id.desc()).limit(limit))
    )
    skipped: dict[str, int] = {}
    error_count = 0
    for run in runs:
        if isinstance(run.skipped_json, dict):
            for reason, count in run.skipped_json.items():
                skipped[str(reason)] = skipped.get(str(reason), 0) + int(count or 0)
        if isinstance(run.errors_json, list):
            error_count += len(run.errors_json)

    return EvidenceRunnerSummary(
        run_count=len(runs),
        latest_run_ids=[run.id for run in runs],
        discovered=sum(run.discovered for run in runs),
        processed=sum(run.processed for run in runs),
        parsed=sum(run.parsed for run in runs),
        forecasts_created=sum(run.forecasts_created for run in runs),
        predictions_created=sum(run.predictions_created for run in runs),
        recommendations_created=sum(run.recommendations_created for run in runs),
        paper_trades_created=sum(run.paper_trades_created for run in runs),
        skipped=skipped,
        error_count=error_count,
    )


def _record_counts(db: Session, model_version: str) -> EvidenceRecordCounts:
    prediction_market_ids = select(Prediction.market_id).where(Prediction.model_version == model_version)
    unresolved_trade_count = _count_scalar(
        db,
        select(func.count(PaperTrade.id))
        .where(PaperTrade.status == "OPEN")
        .where(PaperTrade.market_id.not_in(select(ResolvedOutcome.market_id))),
    )
    return EvidenceRecordCounts(
        markets=_count_scalar(db, select(func.count(Market.id))),
        predictions=_count_scalar(db, select(func.count(Prediction.id)).where(Prediction.model_version == model_version)),
        resolved_outcomes=_count_scalar(
            db,
            select(func.count(ResolvedOutcome.id)).where(ResolvedOutcome.market_id.in_(prediction_market_ids)),
        ),
        open_paper_trades=_count_scalar(db, select(func.count(PaperTrade.id)).where(PaperTrade.status == "OPEN")),
        resolved_paper_trades=_count_scalar(db, select(func.count(PaperTrade.id)).where(PaperTrade.status == "RESOLVED")),
        closed_paper_trades=_count_scalar(db, select(func.count(PaperTrade.id)).where(PaperTrade.status == "CLOSED")),
        unresolved_paper_trades=unresolved_trade_count,
    )


def _paper_trade_lifecycle_counts(db: Session, model_version: str) -> PaperTradeLifecycleCounts:
    recommendation_ids = set(
        db.scalars(
            select(EVRecommendation.id)
            .join(Prediction, EVRecommendation.prediction_id == Prediction.id)
            .where(Prediction.model_version == model_version)
            .where(EVRecommendation.recommendation.in_(["PAPER_BUY_YES", "PAPER_BUY_NO"]))
        ).all()
    )
    traded_recommendation_ids = set(
        db.scalars(
            select(PaperTrade.recommendation_id)
            .where(PaperTrade.recommendation_id.is_not(None))
            .where(PaperTrade.recommendation_id.in_(recommendation_ids))
        ).all()
    )
    open_trades = list(
        db.scalars(
            select(PaperTrade)
            .join(EVRecommendation, PaperTrade.recommendation_id == EVRecommendation.id)
            .join(Prediction, EVRecommendation.prediction_id == Prediction.id)
            .where(Prediction.model_version == model_version)
            .where(PaperTrade.status == "OPEN")
        )
    )
    return PaperTradeLifecycleCounts(
        recommended_buy_signals=len(recommendation_ids),
        recommended_but_not_traded=len(recommendation_ids - traded_recommendation_ids),
        open=len(open_trades),
        resolved=_count_paper_trades_by_status(db, model_version, "RESOLVED"),
        manually_closed=_count_paper_trades_by_status(db, model_version, "CLOSED"),
        unresolved=len([trade for trade in open_trades if _trade_has_no_outcome(db, trade)]),
        unresolved_past_target_window=len(
            [trade for trade in open_trades if _trade_has_no_outcome(db, trade) and _trade_target_window_elapsed(trade)]
        ),
    )


def _count_paper_trades_by_status(db: Session, model_version: str, status: str) -> int:
    return _count_scalar(
        db,
        select(func.count(PaperTrade.id))
        .join(EVRecommendation, PaperTrade.recommendation_id == EVRecommendation.id)
        .join(Prediction, EVRecommendation.prediction_id == Prediction.id)
        .where(Prediction.model_version == model_version)
        .where(PaperTrade.status == status),
    )


def _trade_has_no_outcome(db: Session, trade: PaperTrade) -> bool:
    return (
        db.scalars(select(ResolvedOutcome.id).where(ResolvedOutcome.market_id == trade.market_id).limit(1)).first()
        is None
    )


def _trade_target_window_elapsed(trade: PaperTrade) -> bool:
    snapshot = trade.signal_snapshot_json if isinstance(trade.signal_snapshot_json, dict) else {}
    parsed_target = snapshot.get("parsed_target") if isinstance(snapshot.get("parsed_target"), dict) else {}
    target_value = parsed_target.get("target_end") or parsed_target.get("target_start")
    if not isinstance(target_value, str) or not target_value:
        return False
    try:
        target_end = datetime.fromisoformat(target_value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if target_end.tzinfo is None:
        target_end = target_end.replace(tzinfo=timezone.utc)
    return target_end < datetime.now(timezone.utc)


def _market_implied_coverage(result: BacktestRunResponse) -> MarketImpliedCoverageDiagnostics:
    evaluated = result.coverage_diagnostics.evaluated_prediction_count
    market_comparison = next(
        (item for item in result.baseline_comparisons if item.name == "market_implied_probability"),
        None,
    )
    with_market = market_comparison.prediction_count if market_comparison is not None else 0
    missing = max(evaluated - with_market, 0)
    if evaluated == 0:
        return MarketImpliedCoverageDiagnostics(
            evaluated_prediction_count=0,
            with_market_implied_count=0,
            missing_market_implied_count=0,
            coverage_ratio=None,
            missing_reason="no evaluated predictions",
        )
    return MarketImpliedCoverageDiagnostics(
        evaluated_prediction_count=evaluated,
        with_market_implied_count=with_market,
        missing_market_implied_count=missing,
        coverage_ratio=round(with_market / evaluated, 6),
        missing_reason=None if missing == 0 else "evaluated predictions lacked linked market YES prices",
    )


def _interpretation_limits(
    result: BacktestRunResponse,
    counts: EvidenceRecordCounts,
    market_implied_coverage: MarketImpliedCoverageDiagnostics,
) -> list[str]:
    limits: list[str] = []
    if result.sample_size_gate == "insufficient_sample":
        limits.append("Sample is too small for performance claims; use results to inspect data flow and early signal quality.")
    if result.coverage_diagnostics.missing_outcome_count:
        limits.append("Some predictions do not have resolved outcomes in the selected window.")
    if counts.unresolved_paper_trades:
        limits.append("Some open paper trades remain unresolved and are excluded from settled PnL interpretation.")
    if market_implied_coverage.evaluated_prediction_count and market_implied_coverage.with_market_implied_count == 0:
        limits.append("No market-implied comparison was available because evaluated predictions lacked linked YES prices.")
    elif market_implied_coverage.missing_market_implied_count:
        limits.append("Market-implied comparison covers only part of the evaluated prediction sample.")
    return limits


@router.get("/evidence-report", response_model=EvidenceReport)
def get_evidence_report(
    start_date: date,
    end_date: date,
    model_version: str = "baseline_precip_v1",
    paper_fee_rate: float = Query(default=0.0, ge=0.0, le=1.0),
    paper_slippage_rate: float = Query(default=0.0, ge=0.0, le=1.0),
    runner_limit: int = Query(default=20, gt=0, le=100),
    db: Session = Depends(get_db),
) -> EvidenceReport:
    backtest = BacktestRunner(db).run(
        BacktestRunRequest(
            start_date=start_date,
            end_date=end_date,
            model_version=model_version,
            paper_fee_rate=paper_fee_rate,
            paper_slippage_rate=paper_slippage_rate,
        )
    )
    counts = _record_counts(db, model_version)
    lifecycle = _paper_trade_lifecycle_counts(db, model_version)
    market_implied_coverage = _market_implied_coverage(backtest)
    return EvidenceReport(
        model_version=model_version,
        start_date=start_date,
        end_date=end_date,
        source=backtest.source,
        status=backtest.status,
        sample_size_gate=backtest.sample_size_gate,
        sample_size_note=backtest.sample_size_note,
        counts=counts,
        paper_trade_lifecycle=lifecycle,
        market_implied_coverage=market_implied_coverage,
        runner_summary=_runner_summary(db, runner_limit),
        backtest=backtest,
        interpretation_limits=_interpretation_limits(backtest, counts, market_implied_coverage),
    )
