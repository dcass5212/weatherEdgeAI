from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EVRecommendation, Market, PaperTrade, ParsedMarket, Prediction, WeatherForecastSnapshot


def test_paper_demo_workflow_creates_full_paper_chain(client: TestClient, db_session: Session) -> None:
    response = client.post("/demo/paper-workflow", json={"quantity": 10})

    assert response.status_code == 200
    body = response.json()
    assert body["market_id"] is not None
    assert body["parsed_market_id"] is not None
    assert body["forecast_snapshot_id"] is not None
    assert body["prediction_id"] is not None
    assert body["recommendation_id"] is not None
    assert body["paper_trade_id"] is not None
    assert body["recommendation"] == "PAPER_BUY_YES"
    assert body["steps_completed"] == [
        "mock_discovery",
        "parsed_market",
        "fixture_forecast",
        "prediction",
        "ev_recommendation",
        "paper_trade",
    ]

    market = db_session.get(Market, body["market_id"])
    assert market is not None
    assert market.source_market_id == "mock-nyc-rain-tomorrow"
    assert db_session.get(ParsedMarket, body["parsed_market_id"]) is not None
    assert db_session.get(WeatherForecastSnapshot, body["forecast_snapshot_id"]) is not None
    assert db_session.get(Prediction, body["prediction_id"]) is not None
    assert db_session.get(EVRecommendation, body["recommendation_id"]) is not None
    trade = db_session.get(PaperTrade, body["paper_trade_id"])
    assert trade is not None
    assert trade.signal_snapshot_json["parsed_target"]["location_name"] == "New York City"
    assert trade.signal_snapshot_json["forecast"]["forecast_precip_total"] == 1.6
    assert trade.signal_snapshot_json["prediction"]["p_yes"] == 0.75
    assert trade.signal_snapshot_json["market_price"]["yes_price"] == 0.44
    assert trade.signal_snapshot_json["market_price"]["edge_yes"] == 0.31

    dashboard_response = client.get("/dashboard/summary")
    dashboard_response.raise_for_status()
    dashboard = dashboard_response.json()
    completed_market = next(
        market for market in dashboard["recent_markets"] if market["source_market_id"] == "mock-nyc-rain-tomorrow"
    )
    assert completed_market["workflow_status"]["next_action"] == "monitor_paper_trade"
    assert len(dashboard["open_paper_trades"]) == 1


def test_paper_demo_workflow_reuses_existing_chain(client: TestClient, db_session: Session) -> None:
    first_response = client.post("/demo/paper-workflow", json={"quantity": 10})
    first_response.raise_for_status()
    second_response = client.post("/demo/paper-workflow", json={"quantity": 10})
    second_response.raise_for_status()

    first = first_response.json()
    second = second_response.json()
    assert second["market_id"] == first["market_id"]
    assert second["parsed_market_id"] == first["parsed_market_id"]
    assert second["forecast_snapshot_id"] == first["forecast_snapshot_id"]
    assert second["prediction_id"] == first["prediction_id"]
    assert second["recommendation_id"] == first["recommendation_id"]
    assert second["paper_trade_id"] == first["paper_trade_id"]
    assert second["steps_completed"] == ["mock_discovery"]

    assert len(db_session.scalars(select(ParsedMarket)).all()) == 1
    assert len(db_session.scalars(select(WeatherForecastSnapshot)).all()) == 1
    assert len(db_session.scalars(select(Prediction)).all()) == 1
    assert len(db_session.scalars(select(EVRecommendation)).all()) == 1
    assert len(db_session.scalars(select(PaperTrade)).all()) == 1
