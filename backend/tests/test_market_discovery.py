import json
from pathlib import Path

import httpx
import pytest

from app.markets.market_discovery import (
    MarketDiscoveryService,
    MarketSourceRefreshService,
    build_source_diagnostics,
    normalize_polymarket_market,
    normalize_price_snapshot,
)
from app.markets.polymarket_client import PolymarketClient, PublicMarketDataError


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


def test_normalize_price_snapshot_from_token_last_price_items() -> None:
    raw_market = _fixture("gamma_token_last_price_items.json")

    snapshot = normalize_price_snapshot(raw_market)
    diagnostics = build_source_diagnostics(raw_market, snapshot)

    assert snapshot is not None
    assert snapshot.yes_price == 0.63
    assert snapshot.no_price == 0.37
    assert snapshot.liquidity == 456.7
    assert snapshot.volume == 890.12
    assert diagnostics["price_status"] == "supported"
    assert diagnostics["capabilities"]["prices"] is True
    assert diagnostics["unsupported_reasons"] == []


def test_normalize_wrapped_gamma_market_payload() -> None:
    raw_market = _fixture("gamma_wrapped_market_payload.json")

    market = normalize_polymarket_market(raw_market)

    assert market is not None
    assert market.source_market_id == "gamma-weather-wrapped"
    assert market.condition_id == "0xwrappedweather"
    assert market.question == "Will New York City get more than 1 inch of rain tomorrow?"
    assert market.raw_json == raw_market
    assert market.price_snapshot is not None
    assert market.price_snapshot.yes_price == 0.46
    assert market.price_snapshot.no_price == 0.54
    assert market.price_snapshot.best_bid_yes == 0.45
    assert market.price_snapshot.best_ask_yes == 0.47
    assert market.price_snapshot.liquidity == 1234.5
    assert market.price_snapshot.volume == 6789.01
    assert market.price_snapshot.raw_json == raw_market
    assert market.source_diagnostics is not None
    assert market.source_diagnostics["price_status"] == "supported"
    assert market.source_diagnostics["capabilities"]["market_metadata"] is True
    assert market.source_diagnostics["capabilities"]["condition_id"] is True
    assert market.source_diagnostics["capabilities"]["prices"] is True


def test_normalize_price_snapshot_from_orderbook_midpoint() -> None:
    raw_book = _fixture("clob_orderbook_yes_token.json")

    snapshot = normalize_price_snapshot(raw_book)

    assert snapshot is not None
    assert snapshot.yes_price == 0.5
    assert snapshot.no_price == 0.5
    assert snapshot.best_bid_yes == 0.48
    assert snapshot.best_ask_yes == 0.52
    assert snapshot.spread == 0.04


def test_normalize_price_snapshot_from_nested_orderbook_midpoint() -> None:
    raw_book = _fixture("clob_nested_orderbook.json")

    snapshot = normalize_price_snapshot(raw_book)
    diagnostics = build_source_diagnostics(raw_book, snapshot)

    assert snapshot is not None
    assert snapshot.yes_price == 0.44
    assert snapshot.no_price == 0.56
    assert snapshot.best_bid_yes == 0.41
    assert snapshot.best_ask_yes == 0.47
    assert snapshot.spread == 0.06
    assert diagnostics["price_status"] == "supported"
    assert diagnostics["capabilities"]["prices"] is True
    assert diagnostics["capabilities"]["top_of_book"] is True


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


def test_source_diagnostics_report_nested_stats_without_price_fields() -> None:
    raw_market = _fixture("gamma_nested_stats_only.json")

    snapshot = normalize_price_snapshot(raw_market)
    diagnostics = build_source_diagnostics(raw_market, snapshot)

    assert snapshot is not None
    assert snapshot.yes_price is None
    assert snapshot.no_price is None
    assert snapshot.liquidity == 432.1
    assert snapshot.volume == 987.65
    assert diagnostics["price_status"] == "partial"
    assert diagnostics["capabilities"]["prices"] is False
    assert diagnostics["capabilities"]["liquidity"] is True
    assert diagnostics["capabilities"]["volume"] is True
    assert diagnostics["unsupported_reasons"] == ["no_supported_price_fields", "missing_binary_yes_no_prices"]


