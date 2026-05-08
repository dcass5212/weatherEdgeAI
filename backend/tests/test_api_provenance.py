from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Market, MarketPriceSnapshot, ParsedMarket, Prediction, WeatherForecastSnapshot


def _dt(hour: int) -> datetime:
    return datetime(2026, 5, 7, hour, tzinfo=timezone.utc)


def test_run_prediction_records_exact_latest_parsed_market_and_forecast_snapshot(
    client: TestClient,
    db_session: Session,
) -> None:
    market = Market(
        source="mock",
        source_market_id="prediction-provenance-market",
        question="Will New York City get more than 1 inch of rain on May 5?",
        category="weather",
    )
    db_session.add(market)
    db_session.flush()

    older_parse = ParsedMarket(
        market_id=market.id,
        location_name="Chicago",
        latitude=41.8781,
        longitude=-87.6298,
        metric="precipitation",
        operator=">",
        threshold_value=1.0,
        threshold_unit="inch",
        parse_confidence=0.8,
        parser_version="regex_precip_v1",
        created_at=_dt(1),
        updated_at=_dt(1),
    )
    latest_parse = ParsedMarket(
        market_id=market.id,
        location_name="New York City",
        latitude=40.7128,
        longitude=-74.006,
        metric="precipitation",
        operator=">",
        threshold_value=1.0,
        threshold_unit="inch",
        parse_confidence=0.8,
        parser_version="regex_precip_v1",
        created_at=_dt(2),
        updated_at=_dt(2),
    )
    db_session.add_all([older_parse, latest_parse])
    db_session.flush()

    older_forecast = WeatherForecastSnapshot(
        parsed_market_id=latest_parse.id,
        forecast_source="fixture",
        forecast_timestamp=_dt(3),
        forecast_precip_total=0.2,
        forecast_precip_unit="inch",
        raw_json={"fixture": "older"},
    )
    latest_forecast = WeatherForecastSnapshot(
        parsed_market_id=latest_parse.id,
        forecast_source="fixture",
        forecast_timestamp=_dt(4),
        forecast_precip_total=1.6,
        forecast_precip_unit="inch",
        raw_json={"fixture": "latest"},
    )
    db_session.add_all([older_forecast, latest_forecast])
    db_session.commit()

    response = client.post(f"/predictions/run/{market.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["market_id"] == market.id
    assert body["parsed_market_id"] == latest_parse.id
    assert body["forecast_snapshot_id"] == latest_forecast.id
    assert body["features_json"]["forecast_precip_total"] == 1.6


def test_strategy_evaluation_records_exact_latest_price_snapshot_and_exposes_prediction_provenance(
    client: TestClient,
    db_session: Session,
) -> None:
    market = Market(
        source="mock",
        source_market_id="strategy-provenance-market",
        question="Will New York City get more than 1 inch of rain on May 5?",
        category="weather",
    )
    db_session.add(market)
    db_session.flush()

    parsed_market = ParsedMarket(
        market_id=market.id,
        location_name="New York City",
        latitude=40.7128,
        longitude=-74.006,
        metric="precipitation",
        operator=">",
        threshold_value=1.0,
        threshold_unit="inch",
        parse_confidence=0.8,
        parser_version="regex_precip_v1",
    )
    db_session.add(parsed_market)
    db_session.flush()

    forecast = WeatherForecastSnapshot(
        parsed_market_id=parsed_market.id,
        forecast_source="fixture",
        forecast_timestamp=_dt(1),
        forecast_precip_total=1.6,
        forecast_precip_unit="inch",
        raw_json={"fixture": "forecast"},
    )
    db_session.add(forecast)
    db_session.flush()

    prediction = Prediction(
        market_id=market.id,
        parsed_market_id=parsed_market.id,
        forecast_snapshot_id=forecast.id,
        model_version="baseline_precip_v1",
        p_yes=0.75,
        p_no=0.25,
        confidence="medium",
        features_json={"forecast_precip_total": 1.6},
    )
    older_price = MarketPriceSnapshot(
        market_id=market.id,
        yes_price=0.55,
        no_price=0.45,
        timestamp=_dt(2),
        raw_json={"fixture": "older"},
    )
    latest_price = MarketPriceSnapshot(
        market_id=market.id,
        yes_price=0.44,
        no_price=0.56,
        timestamp=_dt(3),
        raw_json={"fixture": "latest"},
    )
    db_session.add_all([prediction, older_price, latest_price])
    db_session.commit()

    response = client.post(f"/strategy/evaluate/{market.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["market_id"] == market.id
    assert body["prediction_id"] == prediction.id
    assert body["parsed_market_id"] == parsed_market.id
    assert body["forecast_snapshot_id"] == forecast.id
    assert body["price_snapshot_id"] == latest_price.id
    assert body["market_price_yes"] == 0.44
    assert body["model_probability_yes"] == 0.75
