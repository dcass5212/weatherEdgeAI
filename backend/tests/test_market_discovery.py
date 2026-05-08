import json
from pathlib import Path

import pytest

from app.markets.market_discovery import (
    MarketDiscoveryService,
    MarketSourceRefreshService,
    build_source_diagnostics,
    normalize_polymarket_market,
    normalize_price_snapshot,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "market_prices"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


def test_normalize_polymarket_market_from_event_market() -> None:
    event = {"title": "Weather markets", "category": "Weather"}
    raw_market = {
        "id": "123",
        "conditionId": "condition-123",
        "question": "Will New York City get more than 1 inch of rain on May 5?",
        "slug": "nyc-rain",
        "active": True,
        "closed": False,
    }

    market = normalize_polymarket_market(raw_market, event)

    assert market is not None
    assert market.source == "polymarket"
    assert market.source_market_id == "123"
    assert market.condition_id == "condition-123"
    assert market.question == raw_market["question"]
    assert market.category == "Weather"
    assert market.source_diagnostics is not None
    assert market.source_diagnostics["price_status"] == "unsupported"
    assert "no_supported_price_fields" in market.source_diagnostics["unsupported_reasons"]


def test_normalize_polymarket_price_snapshot_from_outcome_prices() -> None:
    raw_market = _fixture("gamma_market_outcome_prices.json")

    snapshot = normalize_price_snapshot(raw_market)

    assert snapshot is not None
    assert snapshot.yes_price == 0.44
    assert snapshot.no_price == 0.56
    assert snapshot.liquidity == 1000.5
    assert snapshot.volume == 2500.0
    assert snapshot.timestamp is not None

    diagnostics = build_source_diagnostics(raw_market, snapshot)
    assert diagnostics["price_status"] == "supported"
    assert diagnostics["capabilities"]["prices"] is True
    assert diagnostics["capabilities"]["liquidity"] is True
    assert diagnostics["unsupported_reasons"] == []


def test_source_diagnostics_report_partial_price_payloads() -> None:
    raw_market = {
        "id": "partial-weather",
        "question": "Will Chicago receive at least 0.5 inches of rain tomorrow?",
        "liquidityNum": "900",
    }

    snapshot = normalize_price_snapshot(raw_market)
    diagnostics = build_source_diagnostics(raw_market, snapshot)

    assert snapshot is not None
    assert snapshot.liquidity == 900.0
    assert diagnostics["price_status"] == "partial"
    assert diagnostics["capabilities"]["prices"] is False
    assert diagnostics["capabilities"]["liquidity"] is True
    assert diagnostics["unsupported_reasons"] == ["no_supported_price_fields", "missing_binary_yes_no_prices"]


def test_normalize_price_snapshot_from_token_items() -> None:
    raw_market = {
        "tokens": [
            {"outcome": "Yes", "price": "0.62"},
            {"outcome": "No", "price": "0.38"},
        ],
        "bestBid": "0.61",
        "bestAsk": "0.63",
    }

    snapshot = normalize_price_snapshot(raw_market)

    assert snapshot is not None
    assert snapshot.yes_price == 0.62
    assert snapshot.no_price == 0.38
    assert snapshot.best_bid_yes == 0.61
    assert snapshot.best_ask_yes == 0.63
    assert snapshot.spread == 0.02


def test_normalize_price_snapshot_from_orderbook_midpoint() -> None:
    raw_book = _fixture("clob_orderbook_yes_token.json")

    snapshot = normalize_price_snapshot(raw_book)

    assert snapshot is not None
    assert snapshot.yes_price == 0.5
    assert snapshot.no_price == 0.5
    assert snapshot.best_bid_yes == 0.48
    assert snapshot.best_ask_yes == 0.52
    assert snapshot.spread == 0.04


def test_normalize_price_snapshot_from_clob_token_price_map() -> None:
    raw_market = _fixture("clob_token_price_map.json")

    snapshot = normalize_price_snapshot(raw_market)

    assert snapshot is not None
    assert snapshot.yes_price == 0.5
    assert snapshot.no_price == 0.5
    assert snapshot.best_bid_yes == 0.48
    assert snapshot.best_ask_yes == 0.52
    assert snapshot.best_bid_no == 0.46
    assert snapshot.best_ask_no == 0.54
    assert snapshot.spread == 0.04
    assert snapshot.liquidity == 750.0
    assert snapshot.volume == 1600.0


def test_source_diagnostics_report_unparseable_price_fields_with_liquidity() -> None:
    raw_market = _fixture("gamma_malformed_price_fields.json")

    snapshot = normalize_price_snapshot(raw_market)
    diagnostics = build_source_diagnostics(raw_market, snapshot)

    assert snapshot is not None
    assert snapshot.yes_price is None
    assert snapshot.no_price is None
    assert snapshot.liquidity == 246.4459
    assert snapshot.volume == 110.23
    assert diagnostics["price_status"] == "partial"
    assert diagnostics["capabilities"]["prices"] is False
    assert diagnostics["capabilities"]["liquidity"] is True
    assert diagnostics["unsupported_reasons"] == ["price_fields_not_parseable", "missing_binary_yes_no_prices"]


@pytest.mark.anyio
async def test_discovery_filters_weather_markets() -> None:
    class FakeClient:
        async def fetch_active_events(self) -> list[dict]:
            return [
                {
                    "title": "Weather event",
                    "markets": [
                        {
                            "id": "weather-1",
                            "question": "Will Chicago receive at least 0.5 inches of rain tomorrow?",
                            "active": True,
                            "closed": False,
                        },
                        {
                            "id": "sports-1",
                            "question": "Will a team win tonight?",
                            "active": True,
                            "closed": False,
                        },
                    ],
                }
            ]

    markets = await MarketDiscoveryService(client=FakeClient()).discover_weather_markets(
        source="polymarket",
        keywords=["rain"],
        limit=10,
    )

    assert len(markets) == 1
    assert markets[0].source_market_id == "weather-1"


@pytest.mark.anyio
async def test_discovery_matches_weather_context_from_parent_event() -> None:
    event = _fixture("gamma_space_weather_event.json")

    class FakeClient:
        async def fetch_active_events(self) -> list[dict]:
            return [event]

    markets = await MarketDiscoveryService(client=FakeClient()).discover_weather_markets(
        source="polymarket",
        keywords=["weather"],
        limit=10,
    )

    assert len(markets) == 1
    assert markets[0].source_market_id == "2126654"
    assert markets[0].question == "Will there be exactly 1 major space event this week?"
    assert markets[0].category == "Weather"
    assert markets[0].raw_json["event"]["title"] == "How many major Space Weather events this week? (May 3 - May 9)"
    assert markets[0].source_diagnostics["price_status"] == "supported"
    assert markets[0].price_snapshot is not None
    assert markets[0].price_snapshot.yes_price == 0.325
    assert markets[0].price_snapshot.no_price == 0.675


@pytest.mark.anyio
async def test_source_refresh_service_fetches_polymarket_price_payload_by_condition_id() -> None:
    raw_market = _fixture("clob_token_price_map.json")

    class FakeClient:
        async def fetch_market_prices(self, condition_id: str) -> dict:
            assert condition_id == raw_market["conditionId"]
            return raw_market

        async def fetch_market(self, market_id: str) -> dict:
            raise AssertionError("condition_id price refresh should be preferred when available")

    payload = await MarketSourceRefreshService(client=FakeClient()).fetch_price_payload(
        source="polymarket",
        source_market_id=raw_market["id"],
        condition_id=raw_market["conditionId"],
    )

    assert payload == raw_market