def test_normalize_price_snapshot_from_clob_liquidity_and_volume_fields() -> None:
    raw_market = {
        "id": "gamma-clob-stats-weather",
        "question": "Will New York City get more than 1 inch of rain tomorrow?",
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0.49", "0.51"]',
        "liquidityClob": 1021.74987,
        "volume24hrClob": 215.93647,
    }

    snapshot = normalize_price_snapshot(raw_market)
    diagnostics = build_source_diagnostics(raw_market, snapshot)

    assert snapshot is not None
    assert snapshot.yes_price == 0.49
    assert snapshot.no_price == 0.51
    assert snapshot.liquidity == 1021.74987
    assert snapshot.volume == 215.93647
    assert diagnostics["price_status"] == "supported"
    assert diagnostics["capabilities"]["liquidity"] is True
    assert diagnostics["capabilities"]["volume"] is True


def test_source_diagnostics_report_non_binary_outcomes() -> None:
    raw_market = _fixture("gamma_non_binary_outcomes.json")

    snapshot = normalize_price_snapshot(raw_market)
    diagnostics = build_source_diagnostics(raw_market, snapshot)

    assert snapshot is not None
    assert snapshot.yes_price is None
    assert snapshot.no_price is None
    assert snapshot.liquidity == 321.0
    assert diagnostics["price_status"] == "partial"
    assert diagnostics["capabilities"]["prices"] is False
    assert diagnostics["unsupported_reasons"] == ["non_binary_outcomes", "missing_binary_yes_no_prices"]


def test_source_diagnostics_report_outcome_price_length_mismatch() -> None:
    raw_market = _fixture("gamma_outcome_price_length_mismatch.json")

    snapshot = normalize_price_snapshot(raw_market)
    diagnostics = build_source_diagnostics(raw_market, snapshot)

    assert snapshot is not None
    assert snapshot.yes_price is None
    assert snapshot.no_price is None
    assert snapshot.liquidity == 222.0
    assert diagnostics["price_status"] == "partial"
    assert diagnostics["capabilities"]["prices"] is False
    assert diagnostics["unsupported_reasons"] == ["outcome_price_length_mismatch", "missing_binary_yes_no_prices"]


def test_source_diagnostics_report_missing_token_context() -> None:
    raw_market = _fixture("clob_missing_token_context.json")

    snapshot = normalize_price_snapshot(raw_market)
    diagnostics = build_source_diagnostics(raw_market, snapshot)

    assert snapshot is not None
    assert snapshot.yes_price is None
    assert snapshot.no_price is None
    assert snapshot.liquidity == 111.0
    assert diagnostics["price_status"] == "partial"
    assert diagnostics["capabilities"]["prices"] is False
    assert diagnostics["unsupported_reasons"] == ["missing_token_context", "missing_binary_yes_no_prices"]


def test_source_diagnostics_report_empty_orderbook() -> None:
    raw_market = _fixture("clob_empty_orderbook.json")

    snapshot = normalize_price_snapshot(raw_market)
    diagnostics = build_source_diagnostics(raw_market, snapshot)

    assert snapshot is not None
    assert snapshot.yes_price is None
    assert snapshot.no_price is None
    assert snapshot.liquidity == 10.5
    assert snapshot.volume == 20.5
    assert diagnostics["price_status"] == "partial"
    assert diagnostics["capabilities"]["prices"] is False
    assert diagnostics["capabilities"]["top_of_book"] is False
    assert diagnostics["unsupported_reasons"] == ["empty_orderbook", "missing_binary_yes_no_prices"]


@pytest.mark.anyio
async def test_polymarket_client_fetches_public_search_events() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/public-search"
        assert request.url.params["q"] == "weather"
        assert request.url.params["limit"] == "3"
        return httpx.Response(
            200,
            json={
                "events": [
                    {
                        "id": "event-1",
                        "title": "Weather markets",
                        "markets": [{"id": "market-1", "question": "Will it rain?"}],
                    }
                ]
            },
        )

    client = PolymarketClient(
        gamma_base_url="https://gamma.test",
        transport=httpx.MockTransport(handler),
    )

    events = await client.fetch_public_search_events("weather", limit=3)

    assert events == [
        {
            "id": "event-1",
            "title": "Weather markets",
            "markets": [{"id": "market-1", "question": "Will it rain?"}],
        }
    ]


