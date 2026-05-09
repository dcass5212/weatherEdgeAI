"""Run a deterministic WeatherEdge AI demo workflow through FastAPI routes.

The script exercises the local API in-process with FastAPI's TestClient. It
uses the configured database, preserves paper trading as the execution path,
and defaults to a fixture forecast so portfolio demos do not depend on network
access or live weather-provider availability.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
import sys
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.base import Base  # noqa: E402
from app.db.models import ParsedMarket, WeatherForecastSnapshot, utc_now  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


StepRunner = Callable[[TestClient], None]


def _fixture_forecast(parsed_market: ParsedMarket) -> WeatherForecastSnapshot:
    return WeatherForecastSnapshot(
        parsed_market_id=parsed_market.id,
        forecast_source="demo_fixture",
        forecast_timestamp=utc_now(),
        target_start=parsed_market.target_start,
        target_end=parsed_market.target_end,
        forecast_precip_total=1.6,
        forecast_precip_unit="inch",
        forecast_temp_max=72.0,
        forecast_temp_min=61.0,
        forecast_temp_unit="fahrenheit",
        raw_json={
            "demo_fixture": True,
            "note": "Deterministic forecast used by scripts/demo_workflow.py.",
        },
    )


async def _fetch_fixture_forecast(parsed_market: ParsedMarket) -> WeatherForecastSnapshot:
    return _fixture_forecast(parsed_market)


def _request(client: TestClient, method: str, path: str, **kwargs: Any) -> dict[str, Any] | list[dict[str, Any]]:
    response = client.request(method, path, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} failed with {response.status_code}: {response.text}")
    data = response.json()
    if not isinstance(data, dict | list):
        raise RuntimeError(f"{method} {path} returned unsupported JSON: {data!r}")
    return data


def _one_line(label: str, data: dict[str, Any], keys: tuple[str, ...]) -> None:
    values = ", ".join(f"{key}={data.get(key)!r}" for key in keys)
    print(f"{label}: {values}")


def _select_demo_market(markets: list[dict[str, Any]]) -> dict[str, Any]:
    for market in markets:
        if market.get("source_market_id") == "mock-nyc-rain-tomorrow":
            return market
    if not markets:
        raise RuntimeError("No markets returned after discovery")
    return markets[0]


def run_demo(client: TestClient, quantity: float) -> None:
    health = _request(client, "GET", "/health")
    _one_line("health", health, ("status", "service"))

    discovery = _request(
        client,
        "POST",
        "/markets/discover",
        json={"source": "mock", "keywords": ["rain", "weather"], "limit": 2},
    )
    _one_line("discovery", discovery, ("discovered", "created", "updated", "price_snapshots_created"))

    markets = _request(client, "GET", "/markets", params={"limit": 20})
    assert isinstance(markets, list)
    market = _select_demo_market(markets)
    market_id = market["id"]
    _one_line("market", market, ("id", "source_market_id", "question"))

    parsed = _request(client, "POST", f"/markets/{market_id}/parse")
    parsed_id = parsed["id"]
    _one_line("parsed", parsed, ("id", "location_name", "operator", "threshold_value", "threshold_unit"))

    forecast = _request(client, "POST", f"/weather/forecast/{parsed_id}")
    _one_line("forecast", forecast, ("id", "forecast_source", "forecast_precip_total", "forecast_precip_unit"))

    prediction = _request(client, "POST", f"/predictions/run/{market_id}")
    _one_line("prediction", prediction, ("id", "model_version", "p_yes", "p_no", "forecast_snapshot_id"))

    recommendation = _request(client, "POST", f"/strategy/evaluate/{market_id}")
    _one_line(
        "strategy",
        recommendation,
        ("id", "recommendation", "model_probability_yes", "market_price_yes", "edge_yes"),
    )

    if recommendation.get("recommendation") in {"PAPER_BUY_YES", "PAPER_BUY_NO"}:
        trade = _request(
            client,
            "POST",
            "/paper-trades",
            json={"recommendation_id": recommendation["id"], "quantity": quantity},
        )
        _one_line("paper_trade", trade, ("id", "side", "entry_price", "quantity", "status"))
    else:
        print(f"paper_trade: skipped because recommendation={recommendation.get('recommendation')!r}")

    detail = _request(client, "GET", f"/markets/{market_id}")
    assert isinstance(detail, dict)
    latest_trade = detail.get("latest_paper_trade")
    print(
        "market_detail: "
        f"latest_price_snapshot_id={detail['latest_price_snapshot']['id']}, "
        f"latest_forecast_snapshot_id={detail['latest_forecast_snapshot']['id']}, "
        f"latest_prediction_id={detail['latest_prediction']['id']}, "
        f"latest_ev_recommendation_id={detail['latest_ev_recommendation']['id']}, "
        f"latest_paper_trade_id={latest_trade['id'] if latest_trade else None}, "
        f"next_action={detail['workflow_status']['next_action']!r}"
    )

    opportunities = _request(client, "GET", "/strategy/opportunities", params={"min_edge": 0.03, "limit": 5})
    assert isinstance(opportunities, list)
    print(f"opportunities: count={len(opportunities)}")

    trades = _request(client, "GET", "/paper-trades", params={"status": "OPEN", "limit": 5})
    assert isinstance(trades, list)
    print(f"open_paper_trades: count={len(trades)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the WeatherEdge AI local paper-trading demo workflow.")
    parser.add_argument("--quantity", type=float, default=10.0, help="Paper-trade quantity to create from a buy signal.")
    parser.add_argument(
        "--use-open-meteo",
        action="store_true",
        help="Call the real Open-Meteo forecast route instead of the deterministic demo fixture.",
    )
    parser.add_argument(
        "--sqlite-memory",
        action="store_true",
        help="Use a temporary in-memory SQLite database for a smoke demo instead of the configured database.",
    )
    return parser.parse_args()


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


def main() -> None:
    args = parse_args()
    if args.sqlite_memory:
        _use_sqlite_memory_database()

    try:
        with TestClient(app) as client:
            if args.use_open_meteo:
                run_demo(client, quantity=args.quantity)
                return

            with patch("app.api.routes_weather.fetch_forecast_for_parsed_market", _fetch_fixture_forecast):
                run_demo(client, quantity=args.quantity)
    except OperationalError as exc:
        raise SystemExit(
            "Database connection failed. Start PostgreSQL with `docker compose up -d` "
            "from the repository root, then run `alembic upgrade head` from backend."
        ) from exc
    finally:
        app.dependency_overrides.clear()


if __name__ == "__main__":
    main()
