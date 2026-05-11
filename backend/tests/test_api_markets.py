import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import routes_markets
from app.db.models import EVRecommendation, Market, PaperTrade, Prediction, WeatherForecastSnapshot
from app.markets.polymarket_client import PublicMarketDataError
from app.weather.geocoding import GeocodedLocation


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "market_prices"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


def test_get_markets_returns_json(client: TestClient) -> None:
    response = client.get("/markets")

    assert response.status_code == 200
    assert response.json() == []


def test_parse_seeded_market(client: TestClient) -> None:
    create_response = client.post(
        "/markets",
        json={
            "source": "mock",
            "source_market_id": "seeded-market-1",
            "question": "Will New York City get more than 1 inch of rain on May 5?",
            "category": "weather",
        },
    )
    assert create_response.status_code == 201
    market_id = create_response.json()["id"]

    response = client.post(f"/markets/{market_id}/parse")

    assert response.status_code == 200
    body = response.json()
    assert body["market_id"] == market_id
    assert body["location_name"] == "New York City"
    assert body["metric"] == "precipitation"
    assert body["operator"] == ">"
    assert body["threshold_value"] == 1.0
    assert body["parser_version"] == "regex_precip_v1"
    assert body["latitude"] == 40.7128
    assert body["longitude"] == -74.006
    assert body["raw_parse_json"]["geocoding"]["source"] == "fixture"


