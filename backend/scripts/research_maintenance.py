"""Run post-run paper research maintenance.

This command keeps the paper-trading research loop repeatable: preview outcome
eligibility, optionally resolve completed weather markets, settle matching open
paper trades, generate an evidence report, and write timestamped JSON logs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.exc import OperationalError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.routes_backtests import preview_outcome_resolution_eligibility, resolve_weather_outcomes_batch  # noqa: E402
from app.api.routes_evaluation import get_evidence_report  # noqa: E402
from app.backtesting.schemas import WeatherOutcomeBatchResolveRequest  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    today = datetime.now(UTC).date()
    parser = argparse.ArgumentParser(description="Resolve eligible paper outcomes and write evidence logs.")
    parser.add_argument(
        "--provider",
        default="open_meteo_archive",
        choices=["open_meteo_archive", "noaa_cdo_daily"],
        help="Observed-weather provider used for outcome resolution.",
    )
    parser.add_argument("--limit", type=int, default=100, help="Maximum parsed markets to preview or resolve.")
    parser.add_argument(
        "--start-date",
        type=date.fromisoformat,
        default=today - timedelta(days=30),
        help="Evidence report start date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--end-date",
        type=date.fromisoformat,
        default=today,
        help="Evidence report end date in YYYY-MM-DD format.",
    )
    parser.add_argument("--model-version", default="baseline_precip_v1", help="Model version for evidence reporting.")
    parser.add_argument("--paper-fee-rate", type=float, default=0.0, help="Fee assumption for evidence paper PnL.")
    parser.add_argument(
        "--paper-slippage-rate",
        type=float,
        default=0.0,
        help="Settlement slippage assumption for evidence paper PnL.",
    )
    parser.add_argument(
        "--runner-limit",
        type=int,
        default=20,
        help="Recent paper-runner rows included in the evidence report.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(BACKEND_DIR / "research_logs"),
        help="Directory for timestamped JSON maintenance logs.",
    )
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="Write eligibility and evidence logs without resolving outcomes.",
    )
    parser.add_argument(
        "--include-existing-outcomes",
        action="store_true",
        help="Do not skip markets that already have an outcome for the selected provider.",
    )
    parser.add_argument(
        "--no-settle-open-trades",
        action="store_true",
        help="Create outcomes without settling matching open paper trades.",
    )
    args = parser.parse_args(argv)
    _validate_args(args)
    return args


def _validate_args(args: argparse.Namespace) -> None:
    if args.limit <= 0:
        raise SystemExit("--limit must be greater than 0")
    if args.runner_limit <= 0:
        raise SystemExit("--runner-limit must be greater than 0")
    if args.start_date > args.end_date:
        raise SystemExit("--start-date must be on or before --end-date")
    if not 0 <= args.paper_fee_rate <= 1:
        raise SystemExit("--paper-fee-rate must be between 0 and 1")
    if not 0 <= args.paper_slippage_rate <= 1:
        raise SystemExit("--paper-slippage-rate must be between 0 and 1")


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _write_json(output_dir: Path, name: str, payload: Any) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"{timestamp}_{name}.json"
    path.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True), encoding="utf-8")
    return path


async def run_maintenance(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    db = SessionLocal()
    try:
        preview = preview_outcome_resolution_eligibility(
            resolution_provider=args.provider,
            limit=args.limit,
            db=db,
        )
        preview_path = _write_json(output_dir, "outcome_eligibility_preview", preview)

        batch = None
        batch_path = None
        if not args.preview_only:
            batch = await resolve_weather_outcomes_batch(
                WeatherOutcomeBatchResolveRequest(
                    resolution_provider=args.provider,
                    limit=args.limit,
                    settle_open_trades=not args.no_settle_open_trades,
                    skip_existing_outcomes=not args.include_existing_outcomes,
                ),
                db=db,
            )
            batch_path = _write_json(output_dir, "outcome_resolution_batch", batch)

        evidence = get_evidence_report(
            start_date=args.start_date,
            end_date=args.end_date,
            model_version=args.model_version,
            paper_fee_rate=args.paper_fee_rate,
            paper_slippage_rate=args.paper_slippage_rate,
            runner_limit=args.runner_limit,
            db=db,
        )
        evidence_path = _write_json(output_dir, "evidence_report", evidence)

        print(f"preview: counts={preview.counts}, log={preview_path}")
        if batch is None:
            print("batch: skipped because --preview-only was set")
        else:
            print(
                "batch: "
                f"scanned={batch.scanned}, resolved={batch.resolved}, skipped={batch.skipped}, "
                f"errors={batch.errors}, settled_trades={batch.settled_trades}, log={batch_path}"
            )
        print(
            "evidence: "
            f"status={evidence.status}, predictions={evidence.backtest.num_predictions}, "
            f"outcomes={evidence.backtest.num_resolved_outcomes}, "
            f"gate={evidence.sample_size_gate}, log={evidence_path}"
        )
        return 0
    finally:
        db.close()


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(run_maintenance(args))
    except OperationalError as exc:
        raise SystemExit(
            "Database connection failed. Start PostgreSQL with `docker compose up -d` "
            "from the repository root, then run `alembic upgrade head` from backend."
        ) from exc


if __name__ == "__main__":
    sys.exit(main())
