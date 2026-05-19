"""Run one public-market paper trading pass.

This command is intentionally paper-only. It discovers public weather markets,
advances eligible markets through the stored forecast/model/EV workflow, and
creates simulated paper trades only within conservative caps.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys

from sqlalchemy.exc import OperationalError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal  # noqa: E402
from app.markets.market_discovery import WEATHER_KEYWORDS  # noqa: E402
from app.modeling.model_registry import DEFAULT_MODEL_VERSION, available_model_versions  # noqa: E402
from app.strategy.paper_market_runner import PaperMarketRunnerConfig, PaperMarketRunnerReport, run_paper_market_once_recorded  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one safe public-market paper trading pass.")
    parser.add_argument("--source", default="polymarket", help="Market source to discover and process.")
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=list(WEATHER_KEYWORDS),
        help="Weather keywords used for public market discovery.",
    )
    parser.add_argument("--discovery-limit", type=int, default=50, help="Maximum public markets to discover.")
    parser.add_argument("--process-limit", type=int, default=25, help="Maximum stored markets to process.")
    parser.add_argument("--max-trades", type=int, default=3, help="Maximum paper trades to create in this run.")
    parser.add_argument("--quantity", type=float, default=1.0, help="Maximum simulated quantity per paper trade.")
    parser.add_argument("--min-liquidity", type=float, default=0.0, help="Skip markets below this liquidity when present.")
    parser.add_argument("--max-spread", type=float, default=0.15, help="Skip markets above this spread when present.")
    parser.add_argument(
        "--model-version",
        default=DEFAULT_MODEL_VERSION,
        choices=available_model_versions(),
        help="Prediction model version to use for this paper pass.",
    )
    parser.add_argument(
        "--max-open-trades",
        type=int,
        default=None,
        help="Skip new paper trades when this many simulated positions are already open. Uses the environment default when omitted.",
    )
    parser.add_argument(
        "--max-total-exposure",
        type=float,
        default=None,
        help="Skip new paper trades when total open simulated cost would exceed this amount. Uses the environment default when omitted.",
    )
    parser.add_argument(
        "--max-market-exposure",
        type=float,
        default=None,
        help="Skip new paper trades when simulated cost in one market would exceed this amount. Uses the environment default when omitted.",
    )
    parser.add_argument(
        "--max-location-exposure",
        type=float,
        default=None,
        help="Skip new paper trades when simulated cost in one parsed location would exceed this amount. Uses the environment default when omitted.",
    )
    parser.add_argument(
        "--entry-slippage-rate",
        type=float,
        default=None,
        help="Add this probability-point slippage to simulated paper entry fills. Uses the environment default when omitted.",
    )
    parser.add_argument(
        "--allow-stale-price-fallback",
        action="store_true",
        help="Allow a stored binary snapshot to be used after a public refresh failure.",
    )
    parser.add_argument(
        "--require-fresh-prices",
        action="store_true",
        help="Fail closed on refresh failures even when a stored binary snapshot exists.",
    )
    parser.add_argument(
        "--max-price-age-minutes",
        type=float,
        default=None,
        help="Skip markets whose latest price snapshot is older than this many minutes. Uses the environment default when omitted.",
    )
    parser.add_argument(
        "--max-forecast-age-hours",
        type=float,
        default=None,
        help="Skip predictions when the created forecast snapshot timestamp is older than this many hours. Uses the environment default when omitted.",
    )
    started_window_group = parser.add_mutually_exclusive_group()
    started_window_group.add_argument(
        "--allow-partial-started-windows",
        dest="allow_partial_started_windows",
        action="store_true",
        help="Use observed precipitation to date plus remaining forecast for target windows that already started.",
    )
    started_window_group.add_argument(
        "--skip-started-windows",
        dest="allow_partial_started_windows",
        action="store_false",
        help="Keep the older behavior and skip any target weather window that has already started.",
    )
    parser.set_defaults(allow_partial_started_windows=None)
    parser.add_argument(
        "--no-refresh-prices",
        action="store_true",
        help="Use stored discovery prices only instead of refreshing public prices before evaluation.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run discovery, forecasts, predictions, and EV evaluation but do not create paper trades.",
    )
    parser.add_argument(
        "--rehearsal",
        action="store_true",
        help="Alias for --dry-run that emphasizes preflight expected-trade reporting.",
    )
    interval_group = parser.add_mutually_exclusive_group()
    interval_group.add_argument(
        "--allow-interval-contracts",
        dest="allow_interval_contracts",
        action="store_true",
        help="Opt in to parsing and modeling between X-Y precipitation contracts.",
    )
    interval_group.add_argument(
        "--disable-interval-contracts",
        dest="allow_interval_contracts",
        action="store_false",
        help="Opt out of interval precipitation contracts even if the environment default is enabled.",
    )
    parser.set_defaults(allow_interval_contracts=None)
    parser.add_argument(
        "--interval-minutes",
        type=float,
        default=None,
        help="Run repeatedly with this many minutes between passes. Omit for one-shot mode.",
    )
    parser.add_argument("--max-hours", type=float, default=None, help="Stop loop mode after this many hours.")
    parser.add_argument("--max-runs", type=int, default=None, help="Stop loop mode after this many passes.")
    args = parser.parse_args(argv)
    if args.rehearsal:
        args.dry_run = True
    _validate_args(args)
    return args


def _validate_args(args: argparse.Namespace) -> None:
    if args.discovery_limit <= 0:
        raise SystemExit("--discovery-limit must be greater than 0")
    if args.process_limit <= 0:
        raise SystemExit("--process-limit must be greater than 0")
    if args.max_trades < 0:
        raise SystemExit("--max-trades cannot be negative")
    if args.quantity <= 0:
        raise SystemExit("--quantity must be greater than 0")
    if args.min_liquidity < 0:
        raise SystemExit("--min-liquidity cannot be negative")
    if args.max_spread < 0:
        raise SystemExit("--max-spread cannot be negative")
    if args.max_open_trades is not None and args.max_open_trades < 0:
        raise SystemExit("--max-open-trades cannot be negative")
    if args.max_total_exposure is not None and args.max_total_exposure < 0:
        raise SystemExit("--max-total-exposure cannot be negative")
    if args.max_market_exposure is not None and args.max_market_exposure < 0:
        raise SystemExit("--max-market-exposure cannot be negative")
    if args.max_location_exposure is not None and args.max_location_exposure < 0:
        raise SystemExit("--max-location-exposure cannot be negative")
    if args.entry_slippage_rate is not None and not 0 <= args.entry_slippage_rate <= 1:
        raise SystemExit("--entry-slippage-rate must be between 0 and 1")
    if args.allow_stale_price_fallback and args.require_fresh_prices:
        raise SystemExit("--allow-stale-price-fallback cannot be combined with --require-fresh-prices")
    if args.max_price_age_minutes is not None and args.max_price_age_minutes < 0:
        raise SystemExit("--max-price-age-minutes cannot be negative")
    if args.max_forecast_age_hours is not None and args.max_forecast_age_hours < 0:
        raise SystemExit("--max-forecast-age-hours cannot be negative")
    if args.interval_minutes is None:
        return
    if args.interval_minutes <= 0:
        raise SystemExit("--interval-minutes must be greater than 0")
    if args.max_hours is None and args.max_runs is None:
        raise SystemExit("loop mode requires --max-hours or --max-runs")
    if args.max_hours is not None and args.max_hours <= 0:
        raise SystemExit("--max-hours must be greater than 0")
    if args.max_runs is not None and args.max_runs <= 0:
        raise SystemExit("--max-runs must be greater than 0")


def _config_from_args(args: argparse.Namespace) -> PaperMarketRunnerConfig:
    return PaperMarketRunnerConfig(
        source=args.source,
        keywords=args.keywords,
        discovery_limit=args.discovery_limit,
        process_limit=args.process_limit,
        max_trades=args.max_trades,
        quantity=args.quantity,
        min_liquidity=args.min_liquidity,
        max_spread=args.max_spread,
        model_version=args.model_version,
        refresh_prices=not args.no_refresh_prices,
        create_trades=not args.dry_run,
        allow_interval_contracts=(
            args.allow_interval_contracts
            if args.allow_interval_contracts is not None
            else PaperMarketRunnerConfig().allow_interval_contracts
        ),
        max_price_age_minutes=(
            args.max_price_age_minutes
            if args.max_price_age_minutes is not None
            else PaperMarketRunnerConfig().max_price_age_minutes
        ),
        max_forecast_age_hours=(
            args.max_forecast_age_hours
            if args.max_forecast_age_hours is not None
            else PaperMarketRunnerConfig().max_forecast_age_hours
        ),
        allow_partial_started_windows=(
            args.allow_partial_started_windows
            if args.allow_partial_started_windows is not None
            else PaperMarketRunnerConfig().allow_partial_started_windows
        ),
        max_open_trades=(
            args.max_open_trades if args.max_open_trades is not None else PaperMarketRunnerConfig().max_open_trades
        ),
        max_total_exposure=(
            args.max_total_exposure
            if args.max_total_exposure is not None
            else PaperMarketRunnerConfig().max_total_exposure
        ),
        max_market_exposure=(
            args.max_market_exposure
            if args.max_market_exposure is not None
            else PaperMarketRunnerConfig().max_market_exposure
        ),
        max_location_exposure=(
            args.max_location_exposure
            if args.max_location_exposure is not None
            else PaperMarketRunnerConfig().max_location_exposure
        ),
        entry_slippage_rate=(
            args.entry_slippage_rate
            if args.entry_slippage_rate is not None
            else PaperMarketRunnerConfig().entry_slippage_rate
        ),
        allow_stale_price_fallback=(
            False
            if args.require_fresh_prices
            else (
                True
                if args.allow_stale_price_fallback
                else PaperMarketRunnerConfig().allow_stale_price_fallback
            )
        ),
    )


def _print_report(report: PaperMarketRunnerReport) -> None:
    print(
        "discovery: "
        f"discovered={report.discovered}, created={report.created}, updated={report.updated}, "
        f"price_snapshots_created={report.price_snapshots_created}"
    )
    print(
        "workflow: "
        f"processed={report.processed}, parsed={report.parsed}, forecasts_created={report.forecasts_created}, "
        f"predictions_created={report.predictions_created}, recommendations_created={report.recommendations_created}, "
        f"actionable_recommendations={report.actionable_recommendations}, "
        f"expected_paper_trades={report.expected_paper_trades}, paper_trades_created={report.paper_trades_created}, "
        f"stale_price_fallbacks_used={report.stale_price_fallbacks_used}"
    )
    if report.skipped:
        skipped = ", ".join(f"{reason}={count}" for reason, count in sorted(report.skipped.items()))
        print(f"skipped: {skipped}")
    else:
        print("skipped: none")
    if report.errors:
        for error in report.errors:
            print(f"error: {error}")


async def _run_once(args: argparse.Namespace) -> PaperMarketRunnerReport:
    db = SessionLocal()
    try:
        run = await run_paper_market_once_recorded(db=db, config=_config_from_args(args))
        if not isinstance(run.report_json, dict):
            raise RuntimeError("paper runner run completed without a report")
        return PaperMarketRunnerReport(
            discovered=run.discovered,
            created=run.created,
            updated=run.updated,
            price_snapshots_created=run.price_snapshots_created,
            processed=run.processed,
            parsed=run.parsed,
            forecasts_created=run.forecasts_created,
            predictions_created=run.predictions_created,
            recommendations_created=run.recommendations_created,
            actionable_recommendations=int(run.report_json.get("actionable_recommendations", 0)),
            expected_paper_trades=int(run.report_json.get("expected_paper_trades", 0)),
            paper_trades_created=run.paper_trades_created,
            stale_price_fallbacks_used=int(run.report_json.get("stale_price_fallbacks_used", 0)),
            skipped=run.skipped_json,
            errors=run.errors_json,
        )
    finally:
        db.close()


def _within_time_limit(started_at: datetime, max_hours: float | None, now: datetime) -> bool:
    if max_hours is None:
        return True
    return now < started_at + timedelta(hours=max_hours)


async def _run(args: argparse.Namespace) -> list[PaperMarketRunnerReport]:
    reports: list[PaperMarketRunnerReport] = []
    started_at = datetime.now(UTC)
    run_number = 0

    while True:
        if not _within_time_limit(started_at, args.max_hours, datetime.now(UTC)):
            break
        run_number += 1
        print(f"run: number={run_number}, started_at={datetime.now(UTC).isoformat()}")
        report = await _run_once(args)
        reports.append(report)
        _print_report(report)

        if args.interval_minutes is None:
            break
        if args.max_runs is not None and run_number >= args.max_runs:
            break
        if not _within_time_limit(started_at, args.max_hours, datetime.now(UTC)):
            break

        sleep_seconds = args.interval_minutes * 60
        if args.max_hours is not None:
            deadline = started_at + timedelta(hours=args.max_hours)
            remaining_seconds = (deadline - datetime.now(UTC)).total_seconds()
            if remaining_seconds <= 0:
                break
            sleep_seconds = min(sleep_seconds, remaining_seconds)
        print(f"sleep: seconds={sleep_seconds:g}")
        await asyncio.sleep(sleep_seconds)

    return reports


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(_run(args))
    except OperationalError as exc:
        raise SystemExit(
            "Database connection failed. Start PostgreSQL with `docker compose up -d` "
            "from the repository root, then run `alembic upgrade head` from backend."
        ) from exc


if __name__ == "__main__":
    main()
