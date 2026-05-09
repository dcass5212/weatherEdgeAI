from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import (
    EVRecommendation,
    Market,
    MarketPriceSnapshot,
    PaperRunnerRun,
    PaperTrade,
    ParsedMarket,
    Prediction,
    ResolvedOutcome,
    WeatherForecastSnapshot,
)


def test_dashboard_summary_starts_empty(client: TestClient) -> None:
    response = client.get("/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["recent_markets"] == []
    assert body["opportunities"] == []
    assert body["open_paper_trades"] == []
    assert body["recent_paper_runs"] == []
    assert body["evaluation_summary"]["source"] == "seed_fixture"
    assert body["evaluation_summary"]["status"] == "completed"
    assert body["evaluation_summary"]["num_predictions"] == 3
    assert body["evaluation_summary"]["brier_score"] == 0.194167


def test_dashboard_summary_returns_paper_trading_inspection_chain(
    client: TestClient,
    db_session: Session,
) -> None:
    market = Market(
        source="mock",
        source_market_id="dashboard-market-1",
        condition_id="dashboard-condition-1",
        question="Will New York City get more than 1 inch of rain on May 5?",
        category="weather",
        active=True,
        closed=False,
        source_diagnostics={
            "price_status": "supported",
            "unsupported_reasons": [],
            "capabilities": {"prices": True},
        },
    )
    db_session.add(market)
    db_session.commit()

    price_snapshot = MarketPriceSnapshot(
        market_id=market.id,
        yes_price=0.44,
        no_price=0.56,
        timestamp=datetime(2026, 5, 4, 12, tzinfo=timezone.utc),
    )
    parsed_market = ParsedMarket(
        market_id=market.id,
        location_name="New York City",
        latitude=40.7128,
        longitude=-74.006,
        metric="precipitation",
        operator=">",
        threshold_value=1.0,
        threshold_unit="inch",
        target_start=datetime(2026, 5, 5, tzinfo=timezone.utc),
        target_end=datetime(2026, 5, 5, 23, 59, tzinfo=timezone.utc),
        parser_version="regex_precip_v1",
        parse_confidence=0.85,
    )
    db_session.add_all([price_snapshot, parsed_market])
    db_session.commit()

    forecast = WeatherForecastSnapshot(
        parsed_market_id=parsed_market.id,
        forecast_source="test_fixture",
        forecast_timestamp=datetime(2026, 5, 4, 12, tzinfo=timezone.utc),
        forecast_precip_total=1.6,
        forecast_precip_unit="inch",
    )
    db_session.add(forecast)
    db_session.commit()

    prediction = Prediction(
        market_id=market.id,
        parsed_market_id=parsed_market.id,
        forecast_snapshot_id=forecast.id,
        model_version="baseline_precip_v1",
        p_yes=0.75,
        p_no=0.25,
        confidence="medium",
    )
    db_session.add(prediction)
    db_session.commit()

    recommendation = EVRecommendation(
        prediction_id=prediction.id,
        price_snapshot_id=price_snapshot.id,
        market_price_yes=0.44,
        market_price_no=0.56,
        edge_yes=0.31,
        edge_no=-0.31,
        ev_yes=0.31,
        ev_no=-0.31,
        recommendation="PAPER_BUY_YES",
        paper_position_size=10.0,
    )
    db_session.add(recommendation)
    db_session.commit()

    trade = PaperTrade(
        market_id=market.id,
        recommendation_id=recommendation.id,
        side="YES",
        entry_price=0.44,
        quantity=10,
        status="OPEN",
    )
    outcome = ResolvedOutcome(
        market_id=market.id,
        actual_outcome="YES",
        actual_value=1.2,
        actual_unit="inch",
        resolution_source="test_fixture",
        resolved_at=datetime(2026, 5, 6, 2, tzinfo=timezone.utc),
    )
    db_session.add_all([trade, outcome])
    db_session.commit()

    runner_run = PaperRunnerRun(
        status="completed",
        source="polymarket",
        started_at=datetime(2026, 5, 5, 12, tzinfo=timezone.utc),
        completed_at=datetime(2026, 5, 5, 12, 1, tzinfo=timezone.utc),
        config_json={"create_trades": False, "max_trades": 1},
        discovered=25,
        processed=10,
        parsed=3,
        forecasts_created=2,
        predictions_created=2,
        recommendations_created=2,
        paper_trades_created=0,
        skipped_json={"missing_coordinates": 4, "wide_spread": 1},
        errors_json=[],
    )
    db_session.add(runner_run)
    db_session.commit()

    response = client.get("/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert len(body["recent_markets"]) == 1
    summary = body["recent_markets"][0]
    assert summary["market_id"] == market.id
    assert summary["source"] == "mock"
    assert summary["price_status"] == "supported"
    assert summary["unsupported_reasons"] == []
    assert summary["has_public_source_error"] is False
    assert summary["source_error_label"] is None
    assert summary["latest_price_snapshot_id"] == price_snapshot.id
    assert summary["latest_parsed_market_id"] == parsed_market.id
    assert summary["latest_forecast_snapshot_id"] == forecast.id
    assert summary["latest_prediction_id"] == prediction.id
    assert summary["latest_ev_recommendation_id"] == recommendation.id
    assert summary["latest_paper_trade_id"] == trade.id
    assert summary["parsed_target"] == "New York City precipitation > 1 inch"
    assert summary["forecast_precip_total"] == 1.6
    assert summary["forecast_precip_unit"] == "inch"
    assert summary["model_probability_yes"] == 0.75
    assert summary["market_price_yes"] == 0.44
    assert summary["edge_yes"] == 0.31
    assert summary["recommendation"] == "PAPER_BUY_YES"
    assert summary["paper_trade_status"] == "OPEN"
    assert summary["workflow_status"] == {
        "has_price_snapshot": True,
        "has_parsed_market": True,
        "has_forecast_snapshot": True,
        "has_prediction": True,
        "has_ev_recommendation": True,
        "has_paper_trade": True,
        "next_action": "monitor_paper_trade",
    }

    assert len(body["opportunities"]) == 1
    assert body["opportunities"][0]["market_id"] == market.id
    assert body["opportunities"][0]["recommendation"] == "PAPER_BUY_YES"

    assert len(body["open_paper_trades"]) == 1
    assert body["open_paper_trades"][0]["id"] == trade.id
    assert body["open_paper_trades"][0]["status"] == "OPEN"

    assert len(body["recent_paper_runs"]) == 1
    paper_run = body["recent_paper_runs"][0]
    assert paper_run["id"] == runner_run.id
    assert paper_run["status"] == "completed"
    assert paper_run["source"] == "polymarket"
    assert paper_run["dry_run"] is True
    assert paper_run["discovered"] == 25
    assert paper_run["processed"] == 10
    assert paper_run["parsed"] == 3
    assert paper_run["recommendations_created"] == 2
    assert paper_run["paper_trades_created"] == 0
    assert paper_run["skipped"] == {"missing_coordinates": 4, "wide_spread": 1}
    assert paper_run["errors"] == []

    evaluation = body["evaluation_summary"]
    assert evaluation["source"] == "persisted_records"
    assert evaluation["status"] == "completed"
    assert evaluation["num_predictions"] == 1
    assert evaluation["num_resolved_outcomes"] == 1
    assert evaluation["win_rate"] == 1.0
    assert evaluation["paper_roi"] == 1.272727
    assert evaluation["calibration_buckets"][3]["count"] == 1


def test_dashboard_summary_exposes_partial_source_diagnostics(
    client: TestClient,
    db_session: Session,
) -> None:
    market = Market(
        source="polymarket",
        source_market_id="dashboard-partial-market",
        condition_id="dashboard-partial-condition",
        question="Will New York City get more than 1 inch of rain tomorrow?",
        category="weather",
        active=True,
        closed=False,
        source_diagnostics={
            "price_status": "partial",
            "unsupported_reasons": ["non_binary_outcomes", "missing_binary_yes_no_prices"],
            "public_source_error": {
                "endpoint": "/prices/dashboard-partial-condition",
                "reason": "rate_limited",
                "attempts": 3,
                "status_code": 429,
                "retryable": True,
            },
        },
    )
    db_session.add(market)
    db_session.commit()

    response = client.get("/dashboard/summary")

    assert response.status_code == 200
    summary = response.json()["recent_markets"][0]
    assert summary["source"] == "polymarket"
    assert summary["price_status"] == "partial"
    assert summary["unsupported_reasons"] == ["non_binary_outcomes", "missing_binary_yes_no_prices"]
    assert summary["has_public_source_error"] is True
    assert summary["source_error_label"] == "rate_limited"


def test_dashboard_summary_labels_stale_supported_source_errors_as_stored_price(
    client: TestClient,
    db_session: Session,
) -> None:
    market = Market(
        source="polymarket",
        source_market_id="dashboard-stale-market",
        condition_id="dashboard-stale-condition",
        question="Will New York City get more than 1 inch of rain tomorrow?",
        category="weather",
        active=True,
        closed=False,
        source_diagnostics={
            "price_status": "stale_supported",
            "unsupported_reasons": ["source_refresh_failed"],
            "fallback_price_snapshot_used": True,
            "public_source_error": {
                "endpoint": "/prices/dashboard-stale-condition",
                "reason": "http_status_error",
                "attempts": 3,
                "status_code": 404,
                "retryable": False,
            },
        },
    )
    db_session.add(market)
    db_session.commit()

    response = client.get("/dashboard/summary")

    assert response.status_code == 200
    summary = response.json()["recent_markets"][0]
    assert summary["price_status"] == "stale_supported"
    assert summary["has_public_source_error"] is True
    assert summary["source_error_label"] == "using stored price"