def test_parse_seeded_market_does_not_create_demo_price_snapshot(client: TestClient) -> None:
    create_response = client.post(
        "/markets",
        json={
            "source": "manual",
            "source_market_id": "seeded-market-no-price-snapshot",
            "question": "Will New York City get more than 1 inch of rain on May 5?",
            "category": "weather",
        },
    )
    assert create_response.status_code == 201
    market_id = create_response.json()["id"]

    parse_response = client.post(f"/markets/{market_id}/parse")
    assert parse_response.status_code == 200

    detail_response = client.get(f"/markets/{market_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["latest_price_snapshot"] is None


def test_parse_interval_market_requires_explicit_opt_in(client: TestClient) -> None:
    create_response = client.post(
        "/markets",
        json={
            "source": "mock",
            "source_market_id": "seeded-interval-market",
            "question": "Will Hong Kong have between 190-200mm of precipitation in May?",
            "category": "weather",
        },
    )
    assert create_response.status_code == 201
    market_id = create_response.json()["id"]

    default_response = client.post(f"/markets/{market_id}/parse")
    assert default_response.status_code == 422
    assert "interval probability modeling" in default_response.json()["detail"]

    enabled_response = client.post(f"/markets/{market_id}/parse?allow_interval_contracts=true")
    assert enabled_response.status_code == 200
    body = enabled_response.json()
    assert body["operator"] == "between"
    assert body["threshold_value"] == 190
    assert body["raw_parse_json"]["interval_upper_value"] == 200


def test_parse_seeded_market_keeps_unknown_location_without_coordinates(client: TestClient) -> None:
    create_response = client.post(
        "/markets",
        json={
            "source": "mock",
            "source_market_id": "seeded-market-unknown-location",
            "question": "Will Springfield get more than 1 inch of rain on May 5?",
            "category": "weather",
        },
    )
    assert create_response.status_code == 201
    market_id = create_response.json()["id"]

    response = client.post(f"/markets/{market_id}/parse")

    assert response.status_code == 200
    body = response.json()
    assert body["location_name"] == "Springfield"
    assert body["latitude"] is None
    assert body["longitude"] is None
    assert body["raw_parse_json"]["geocoding"] is None


def test_parse_seeded_market_can_use_external_geocoding(client: TestClient, monkeypatch) -> None:
    async def fake_resolve_location_for_market(location_name: str) -> GeocodedLocation | None:
        assert location_name == "Boston"
        return GeocodedLocation(
            name="Boston, Massachusetts, United States",
            latitude=42.3584,
            longitude=-71.0598,
            source="open_meteo_geocoding",
        )

    monkeypatch.setattr(routes_markets, "resolve_location_for_market", fake_resolve_location_for_market)
    create_response = client.post(
        "/markets",
        json={
            "source": "mock",
            "source_market_id": "seeded-market-boston",
            "question": "Will Boston get more than 1 inch of rain on May 5?",
            "category": "weather",
        },
    )
    assert create_response.status_code == 201
    market_id = create_response.json()["id"]

    response = client.post(f"/markets/{market_id}/parse")

    assert response.status_code == 200
    body = response.json()
    assert body["location_name"] == "Boston, Massachusetts, United States"
    assert body["latitude"] == 42.3584
    assert body["longitude"] == -71.0598
    assert body["raw_parse_json"]["geocoding"]["source"] == "open_meteo_geocoding"


def test_discover_mock_markets_persists_price_snapshot(client: TestClient) -> None:
    discover_response = client.post(
        "/markets/discover",
        json={"source": "mock", "keywords": ["rain"], "limit": 1},
    )

    assert discover_response.status_code == 200
    discovery = discover_response.json()
    assert discovery["discovered"] == 1
    assert discovery["created"] == 1
    assert discovery["updated"] == 0
    assert discovery["price_snapshots_created"] == 1

    markets_response = client.get("/markets")
    assert markets_response.status_code == 200
    market_id = markets_response.json()[0]["id"]

    detail_response = client.get(f"/markets/{market_id}")

    assert detail_response.status_code == 200
    snapshot = detail_response.json()["latest_price_snapshot"]
    assert snapshot["yes_price"] == 0.44
    assert snapshot["no_price"] == 0.56
    assert snapshot["spread"] == 0.02
    diagnostics = detail_response.json()["source_diagnostics"]
    assert diagnostics["price_status"] == "supported"
    assert diagnostics["capabilities"]["prices"] is True


def test_market_detail_workflow_status_walks_pipeline(client: TestClient, db_session: Session) -> None:
    create_response = client.post(
        "/markets",
        json={
            "source": "manual",
            "source_market_id": "workflow-status-manual",
            "question": "Will New York City get more than 1 inch of rain on May 5?",
            "category": "weather",
        },
    )
    assert create_response.status_code == 201
    manual_market_id = create_response.json()["id"]

    manual_detail = client.get(f"/markets/{manual_market_id}").json()
    assert manual_detail["workflow_status"] == {
        "has_price_snapshot": False,
        "has_parsed_market": False,
        "has_forecast_snapshot": False,
        "has_prediction": False,
        "has_ev_recommendation": False,
        "has_paper_trade": False,
        "next_action": "refresh_price_snapshot",
    }

    discover_response = client.post("/markets/discover", json={"source": "mock", "keywords": ["rain"], "limit": 1})
    assert discover_response.status_code == 200
    market_id = client.get("/markets").json()[0]["id"]

    price_only_detail = client.get(f"/markets/{market_id}").json()
    assert price_only_detail["workflow_status"]["has_price_snapshot"] is True
    assert price_only_detail["workflow_status"]["has_parsed_market"] is False
    assert price_only_detail["workflow_status"]["next_action"] == "parse_market"

    parse_response = client.post(f"/markets/{market_id}/parse")
    assert parse_response.status_code == 200
    parsed_market_id = parse_response.json()["id"]

    parsed_detail = client.get(f"/markets/{market_id}").json()
    assert parsed_detail["workflow_status"]["has_parsed_market"] is True
    assert parsed_detail["workflow_status"]["has_forecast_snapshot"] is False
    assert parsed_detail["workflow_status"]["next_action"] == "create_forecast"

    forecast = WeatherForecastSnapshot(
        parsed_market_id=parsed_market_id,
        forecast_source="test_fixture",
        forecast_timestamp=datetime(2026, 5, 4, 12, tzinfo=timezone.utc),
        target_start=datetime(2026, 5, 5, tzinfo=timezone.utc),
        target_end=datetime(2026, 5, 5, tzinfo=timezone.utc),
        forecast_precip_total=1.4,
        forecast_precip_unit="inch",
        raw_json={"source": "test"},
    )
    db_session.add(forecast)
    db_session.commit()

    forecast_detail = client.get(f"/markets/{market_id}").json()
    assert forecast_detail["latest_forecast_snapshot"]["id"] == forecast.id
    assert forecast_detail["latest_forecast_snapshot"]["forecast_precip_total"] == 1.4
    assert forecast_detail["workflow_status"]["has_forecast_snapshot"] is True
    assert forecast_detail["workflow_status"]["has_prediction"] is False
    assert forecast_detail["workflow_status"]["next_action"] == "run_prediction"

    market = db_session.get(Market, market_id)
    assert market is not None
    prediction = Prediction(
        market_id=market.id,
        parsed_market_id=parsed_market_id,
        forecast_snapshot_id=forecast.id,
        model_version="baseline_precip_v1",
        p_yes=0.7,
        p_no=0.3,
        confidence="medium",
    )
    db_session.add(prediction)
    db_session.commit()

    prediction_detail = client.get(f"/markets/{market_id}").json()
    assert prediction_detail["workflow_status"]["has_prediction"] is True
    assert prediction_detail["workflow_status"]["has_ev_recommendation"] is False
    assert prediction_detail["workflow_status"]["next_action"] == "evaluate_strategy"

    recommendation = EVRecommendation(
        prediction_id=prediction.id,
        market_price_yes=0.44,
        market_price_no=0.56,
        edge_yes=0.26,
        edge_no=-0.26,
        ev_yes=0.26,
        ev_no=-0.26,
        recommendation="PAPER_BUY_YES",
        paper_position_size=10.0,
    )
    db_session.add(recommendation)
    db_session.commit()

    ready_detail = client.get(f"/markets/{market_id}").json()
    assert ready_detail["workflow_status"]["has_ev_recommendation"] is True
    assert ready_detail["workflow_status"]["has_paper_trade"] is False
    assert ready_detail["workflow_status"]["next_action"] == "ready_for_paper_trade"
    assert ready_detail["latest_paper_trade"] is None

    trade = PaperTrade(
        market_id=market_id,
        recommendation_id=recommendation.id,
        side="YES",
        entry_price=0.44,
        quantity=10.0,
        status="OPEN",
    )
    db_session.add(trade)
    db_session.commit()

    trade_detail = client.get(f"/markets/{market_id}").json()
    assert trade_detail["latest_paper_trade"]["id"] == trade.id
    assert trade_detail["latest_paper_trade"]["side"] == "YES"
    assert trade_detail["workflow_status"]["has_paper_trade"] is True
    assert trade_detail["workflow_status"]["next_action"] == "monitor_paper_trade"


def test_refresh_polymarket_price_snapshot_fetches_fresh_source_payload(client: TestClient, monkeypatch) -> None:
    fresh_payload = {
        "id": "source-market-1",
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0.57", "0.43"]',
        "bestBid": "0.56",
        "bestAsk": "0.58",
        "liquidityNum": "900",
        "volumeNum": "1200",
    }

    class FakeRefreshService:
        async def fetch_price_payload(self, source: str, source_market_id: str, condition_id: str | None = None) -> dict:
            assert source == "polymarket"
            assert source_market_id == "source-market-1"
            assert condition_id == "condition-1"
            return fresh_payload

    monkeypatch.setattr(routes_markets, "MarketSourceRefreshService", FakeRefreshService)
    create_response = client.post(
        "/markets",
        json={
            "source": "polymarket",
            "source_market_id": "source-market-1",
            "condition_id": "condition-1",
            "question": "Will New York City get more than 1 inch of rain on May 5?",
            "category": "weather",
            "raw_json": {
                "market": {
                    "id": "source-market-1",
                    "outcomes": '["Yes", "No"]',
                    "outcomePrices": '["0.11", "0.89"]',
                }
            },
        },
    )
    assert create_response.status_code == 201
    market_id = create_response.json()["id"]

    response = client.post(f"/markets/{market_id}/price-snapshots/refresh")

    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["market_id"] == market_id
    assert snapshot["yes_price"] == 0.57
    assert snapshot["no_price"] == 0.43
    assert snapshot["best_bid_yes"] == 0.56
    assert snapshot["best_ask_yes"] == 0.58
    assert snapshot["liquidity"] == 900.0
    assert snapshot["volume"] == 1200.0
    assert client.get(f"/markets/{market_id}").json()["source_diagnostics"]["price_status"] == "supported"


def test_refresh_manual_market_price_snapshot_from_stored_payload(client: TestClient) -> None:
    create_response = client.post(
        "/markets",
        json={
            "source": "manual_fixture",
            "source_market_id": "source-market-1",
            "condition_id": "condition-1",
            "question": "Will New York City get more than 1 inch of rain on May 5?",
            "category": "weather",
            "raw_json": {
                "market": {
                    "id": "source-market-1",
                    "outcomes": '["Yes", "No"]',
                    "outcomePrices": '["0.57", "0.43"]',
                    "bestBid": "0.56",
                    "bestAsk": "0.58",
                    "liquidityNum": "900",
                    "volumeNum": "1200",
                }
            },
        },
    )
    assert create_response.status_code == 201
    market_id = create_response.json()["id"]

    response = client.post(f"/markets/{market_id}/price-snapshots/refresh")

    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["market_id"] == market_id
    assert snapshot["yes_price"] == 0.57
    assert snapshot["no_price"] == 0.43
    assert client.get(f"/markets/{market_id}").json()["source_diagnostics"]["price_status"] == "supported"


def test_refresh_market_price_snapshot_from_clob_token_price_map(client: TestClient, monkeypatch) -> None:
    raw_market = _fixture("clob_token_price_map.json")

    class FakeRefreshService:
        async def fetch_price_payload(self, source: str, source_market_id: str, condition_id: str | None = None) -> dict:
            return raw_market

    monkeypatch.setattr(routes_markets, "MarketSourceRefreshService", FakeRefreshService)
    create_response = client.post(
        "/markets",
        json={
            "source": "polymarket",
            "source_market_id": raw_market["id"],
            "condition_id": raw_market["conditionId"],
            "question": raw_market["question"],
            "category": "weather",
            "raw_json": {"market": raw_market},
        },
    )
    assert create_response.status_code == 201
    market_id = create_response.json()["id"]

    response = client.post(f"/markets/{market_id}/price-snapshots/refresh")

    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["market_id"] == market_id
    assert snapshot["yes_price"] == 0.5
    assert snapshot["no_price"] == 0.5
    assert snapshot["best_bid_yes"] == 0.48
    assert snapshot["best_ask_yes"] == 0.52
    assert snapshot["best_bid_no"] == 0.46
    assert snapshot["best_ask_no"] == 0.54
    assert snapshot["spread"] == 0.04


def test_refresh_market_price_snapshot_from_wrapped_gamma_payload(client: TestClient, monkeypatch) -> None:
    raw_market = _fixture("gamma_wrapped_market_payload.json")

    class FakeRefreshService:
        async def fetch_price_payload(self, source: str, source_market_id: str, condition_id: str | None = None) -> dict:
            assert source == "polymarket"
            assert source_market_id == "gamma-weather-wrapped"
            assert condition_id == "0xwrappedweather"
            return raw_market

    monkeypatch.setattr(routes_markets, "MarketSourceRefreshService", FakeRefreshService)
    create_response = client.post(
        "/markets",
        json={
            "source": "polymarket",
            "source_market_id": "gamma-weather-wrapped",
            "condition_id": "0xwrappedweather",
            "question": "Will New York City get more than 1 inch of rain tomorrow?",
            "category": "weather",
            "raw_json": {"market": raw_market["market"]},
        },
    )
    assert create_response.status_code == 201
    market_id = create_response.json()["id"]

    response = client.post(f"/markets/{market_id}/price-snapshots/refresh")

    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["market_id"] == market_id
    assert snapshot["yes_price"] == 0.46
    assert snapshot["no_price"] == 0.54
    assert snapshot["best_bid_yes"] == 0.45
    assert snapshot["best_ask_yes"] == 0.47
    assert snapshot["liquidity"] == 1234.5
    assert snapshot["volume"] == 6789.01
    diagnostics = client.get(f"/markets/{market_id}").json()["source_diagnostics"]
    assert diagnostics["price_status"] == "supported"
    assert diagnostics["capabilities"]["market_metadata"] is True
    assert diagnostics["capabilities"]["prices"] is True


def test_refresh_market_price_snapshot_combines_fresh_prices_with_stored_token_context(
    client: TestClient, monkeypatch
) -> None:
    fresh_payload = _fixture("clob_price_map_refresh_only.json")
    stored_market_payload = {
        "id": "gamma-weather-3",
        "conditionId": "0xgammaweather3",
        "question": "Will Chicago receive at least 0.5 inches of rain tomorrow?",
        "outcomes": '["Yes", "No"]',
        "clobTokenIds": '["yes-token-3", "no-token-3"]',
    }

    class FakeRefreshService:
        async def fetch_price_payload(self, source: str, source_market_id: str, condition_id: str | None = None) -> dict:
            assert source == "polymarket"
            assert source_market_id == "gamma-weather-3"
            assert condition_id == "0xgammaweather3"
            return fresh_payload

    monkeypatch.setattr(routes_markets, "MarketSourceRefreshService", FakeRefreshService)
    create_response = client.post(
        "/markets",
        json={
            "source": "polymarket",
            "source_market_id": stored_market_payload["id"],
            "condition_id": stored_market_payload["conditionId"],
            "question": stored_market_payload["question"],
            "category": "weather",
            "raw_json": {"market": stored_market_payload},
        },
    )
    assert create_response.status_code == 201
    market_id = create_response.json()["id"]

    response = client.post(f"/markets/{market_id}/price-snapshots/refresh")

    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["market_id"] == market_id
    assert snapshot["yes_price"] == 0.59
    assert snapshot["no_price"] == 0.41
    assert snapshot["best_bid_yes"] == 0.57
    assert snapshot["best_ask_yes"] == 0.61
    assert snapshot["best_bid_no"] == 0.41
    assert snapshot["best_ask_no"] == 0.45
    assert snapshot["spread"] == 0.04
    diagnostics = client.get(f"/markets/{market_id}").json()["source_diagnostics"]
    assert diagnostics["price_status"] == "supported"
    assert diagnostics["capabilities"]["prices"] is True


def test_refresh_market_price_snapshot_rejects_payload_without_prices(client: TestClient) -> None:
    create_response = client.post(
        "/markets",
        json={
            "source": "manual",
            "source_market_id": "source-market-no-price",
            "question": "Will New York City get more than 1 inch of rain on May 5?",
            "category": "weather",
            "raw_json": {"question": "No price fields here"},
        },
    )
    assert create_response.status_code == 201
    market_id = create_response.json()["id"]

    response = client.post(f"/markets/{market_id}/price-snapshots/refresh")

    assert response.status_code == 409
    assert response.json()["detail"] == "Source payload does not include supported price fields"
    diagnostics = client.get(f"/markets/{market_id}").json()["source_diagnostics"]
    assert diagnostics["price_status"] == "unsupported"
    assert diagnostics["unsupported_reasons"] == ["no_supported_price_fields"]


def test_refresh_market_price_snapshot_persists_specific_partial_diagnostics(
    client: TestClient, monkeypatch
) -> None:
    raw_market = _fixture("gamma_non_binary_outcomes.json")

    class FakeRefreshService:
        async def fetch_price_payload(self, source: str, source_market_id: str, condition_id: str | None = None) -> dict:
            assert source == "polymarket"
            assert source_market_id == raw_market["id"]
            assert condition_id == raw_market["conditionId"]
            return raw_market

    monkeypatch.setattr(routes_markets, "MarketSourceRefreshService", FakeRefreshService)
    create_response = client.post(
        "/markets",
        json={
            "source": "polymarket",
            "source_market_id": raw_market["id"],
            "condition_id": raw_market["conditionId"],
            "question": raw_market["question"],
            "category": "weather",
            "raw_json": {"market": raw_market},
        },
    )
    assert create_response.status_code == 201
    market_id = create_response.json()["id"]

    response = client.post(f"/markets/{market_id}/price-snapshots/refresh")

    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["yes_price"] is None
    assert snapshot["no_price"] is None
    assert snapshot["liquidity"] == 321.0
    diagnostics = client.get(f"/markets/{market_id}").json()["source_diagnostics"]
    assert diagnostics["price_status"] == "partial"
    assert diagnostics["capabilities"]["prices"] is False
    assert diagnostics["capabilities"]["liquidity"] is True
    assert diagnostics["unsupported_reasons"] == ["non_binary_outcomes", "missing_binary_yes_no_prices"]


def test_refresh_polymarket_price_snapshot_persists_rate_limit_diagnostics(client: TestClient, monkeypatch) -> None:
    class FakeRefreshService:
        async def fetch_price_payload(self, source: str, source_market_id: str, condition_id: str | None = None) -> dict:
            raise PublicMarketDataError(
                endpoint="/prices/condition-1",
                reason="rate_limited",
                attempts=3,
                status_code=429,
                retryable=True,
            )

    monkeypatch.setattr(routes_markets, "MarketSourceRefreshService", FakeRefreshService)
    create_response = client.post(
        "/markets",
        json={
            "source": "polymarket",
            "source_market_id": "source-market-rate-limited",
            "condition_id": "condition-1",
            "question": "Will New York City get more than 1 inch of rain on May 5?",
            "category": "weather",
            "raw_json": {
                "market": {
                    "id": "source-market-rate-limited",
                    "outcomes": '["Yes", "No"]',
                    "outcomePrices": '["0.44", "0.56"]',
                }
            },
        },
    )
    assert create_response.status_code == 201
    market_id = create_response.json()["id"]

    response = client.post(f"/markets/{market_id}/price-snapshots/refresh")

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "Market data source request failed" in detail
    diagnostics = client.get(f"/markets/{market_id}").json()["source_diagnostics"]
    assert diagnostics["price_status"] == "unsupported"
    assert diagnostics["unsupported_reasons"] == ["source_refresh_failed"]
    assert diagnostics["public_source_error"] == {
        "endpoint": "/prices/condition-1",
        "reason": "rate_limited",
        "attempts": 3,
        "status_code": 429,
        "retryable": True,
    }