@pytest.mark.anyio
async def test_polymarket_client_fetches_clob_market_info_by_condition_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/clob-markets/condition-1"
        return httpx.Response(200, json={"condition_id": "condition-1", "tokens": []})

    client = PolymarketClient(
        clob_base_url="https://clob.test",
        transport=httpx.MockTransport(handler),
    )

    payload = await client.fetch_clob_market_info("condition-1")

    assert payload == {"condition_id": "condition-1", "tokens": []}


@pytest.mark.anyio
async def test_discovery_uses_public_search_and_skips_closed_child_markets() -> None:
    class FakeClient:
        async def fetch_public_search_events(self, query: str, limit: int = 20) -> list[dict]:
            assert query == "rain"
            assert limit == 10
            return [
                {
                    "id": "rain-event",
                    "title": "Rain markets",
                    "category": "Weather",
                    "markets": [
                        {
                            "id": "open-rain-market",
                            "conditionId": "condition-open-rain",
                            "question": "Will New York City get more than 1 inch of rain tomorrow?",
                            "outcomes": '["Yes", "No"]',
                            "outcomePrices": '["0.41", "0.59"]',
                            "active": True,
                            "closed": False,
                        },
                        {
                            "id": "closed-rain-market",
                            "question": "Will Chicago receive at least 0.5 inches of rain tomorrow?",
                            "outcomes": '["Yes", "No"]',
                            "outcomePrices": '["0.90", "0.10"]',
                            "active": True,
                            "closed": True,
                        },
                    ],
                }
            ]

        async def fetch_active_events(self) -> list[dict]:
            raise AssertionError("public search should be used before active event fallback")

    markets = await MarketDiscoveryService(client=FakeClient()).discover_weather_markets(
        source="polymarket",
        keywords=["rain"],
        limit=10,
    )

    assert len(markets) == 1
    assert markets[0].source_market_id == "open-rain-market"
    assert markets[0].category == "Weather"
    assert markets[0].price_snapshot is not None
    assert markets[0].price_snapshot.yes_price == 0.41


@pytest.mark.anyio
async def test_discovery_falls_back_to_active_events_when_public_search_is_empty() -> None:
    class FakeClient:
        async def fetch_public_search_events(self, query: str, limit: int = 20) -> list[dict]:
            return []

        async def fetch_active_events(self) -> list[dict]:
            return [
                {
                    "id": "fallback-rain",
                    "question": "Will Chicago receive at least 0.5 inches of rain tomorrow?",
                    "outcomes": '["Yes", "No"]',
                    "outcomePrices": '["0.52", "0.48"]',
                    "active": True,
                    "closed": False,
                }
            ]

    markets = await MarketDiscoveryService(client=FakeClient()).discover_weather_markets(
        source="polymarket",
        keywords=["rain"],
        limit=10,
    )

    assert len(markets) == 1
    assert markets[0].source_market_id == "fallback-rain"
    assert markets[0].price_snapshot is not None
    assert markets[0].price_snapshot.yes_price == 0.52


@pytest.mark.anyio
async def test_discovery_combines_temperature_event_title_with_bucket_outcome() -> None:
    class FakeClient:
        async def fetch_public_search_events(self, query: str, limit: int = 20) -> list[dict]:
            return [
                {
                    "id": "temp-event",
                    "title": "Highest temperature in NYC on May 17?",
                    "category": "Weather",
                    "markets": [
                        {
                            "id": "temp-bucket-80-81",
                            "conditionId": "condition-temp",
                            "groupItemTitle": "80-81F",
                            "outcomes": '["Yes", "No"]',
                            "outcomePrices": '["0.41", "0.59"]',
                            "active": True,
                            "closed": False,
                        }
                    ],
                }
            ]

        async def fetch_active_events(self) -> list[dict]:
            raise AssertionError("public search should be used before active event fallback")

    markets = await MarketDiscoveryService(client=FakeClient()).discover_weather_markets(
        source="polymarket",
        keywords=["temperature"],
        limit=10,
    )

    assert len(markets) == 1
    assert markets[0].question == "Highest temperature in NYC on May 17 80-81F?"
    assert markets[0].price_snapshot is not None
    assert markets[0].price_snapshot.yes_price == 0.41


