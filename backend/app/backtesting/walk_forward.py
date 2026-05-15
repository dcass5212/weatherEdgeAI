"""Walk-forward backtest orchestration.

This module slices a requested evaluation period into rolling date windows and
reuses the persisted-record backtest runner for each window. The goal is to make
model evaluation less dependent on one static replay window while keeping the
single-window replay logic as the source of truth.
"""

from datetime import timedelta

from sqlalchemy.orm import Session

from app.backtesting.backtest_runner import BacktestRunner
from app.backtesting.schemas import (
    BacktestRunRequest,
    BacktestRunResponse,
    WalkForwardBacktestAggregate,
    WalkForwardBacktestRequest,
    WalkForwardBacktestResponse,
    WalkForwardWindowResult,
)


MAX_WALK_FORWARD_WINDOWS = 500


def _weighted_average(windows: list[BacktestRunResponse], metric_name: str) -> float | None:
    weighted_total = 0.0
    weight = 0
    for window in windows:
        metric = getattr(window, metric_name)
        if metric is None or window.num_predictions <= 0:
            continue
        weighted_total += metric * window.num_predictions
        weight += window.num_predictions
    return round(weighted_total / weight, 6) if weight else None


def _sum_optional(windows: list[BacktestRunResponse], metric_name: str) -> float | None:
    values = [getattr(window, metric_name) for window in windows if getattr(window, metric_name) is not None]
    return round(sum(values), 6) if values else None


def _worst_drawdown(windows: list[BacktestRunResponse]) -> float | None:
    values = [window.max_drawdown for window in windows if window.max_drawdown is not None]
    return round(max(values), 6) if values else None


def _aggregate(windows: list[BacktestRunResponse]) -> WalkForwardBacktestAggregate:
    return WalkForwardBacktestAggregate(
        window_count=len(windows),
        completed_window_count=len([window for window in windows if window.status == "completed"]),
        no_resolved_window_count=len([window for window in windows if window.status == "no_resolved_predictions"]),
        total_evaluated_predictions=sum(window.num_predictions for window in windows),
        total_resolved_outcomes=sum(window.num_resolved_outcomes for window in windows),
        total_ev_recommendations=sum(window.ev_recommendation_count for window in windows),
        total_paper_trades=sum(window.paper_trade_count for window in windows),
        average_brier_score=_weighted_average(windows, "brier_score"),
        average_log_loss=_weighted_average(windows, "log_loss"),
        average_win_rate=_weighted_average(windows, "win_rate"),
        paper_gross_pnl=_sum_optional(windows, "paper_gross_pnl"),
        paper_fee_cost=_sum_optional(windows, "paper_fee_cost"),
        paper_slippage_cost=_sum_optional(windows, "paper_slippage_cost"),
        paper_total_pnl=_sum_optional(windows, "paper_total_pnl"),
        worst_max_drawdown=_worst_drawdown(windows),
    )


def _interpretation_limits(payload: WalkForwardBacktestRequest, aggregate: WalkForwardBacktestAggregate) -> list[str]:
    limits: list[str] = []
    if payload.window_days < 30:
        limits.append("Short rolling windows are useful for workflow review, but each window may have sparse outcomes.")
    if payload.step_days < payload.window_days:
        limits.append("Overlapping windows reuse some evaluated records, so aggregate counts are not unique market counts.")
    if aggregate.total_evaluated_predictions < 30:
        limits.append("Total evaluated predictions remain below the insufficient-sample threshold for performance claims.")
    if aggregate.no_resolved_window_count:
        limits.append("Some windows had no resolved predictions and should be treated as coverage gaps.")
    return limits


class WalkForwardBacktestRunner:
    def __init__(self, db: Session) -> None:
        self.db = db

    def run(self, payload: WalkForwardBacktestRequest) -> WalkForwardBacktestResponse:
        if payload.end_date < payload.start_date:
            raise ValueError("end_date must be on or after start_date")

        runner = BacktestRunner(self.db)
        window_results: list[WalkForwardWindowResult] = []
        cursor = payload.start_date
        index = 0
        while cursor <= payload.end_date:
            if index >= MAX_WALK_FORWARD_WINDOWS:
                raise ValueError(f"walk-forward request produced more than {MAX_WALK_FORWARD_WINDOWS} windows")

            window_end = min(cursor + timedelta(days=payload.window_days - 1), payload.end_date)
            backtest = runner.run(
                BacktestRunRequest(
                    start_date=cursor,
                    end_date=window_end,
                    model_version=payload.model_version,
                    paper_fee_rate=payload.paper_fee_rate,
                    paper_slippage_rate=payload.paper_slippage_rate,
                )
            )
            window_results.append(
                WalkForwardWindowResult(
                    index=index,
                    start_date=cursor,
                    end_date=window_end,
                    backtest=backtest,
                )
            )
            cursor = cursor + timedelta(days=payload.step_days)
            index += 1

        backtest_windows = [window.backtest for window in window_results]
        aggregate = _aggregate(backtest_windows)
        status = "completed" if aggregate.completed_window_count else "no_resolved_predictions"
        return WalkForwardBacktestResponse(
            model_version=payload.model_version,
            start_date=payload.start_date,
            end_date=payload.end_date,
            window_days=payload.window_days,
            step_days=payload.step_days,
            status=status,
            aggregate=aggregate,
            windows=window_results,
            interpretation_limits=_interpretation_limits(payload, aggregate),
        )
