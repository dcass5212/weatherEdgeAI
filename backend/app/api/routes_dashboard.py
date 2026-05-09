"""Dashboard API routes.

This read-only surface gives a future frontend one compact summary endpoint
without changing the narrower workflow endpoints used by tests and demos.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtesting.backtest_runner import BacktestRunner, build_seed_fixture_backtest_response
from app.backtesting.schemas import BacktestRunRequest, CalibrationBucket
from app.db.models import EVRecommendation, Market, PaperTrade, Prediction
from app.db.models import ResolvedOutcome
from app.db.repositories import (
    latest_forecast_snapshot,
    latest_paper_trade,
    latest_parsed_market,
    latest_prediction,
    latest_price_snapshot,
    latest_recommendation,
)
from app.db.session import get_db
from app.markets.schemas import MarketWorkflowStatus
from app.strategy.schemas import OpportunityRead, PaperTradeRead


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardMarketSummary(BaseModel):
    market_id: int
    question: str
    source: str
    source_market_id: str
    price_status: str | None = None
    unsupported_reasons: list[str] = []
    has_public_source_error: bool = False
    active: bool
    closed: bool
    latest_price_snapshot_id: int | None = None
    latest_parsed_market_id: int | None = None
    latest_forecast_snapshot_id: int | None = None
    latest_prediction_id: int | None = None
    latest_ev_recommendation_id: int | None = None
    latest_paper_trade_id: int | None = None
    parsed_target: str | None = None
    forecast_precip_total: float | None = None
    forecast_precip_unit: str | None = None
    model_probability_yes: float | None = None
    market_price_yes: float | None = None
    edge_yes: float | None = None
    recommendation: str | None = None
    paper_trade_status: str | None = None
    workflow_status: MarketWorkflowStatus
    updated_at: datetime


class DashboardEvaluationSummary(BaseModel):
    model_version: str
    source: str
    status: str
    num_predictions: int
    num_resolved_outcomes: int
    win_rate: float | None = None
    brier_score: float | None = None
    log_loss: float | None = None
    paper_roi: float | None = None
    paper_total_pnl: float | None = None
    max_drawdown: float | None = None
    sample_size_note: str | None = None
    calibration_buckets: list[CalibrationBucket]


class DashboardSummaryRead(BaseModel):
    recent_markets: list[DashboardMarketSummary]
    opportunities: list[OpportunityRead]
    open_paper_trades: list[PaperTradeRead]
    evaluation_summary: DashboardEvaluationSummary


def _workflow_status(
    price_snapshot_id: int | None,
    parsed_market_id: int | None,
    forecast_snapshot_id: int | None,
    prediction_id: int | None,
    ev_recommendation_id: int | None,
    paper_trade_id: int | None,
) -> MarketWorkflowStatus:
    if price_snapshot_id is None:
        next_action = "refresh_price_snapshot"
    elif parsed_market_id is None:
        next_action = "parse_market"
    elif forecast_snapshot_id is None:
        next_action = "create_forecast"
    elif prediction_id is None:
        next_action = "run_prediction"
    elif ev_recommendation_id is None:
        next_action = "evaluate_strategy"
    elif paper_trade_id is None:
        next_action = "ready_for_paper_trade"
    else:
        next_action = "monitor_paper_trade"

    return MarketWorkflowStatus(
        has_price_snapshot=price_snapshot_id is not None,
        has_parsed_market=parsed_market_id is not None,
        has_forecast_snapshot=forecast_snapshot_id is not None,
        has_prediction=prediction_id is not None,
        has_ev_recommendation=ev_recommendation_id is not None,
        has_paper_trade=paper_trade_id is not None,
        next_action=next_action,
    )


def _parsed_target_label(parsed_market: object | None) -> str | None:
    if parsed_market is None:
        return None
    location_name = getattr(parsed_market, "location_name", None)
    metric = getattr(parsed_market, "metric", None)
    operator = getattr(parsed_market, "operator", None)
    threshold_value = getattr(parsed_market, "threshold_value", None)
    threshold_unit = getattr(parsed_market, "threshold_unit", None)
    if not all([location_name, metric, operator, threshold_value, threshold_unit]):
        return None
    return f"{location_name} {metric} {operator} {threshold_value:g} {threshold_unit}"


def _source_diagnostics_summary(market: Market) -> dict:
    diagnostics = market.source_diagnostics if isinstance(market.source_diagnostics, dict) else {}
    unsupported_reasons = diagnostics.get("unsupported_reasons")
    return {
        "price_status": diagnostics.get("price_status") if isinstance(diagnostics.get("price_status"), str) else None,
        "unsupported_reasons": unsupported_reasons if isinstance(unsupported_reasons, list) else [],
        "has_public_source_error": bool(diagnostics.get("public_source_error")),
    }


def _recent_market_summaries(db: Session, limit: int) -> list[DashboardMarketSummary]:
    markets = list(db.scalars(select(Market).order_by(Market.updated_at.desc()).limit(limit)))
    summaries: list[DashboardMarketSummary] = []
    for market in markets:
        price_snapshot = latest_price_snapshot(db, market.id)
        parsed_market = latest_parsed_market(db, market.id)
        forecast_snapshot = latest_forecast_snapshot(db, parsed_market.id) if parsed_market else None
        prediction = latest_prediction(db, market.id)
        recommendation = latest_recommendation(db, prediction.id) if prediction else None
        paper_trade = latest_paper_trade(db, market.id)

        price_snapshot_id = price_snapshot.id if price_snapshot else None
        parsed_market_id = parsed_market.id if parsed_market else None
        forecast_snapshot_id = forecast_snapshot.id if forecast_snapshot else None
        prediction_id = prediction.id if prediction else None
        recommendation_id = recommendation.id if recommendation else None
        paper_trade_id = paper_trade.id if paper_trade else None
        diagnostics_summary = _source_diagnostics_summary(market)
        summaries.append(
            DashboardMarketSummary(
                market_id=market.id,
                question=market.question,
                source=market.source,
                source_market_id=market.source_market_id,
                price_status=diagnostics_summary["price_status"],
                unsupported_reasons=diagnostics_summary["unsupported_reasons"],
                has_public_source_error=diagnostics_summary["has_public_source_error"],
                active=market.active,
                closed=market.closed,
                latest_price_snapshot_id=price_snapshot_id,
                latest_parsed_market_id=parsed_market_id,
                latest_forecast_snapshot_id=forecast_snapshot_id,
                latest_prediction_id=prediction_id,
                latest_ev_recommendation_id=recommendation_id,
                latest_paper_trade_id=paper_trade_id,
                parsed_target=_parsed_target_label(parsed_market),
                forecast_precip_total=forecast_snapshot.forecast_precip_total if forecast_snapshot else None,
                forecast_precip_unit=forecast_snapshot.forecast_precip_unit if forecast_snapshot else None,
                model_probability_yes=prediction.p_yes if prediction else None,
                market_price_yes=price_snapshot.yes_price if price_snapshot else None,
                edge_yes=recommendation.edge_yes if recommendation else None,
                recommendation=recommendation.recommendation if recommendation else None,
                paper_trade_status=paper_trade.status if paper_trade else None,
                workflow_status=_workflow_status(
                    price_snapshot_id=price_snapshot_id,
                    parsed_market_id=parsed_market_id,
                    forecast_snapshot_id=forecast_snapshot_id,
                    prediction_id=prediction_id,
                    ev_recommendation_id=recommendation_id,
                    paper_trade_id=paper_trade_id,
                ),
                updated_at=market.updated_at,
            )
        )
    return summaries


def _opportunities(db: Session, limit: int) -> list[OpportunityRead]:
    rows = db.execute(
        select(EVRecommendation, Prediction, Market)
        .join(Prediction, EVRecommendation.prediction_id == Prediction.id)
        .join(Market, Prediction.market_id == Market.id)
        .where(EVRecommendation.recommendation.in_(["PAPER_BUY_YES", "PAPER_BUY_NO"]))
        .order_by(EVRecommendation.created_at.desc())
        .limit(limit)
    ).all()

    return [
        OpportunityRead(
            market_id=market.id,
            prediction_id=prediction.id,
            price_snapshot_id=recommendation.price_snapshot_id,
            question=market.question,
            model_probability_yes=prediction.p_yes,
            market_price_yes=recommendation.market_price_yes,
            edge_yes=recommendation.edge_yes,
            recommendation=recommendation.recommendation,
            created_at=recommendation.created_at,
        )
        for recommendation, prediction, market in rows
    ]


def _evaluation_summary(db: Session, model_version: str) -> DashboardEvaluationSummary:
    resolved_dates = list(
        db.scalars(
            select(ResolvedOutcome.resolved_at)
            .where(ResolvedOutcome.resolved_at.is_not(None))
            .order_by(ResolvedOutcome.resolved_at.asc())
        )
    )
    result = None
    if resolved_dates:
        result = BacktestRunner(db).run(
            BacktestRunRequest(
                start_date=resolved_dates[0].date(),
                end_date=resolved_dates[-1].date(),
                model_version=model_version,
            )
        )
    if result is None or result.status != "completed":
        result = build_seed_fixture_backtest_response(model_version=model_version)

    return DashboardEvaluationSummary(
        model_version=result.model_version,
        source=result.source,
        status=result.status,
        num_predictions=result.num_predictions,
        num_resolved_outcomes=result.num_resolved_outcomes,
        win_rate=result.win_rate,
        brier_score=result.brier_score,
        log_loss=result.log_loss,
        paper_roi=result.paper_roi,
        paper_total_pnl=result.paper_total_pnl,
        max_drawdown=result.max_drawdown,
        sample_size_note=result.sample_size_note,
        calibration_buckets=result.calibration_buckets,
    )


@router.get("/summary", response_model=DashboardSummaryRead)
def get_dashboard_summary(
    market_limit: int = Query(default=10, gt=0, le=50),
    opportunity_limit: int = Query(default=10, gt=0, le=50),
    trade_limit: int = Query(default=10, gt=0, le=50),
    model_version: str = "baseline_precip_v1",
    db: Session = Depends(get_db),
) -> DashboardSummaryRead:
    open_trades = list(
        db.scalars(
            select(PaperTrade).where(PaperTrade.status == "OPEN").order_by(PaperTrade.created_at.desc()).limit(trade_limit)
        )
    )
    return DashboardSummaryRead(
        recent_markets=_recent_market_summaries(db, market_limit),
        opportunities=_opportunities(db, opportunity_limit),
        open_paper_trades=[PaperTradeRead.model_validate(trade) for trade in open_trades],
        evaluation_summary=_evaluation_summary(db, model_version),
    )
