import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import routes_markets
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