@pytest.mark.anyio
async def test_default_discovery_keywords_prioritize_precipitation_queries() -> None:
    queries: list[str] = []

    class FakeClient:
        async def fetch_public_search_events(self, query: str, limit: int = 20) -> list[dict]:
            queries.append(query)
            if query == "rain":
                return [
                    {
                        "id": "rain-event",
                        "title": "Rain markets",
                        "markets": [
                            {
                                "id": "rain-market",
                                "question": "Will New York City get more than 1 inch of rain tomorrow?",
                                "outcomes": '["Yes", "No"]',
                                "outcomePrices": '["0.41", "0.59"]',
                                "active": True,
                                "closed": False,
                            }
                        ],
                    }
                ]
            return []

        async def fetch_active_events(self) -> list[dict]:
            raise AssertionError("active event fallback should not run when search returns candidates")

    markets = await MarketDiscoveryService(client=FakeClient()).discover_weather_markets(
        source="polymarket",
        keywords=None,
        limit=1,
    )

    assert queries == ["rain"]
    assert len(markets) == 1
    assert markets[0].source_market_id == "rain-market"


@pytest.mark.anyio
async def test_polymarket_client_retries_rate_limited_public_requests() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json=[{"id": "weather-1", "question": "Will it rain?"}])

    client = PolymarketClient(
        gamma_base_url="https://gamma.test",
        max_retries=1,
        transport=httpx.MockTransport(handler),
    )

    events = await client.fetch_active_events()

    assert calls == 2
    assert events == [{"id": "weather-1", "question": "Will it rain?"}]


@pytest.mark.anyio
async def test_polymarket_client_reports_rate_limit_after_retry_budget() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    client = PolymarketClient(
        gamma_base_url="https://gamma.test",
        max_retries=1,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(PublicMarketDataError) as exc_info:
        await client.fetch_active_events()

    error = exc_info.value
    assert error.reason == "rate_limited"
    assert error.status_code == 429
    assert error.attempts == 2
    assert error.retryable is True


@pytest.mark.anyio
async def test_polymarket_client_reports_malformed_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"{not-json")

    client = PolymarketClient(
        gamma_base_url="https://gamma.test",
        max_retries=1,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(PublicMarketDataError) as exc_info:
        await client.fetch_active_events()

    error = exc_info.value
    assert error.reason == "malformed_json"
    assert error.status_code == 200
    assert error.attempts == 1
    assert error.retryable is False


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
        async def fetch_market(self, market_id: str) -> dict:
            assert market_id == raw_market["id"]
            return {"id": raw_market["id"], "question": raw_market["question"]}

        async def fetch_clob_market_info(self, condition_id: str) -> dict:
            assert condition_id == raw_market["conditionId"]
            return raw_market

    payload = await MarketSourceRefreshService(client=FakeClient()).fetch_price_payload(
        source="polymarket",
        source_market_id=raw_market["id"],
        condition_id=raw_market["conditionId"],
    )

    assert payload["id"] == raw_market["id"]
    assert payload["prices"] == raw_market["prices"]


@pytest.mark.anyio
async def test_source_refresh_service_falls_back_to_gamma_when_clob_condition_price_fails() -> None:
    gamma_payload = _fixture("gamma_market_outcome_prices.json")

    class FakeClient:
        async def fetch_market(self, market_id: str) -> dict:
            assert market_id == gamma_payload["id"]
            return gamma_payload

        async def fetch_clob_market_info(self, condition_id: str) -> dict:
            raise PublicMarketDataError(
                endpoint=f"/clob-markets/{condition_id}",
                reason="http_status_error",
                attempts=1,
                status_code=404,
                retryable=False,
            )

    payload = await MarketSourceRefreshService(client=FakeClient()).fetch_price_payload(
        source="polymarket",
        source_market_id=gamma_payload["id"],
        condition_id=gamma_payload["conditionId"],
    )

    assert payload == gamma_payload
