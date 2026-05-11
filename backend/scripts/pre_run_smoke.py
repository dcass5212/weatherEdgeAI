"""Pre-run readiness checks for bounded paper-market runs.

The checks are intentionally conservative: they verify database access,
migration shape, paper-mode safety settings, and a tiny fixture-backed replay
without creating live execution records.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import inspect, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.backtesting.backtest_runner import BacktestRunner
from app.backtesting.schemas import BacktestRunRequest
from app.config import settings
from app.db.models import PaperRunnerRun
from app.db.session import SessionLocal, engine


REQUIRED_TABLES = {
    "markets",
    "parsed_markets",
    "market_price_snapshots",
    "weather_forecast_snapshots",
    "predictions",
    "ev_recommendations",
    "paper_trades",
    "resolved_outcomes",
    "paper_runner_runs",
}


def _ok(message: str) -> None:
    print(f"OK: {message}")


def _fail(message: str) -> None:
    print(f"FAIL: {message}")


def run_smoke(*, require_runner_history: bool = False) -> int:
    failures: list[str] = []

    if settings.live_execution_allowed:
        failures.append("live execution is enabled; paper-run smoke requires paper/read-only safety settings")
    else:
        _ok(f"live execution disabled (TRADING_MODE={settings.TRADING_MODE}, LIVE_TRADING_ENABLED={settings.LIVE_TRADING_ENABLED})")

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        _ok("database connection succeeded")
    except Exception as exc:
        failures.append(f"database connection failed: {exc}")

    try:
        table_names = set(inspect(engine).get_table_names())
        missing = sorted(REQUIRED_TABLES - table_names)
        if missing:
            failures.append(f"database schema is missing required tables: {', '.join(missing)}")
        else:
            _ok("required workflow tables are present")
    except Exception as exc:
        failures.append(f"schema inspection failed: {exc}")

    try:
        with SessionLocal() as db:
            result = BacktestRunner(db).run(
                BacktestRunRequest(
                    start_date=date(2026, 5, 1),
                    end_date=date(2026, 5, 10),
                    seed_fixtures=True,
                )
            )
            if result.status != "completed" or result.num_predictions == 0:
                failures.append("fixture replay did not produce completed evaluation metrics")
            else:
                _ok(f"fixture replay completed with {result.num_predictions} predictions and gate={result.sample_size_gate}")

            runner_count = db.query(PaperRunnerRun).count()
            if require_runner_history and runner_count == 0:
                failures.append("no paper runner history found; run a dry run before starting a multi-day loop")
            else:
                _ok(f"paper runner history rows: {runner_count}")
    except Exception as exc:
        failures.append(f"fixture replay check failed: {exc}")

    if failures:
        for failure in failures:
            _fail(failure)
        return 1

    _ok("pre-run smoke checks passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run paper-market readiness smoke checks.")
    parser.add_argument(
        "--require-runner-history",
        action="store_true",
        help="Fail when no previous paper runner records exist.",
    )
    args = parser.parse_args()
    return run_smoke(require_runner_history=args.require_runner_history)


if __name__ == "__main__":
    sys.exit(main())
