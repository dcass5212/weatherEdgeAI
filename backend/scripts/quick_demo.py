"""Run the fastest deterministic WeatherEdge AI demo.

This script is meant for first-pass review: it uses an in-memory SQLite
database, exercises FastAPI routes in-process, keeps execution paper-only, and
does not require PostgreSQL, Docker, frontend setup, or network access.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


def _use_sqlite_memory_database() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db


def _request(client: TestClient, method: str, path: str, **kwargs: Any) -> dict[str, Any] | list[dict[str, Any]]:
    response = client.request(method, path, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} failed with {response.status_code}: {response.text}")
    data = response.json()
    if not isinstance(data, dict | list):
        raise RuntimeError(f"{method} {path} returned unsupported JSON: {data!r}")
    return data


def _print_section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def _print_key_values(values: dict[str, Any], keys: tuple[str, ...]) -> None:
    for key in keys:
        print(f"{key}: {values.get(key)!r}")


def main() -> int:
    _use_sqlite_memory_database()

    try:
        with TestClient(app) as client:
            _print_section("Health")
            health = _request(client, "GET", "/health")
            assert isinstance(health, dict)
            _print_key_values(health, ("status", "service"))

            _print_section("Paper Workflow")
            demo = _request(client, "POST", "/demo/paper-workflow", json={"quantity": 10})
            assert isinstance(demo, dict)
            _print_key_values(
                demo,
                (
                    "market_id",
                    "parsed_market_id",
                    "forecast_snapshot_id",
                    "prediction_id",
                    "recommendation_id",
                    "paper_trade_id",
                    "recommendation",
                    "message",
                ),
            )
            print(f"steps_completed: {', '.join(demo.get('steps_completed', []))}")

            _print_section("Market Detail")
            detail = _request(client, "GET", f"/markets/{demo['market_id']}")
            assert isinstance(detail, dict)
            workflow_status = detail.get("workflow_status", {})
            latest_prediction = detail.get("latest_prediction") or {}
            latest_recommendation = detail.get("latest_ev_recommendation") or {}
            latest_trade = detail.get("latest_paper_trade") or {}
            print(f"question: {detail.get('question')!r}")
            print(f"next_action: {workflow_status.get('next_action')!r}")
            print(f"model_probability_yes: {latest_prediction.get('p_yes')!r}")
            print(f"market_price_yes: {latest_recommendation.get('market_price_yes')!r}")
            print(f"edge_yes: {latest_recommendation.get('edge_yes')!r}")
            print(f"paper_trade_status: {latest_trade.get('status')!r}")

            _print_section("Dashboard Summary")
            dashboard = _request(client, "GET", "/dashboard/summary")
            assert isinstance(dashboard, dict)
            print(f"recent_markets: {len(dashboard.get('recent_markets', []))}")
            print(f"open_paper_trades: {len(dashboard.get('open_paper_trades', []))}")
            evaluation = dashboard.get("evaluation_summary") or {}
            print(f"evaluation_source: {evaluation.get('source')!r}")
            print(f"evaluation_predictions: {evaluation.get('num_predictions')!r}")

            _print_section("Seed Backtest")
            backtest = _request(
                client,
                "POST",
                "/backtests/run",
                json={
                    "start_date": date(2026, 5, 1).isoformat(),
                    "end_date": date(2026, 5, 10).isoformat(),
                    "model_version": "baseline_precip_v1",
                    "seed_fixtures": True,
                },
            )
            assert isinstance(backtest, dict)
            _print_key_values(
                backtest,
                (
                    "status",
                    "source",
                    "num_predictions",
                    "win_rate",
                    "brier_score",
                    "log_loss",
                    "paper_total_pnl",
                    "paper_roi",
                    "sample_size_gate",
                    "sample_size_note",
                ),
            )

            _print_section("Safety Boundary")
            print("mode: paper-only demo")
            print("live_orders: not implemented or called")
            print("network: not required")
    finally:
        app.dependency_overrides.clear()

    return 0


if __name__ == "__main__":
    sys.exit(main())
