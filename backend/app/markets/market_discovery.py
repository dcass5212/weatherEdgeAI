"""Market discovery normalization.

This module keeps external market-source payloads behind a small adapter layer.
Routes persist normalized market metadata and source price snapshots while
preserving raw payloads for debugging and future replay.
"""

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any

from app.markets.polymarket_client import PolymarketClient


WEATHER_KEYWORDS = ("weather", "rain", "snow", "temperature", "precipitation", "inch")


@dataclass(frozen=True)
class DiscoveredPriceSnapshot:
    yes_price: float | None = None
    no_price: float | None = None
    best_bid_yes: float | None = None
    best_ask_yes: float | None = None
    best_bid_no: float | None = None
    best_ask_no: float | None = None
    spread: float | None = None
    liquidity: float | None = None
    volume: float | None = None
    timestamp: datetime | None = None
    raw_json: dict[str, Any] | None = None


@dataclass(frozen=True)
class DiscoveredMarket:
    source: str
    source_market_id: str
    condition_id: str | None
    question: str
    slug: str | None
    category: str | None
    active: bool
    closed: bool
    end_time: datetime | None
    resolution_source: str | None
    raw_json: dict[str, Any]
    source_diagnostics: dict[str, Any] | None = None
    price_snapshot: DiscoveredPriceSnapshot | None = None


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    return bool(value)


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _probability(value: Any) -> float | None:
    parsed = _as_float(value)
    if parsed is None or parsed < 0 or parsed > 1:
        return None
    return parsed


def _first_float(raw: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = _as_float(raw.get(key))
        if value is not None:
            return value
    return None


def _first_probability(raw: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = _probability(raw.get(key))
        if value is not None:
            return value
    return None


def _first_present(*values: float | None) -> float | None:
    for value in values:
        if value is not None:
            return value
    return None


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _token_id_map(raw: dict[str, Any]) -> dict[str, str]:
    outcomes = _json_list(raw.get("outcomes"))
    token_ids = _json_list(raw.get("clobTokenIds") or raw.get("clob_token_ids") or raw.get("tokenIds"))
    if not outcomes or not token_ids or len(outcomes) != len(token_ids):
        return {}

    mapped: dict[str, str] = {}
    for outcome, token_id in zip(outcomes, token_ids):
        if not isinstance(outcome, str) or token_id is None:
            continue
        normalized_outcome = outcome.strip().lower()
        if normalized_outcome in {"yes", "no"}:
            mapped[normalized_outcome] = str(token_id)
    return mapped


def _side_price(side_map: Any, side: str) -> float | None:
    if not isinstance(side_map, dict):
        return None
    return _probability(side_map.get(side) or side_map.get(side.lower()))


def _token_side_prices(raw: dict[str, Any]) -> tuple[float | None, float | None, float | None, float | None]:
    token_ids = _token_id_map(raw)
    prices = raw.get("prices") or raw.get("tokenPrices") or raw.get("token_prices")
    if not token_ids or not isinstance(prices, dict):
        return None, None, None, None

    yes_prices = prices.get(token_ids.get("yes"))
    no_prices = prices.get(token_ids.get("no"))
    yes_bid = _side_price(yes_prices, "SELL")
    yes_ask = _side_price(yes_prices, "BUY")
    no_bid = _side_price(no_prices, "SELL")
    no_ask = _side_price(no_prices, "BUY")
    return yes_bid, yes_ask, no_bid, no_ask


def _named_probability_from_items(
    items: list[Any],
    name_keys: tuple[str, ...],
    price_keys: tuple[str, ...],
) -> tuple[float | None, float | None]:
    yes_price: float | None = None
    no_price: float | None = None
    for item in items:
        if not isinstance(item, dict):
            continue
        name = None
        for key in name_keys:
            candidate = item.get(key)
            if isinstance(candidate, str) and candidate.strip():
                name = candidate.strip().lower()
                break
        if name not in {"yes", "no"}:
            continue
        price = _first_probability(item, price_keys)
        if price is None:
            continue
        if name == "yes":
            yes_price = price
        else:
            no_price = price
    return yes_price, no_price


def _outcome_prices(raw: dict[str, Any]) -> tuple[float | None, float | None]:
    prices = _json_list(raw.get("outcomePrices") or raw.get("outcome_prices"))
    token_yes, token_no = _named_probability_from_items(
        _json_list(raw.get("tokens")),
        name_keys=("outcome", "name", "side"),
        price_keys=("price", "midpoint", "mid", "lastTradePrice", "last_trade_price"),
    )
    if token_yes is not None or token_no is not None:
        return token_yes, token_no

    market_outcome_yes, market_outcome_no = _named_probability_from_items(
        _json_list(raw.get("outcomes")),
        name_keys=("outcome", "name", "side"),
        price_keys=("price", "midpoint", "mid", "lastTradePrice", "last_trade_price"),
    )
    if market_outcome_yes is not None or market_outcome_no is not None:
        return market_outcome_yes, market_outcome_no

    if not prices:
        return None, None

    outcomes = _json_list(raw.get("outcomes"))
    if outcomes and len(outcomes) == len(prices):
        mapped = {str(outcome).strip().lower(): _probability(price) for outcome, price in zip(outcomes, prices)}
        return mapped.get("yes"), mapped.get("no")

    yes_price = _probability(prices[0]) if len(prices) >= 1 else None
    no_price = _probability(prices[1]) if len(prices) >= 2 else None
    return yes_price, no_price


def _has_price_field(raw: dict[str, Any]) -> bool:
    return any(
        key in raw
        for key in (
            "outcomePrices",
            "outcome_prices",
            "tokens",
            "prices",
            "tokenPrices",
            "token_prices",
            "yesPrice",
            "yes_price",
            "priceYes",
            "price_yes",
            "bestBid",
            "best_bid",
            "bid",
            "bids",
            "bestAsk",
            "best_ask",
            "ask",
            "asks",
            "midpoint",
            "mid",
            "lastTradePrice",
            "last_trade_price",
        )
    )


def _has_parsed_price_value(price_snapshot: DiscoveredPriceSnapshot | None) -> bool:
    return bool(
        price_snapshot
        and (
            price_snapshot.yes_price is not None
            or price_snapshot.no_price is not None
            or price_snapshot.best_bid_yes is not None
            or price_snapshot.best_ask_yes is not None
            or price_snapshot.best_bid_no is not None
            or price_snapshot.best_ask_no is not None
        )
    )


def _top_book_price(raw: dict[str, Any], side: str) -> float | None:
    levels = raw.get(side)
    if not isinstance(levels, list) or not levels:
        return None
    first_level = levels[0]
    if isinstance(first_level, dict):
        return _probability(first_level.get("price"))
    return _probability(first_level)


def normalize_price_snapshot(raw: dict[str, Any]) -> DiscoveredPriceSnapshot | None:
    outcome_yes, outcome_no = _outcome_prices(raw)
    best_bid_yes = _first_probability(raw, ("bestBidYes", "best_bid_yes", "bestBid", "best_bid", "bid"))
    best_ask_yes = _first_probability(raw, ("bestAskYes", "best_ask_yes", "bestAsk", "best_ask", "ask"))
    token_bid_yes, token_ask_yes, token_bid_no, token_ask_no = _token_side_prices(raw)
    best_bid_yes = best_bid_yes if best_bid_yes is not None else token_bid_yes
    best_ask_yes = best_ask_yes if best_ask_yes is not None else token_ask_yes
    if best_bid_yes is None:
        best_bid_yes = _top_book_price(raw, "bids")
    if best_ask_yes is None:
        best_ask_yes = _top_book_price(raw, "asks")

    explicit_yes_price = _first_probability(raw, ("yesPrice", "yes_price", "priceYes", "price_yes", "midpoint", "mid"))
    last_trade_price = _first_probability(raw, ("lastTradePrice", "last_trade_price"))
    yes_price = _first_present(
        explicit_yes_price,
        outcome_yes,
        last_trade_price,
    )
    if yes_price is None and best_bid_yes is not None and best_ask_yes is not None:
        yes_price = round((best_bid_yes + best_ask_yes) / 2, 10)

    no_price = _first_present(_first_probability(raw, ("noPrice", "no_price", "priceNo", "price_no")), outcome_no)
    if no_price is None and yes_price is not None:
        no_price = round(1 - yes_price, 10)

    best_bid_no = _first_probability(raw, ("bestBidNo", "best_bid_no")) or token_bid_no
    best_ask_no = _first_probability(raw, ("bestAskNo", "best_ask_no")) or token_ask_no
    spread = _first_float(raw, ("spread", "bidAskSpread", "bid_ask_spread"))
    if spread is None and best_bid_yes is not None and best_ask_yes is not None:
        spread = round(best_ask_yes - best_bid_yes, 10)

    liquidity = _first_float(raw, ("liquidity", "liquidityNum", "liquidity_num"))
    volume = _first_float(raw, ("volume", "volumeNum", "volume_num"))
    timestamp = (
        _parse_datetime(raw.get("priceTimestamp") or raw.get("price_timestamp"))
        or _parse_datetime(raw.get("timestamp"))
        or _parse_datetime(raw.get("updatedAt") or raw.get("updated_at"))
        or _parse_datetime(raw.get("createdAt") or raw.get("created_at"))
    )

    values = (yes_price, no_price, best_bid_yes, best_ask_yes, best_bid_no, best_ask_no, spread, liquidity, volume)
    if all(value is None for value in values):
        return None

    return DiscoveredPriceSnapshot(
        yes_price=yes_price,
        no_price=no_price,
        best_bid_yes=best_bid_yes,
        best_ask_yes=best_ask_yes,
        best_bid_no=best_bid_no,
        best_ask_no=best_ask_no,
        spread=spread,
        liquidity=liquidity,
        volume=volume,
        timestamp=timestamp,
        raw_json=raw,
    )


def build_source_diagnostics(
    raw: dict[str, Any],
    price_snapshot: DiscoveredPriceSnapshot | None = None,
    source: str = "polymarket",
) -> dict[str, Any]:
    """Summarize source coverage without hiding unsupported payload shapes."""
    has_status = "active" in raw or "closed" in raw
    has_resolution = any(raw.get(key) for key in ("resolutionSource", "resolution_source", "rules", "description"))
    has_price_payload = _has_price_field(raw)
    has_parsed_price_value = _has_parsed_price_value(price_snapshot)
    has_top_of_book = bool(
        price_snapshot
        and (
            price_snapshot.best_bid_yes is not None
            or price_snapshot.best_ask_yes is not None
            or price_snapshot.best_bid_no is not None
            or price_snapshot.best_ask_no is not None
        )
    )
    has_binary_prices = bool(price_snapshot and price_snapshot.yes_price is not None and price_snapshot.no_price is not None)
    unsupported_reasons: list[str] = []
    if not has_price_payload:
        unsupported_reasons.append("no_supported_price_fields")
    if has_price_payload and not has_parsed_price_value:
        unsupported_reasons.append("price_fields_not_parseable")
    if price_snapshot is not None and not has_binary_prices:
        unsupported_reasons.append("missing_binary_yes_no_prices")

    price_status = "supported" if has_binary_prices else "partial" if price_snapshot is not None else "unsupported"
    return {
        "source": source,
        "capabilities": {
            "market_metadata": bool(_market_question(raw) and (raw.get("id") or raw.get("marketId") or raw.get("slug") or raw.get("conditionId"))),
            "condition_id": bool(raw.get("conditionId") or raw.get("condition_id")),
            "prices": has_binary_prices,
            "top_of_book": has_top_of_book,
            "liquidity": bool(price_snapshot and price_snapshot.liquidity is not None),
            "volume": bool(price_snapshot and price_snapshot.volume is not None),
            "status": has_status,
            "resolution_metadata": has_resolution,
        },
        "price_status": price_status,
        "unsupported_reasons": unsupported_reasons,
    }


def _text_matches_weather(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _market_question(raw: dict[str, Any], parent_event: dict[str, Any] | None = None) -> str | None:
    for key in ("question", "title", "name"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if parent_event:
        for key in ("title", "name"):
            value = parent_event.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _tag_text(raw: dict[str, Any]) -> list[str]:
    tags = raw.get("tags")
    if not isinstance(tags, list):
        return []

    values: list[str] = []
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        for key in ("label", "slug"):
            value = tag.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
    return values


def _search_context(raw: dict[str, Any], parent_event: dict[str, Any] | None = None) -> str:
    values: list[str] = []
    for source in (raw, parent_event or {}):
        for key in ("question", "title", "name", "category", "description"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
        values.extend(_tag_text(source))
    return " ".join(values)


def normalize_polymarket_market(raw: dict[str, Any], parent_event: dict[str, Any] | None = None) -> DiscoveredMarket | None:
    question = _market_question(raw, parent_event)
    source_market_id = raw.get("id") or raw.get("marketId") or raw.get("slug") or raw.get("conditionId")
    if question is None or source_market_id is None:
        return None

    category = raw.get("category")
    if category is None and parent_event:
        category = parent_event.get("category")

    end_time = raw.get("endDate") or raw.get("end_date") or raw.get("endTime") or raw.get("end_time")
    if end_time is None and parent_event:
        end_time = parent_event.get("endDate") or parent_event.get("end_date") or parent_event.get("endTime")

    price_snapshot = normalize_price_snapshot(raw)
    return DiscoveredMarket(
        source="polymarket",
        source_market_id=str(source_market_id),
        condition_id=raw.get("conditionId") or raw.get("condition_id"),
        question=question,
        slug=raw.get("slug"),
        category=str(category) if category else "weather",
        active=_as_bool(raw.get("active"), default=True),
        closed=_as_bool(raw.get("closed"), default=False),
        end_time=_parse_datetime(end_time),
        resolution_source=raw.get("resolutionSource") or raw.get("resolution_source"),
        raw_json={"market": raw, "event": parent_event} if parent_event else raw,
        source_diagnostics=build_source_diagnostics(raw, price_snapshot=price_snapshot, source="polymarket"),
        price_snapshot=price_snapshot,
    )


def _iter_candidate_markets(events: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any] | None]]:
    candidates: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
    for event in events:
        markets = event.get("markets")
        if isinstance(markets, list) and markets:
            candidates.extend((market, event) for market in markets if isinstance(market, dict))
        else:
            candidates.append((event, None))
    return candidates


def mock_weather_markets(limit: int, source: str = "mock") -> list[DiscoveredMarket]:
    markets = [
        DiscoveredMarket(
            source=source,
            source_market_id="mock-nyc-rain-may-5",
            condition_id="mock-condition-nyc-rain-may-5",
            question="Will New York City get more than 1 inch of rain on May 5?",
            slug="nyc-rain-more-than-1-inch-may-5",
            category="weather",
            active=True,
            closed=False,
            end_time=None,
            resolution_source=None,
            raw_json={
                "mock": True,
                "yesPrice": 0.44,
                "noPrice": 0.56,
                "spread": 0.02,
                "liquidity": 1000.0,
                "volume": 2500.0,
            },
            source_diagnostics={
                "source": source,
                "capabilities": {
                    "market_metadata": True,
                    "condition_id": True,
                    "prices": True,
                    "top_of_book": False,
                    "liquidity": True,
                    "volume": True,
                    "status": True,
                    "resolution_metadata": False,
                },
                "price_status": "supported",
                "unsupported_reasons": [],
            },
            price_snapshot=DiscoveredPriceSnapshot(
                yes_price=0.44,
                no_price=0.56,
                spread=0.02,
                liquidity=1000.0,
                volume=2500.0,
                raw_json={"mock": True, "source": "mock_discovery"},
            ),
        ),
        DiscoveredMarket(
            source=source,
            source_market_id="mock-chicago-rain-tomorrow",
            condition_id="mock-condition-chicago-rain-tomorrow",
            question="Will Chicago receive at least 0.5 inches of rain tomorrow?",
            slug="chicago-rain-at-least-half-inch-tomorrow",
            category="weather",
            active=True,
            closed=False,
            end_time=None,
            resolution_source=None,
            raw_json={
                "mock": True,
                "yesPrice": 0.51,
                "noPrice": 0.49,
                "spread": 0.03,
                "liquidity": 800.0,
                "volume": 1800.0,
            },
            source_diagnostics={
                "source": source,
                "capabilities": {
                    "market_metadata": True,
                    "condition_id": True,
                    "prices": True,
                    "top_of_book": False,
                    "liquidity": True,
                    "volume": True,
                    "status": True,
                    "resolution_metadata": False,
                },
                "price_status": "supported",
                "unsupported_reasons": [],
            },
            price_snapshot=DiscoveredPriceSnapshot(
                yes_price=0.51,
                no_price=0.49,
                spread=0.03,
                liquidity=800.0,
                volume=1800.0,
                raw_json={"mock": True, "source": "mock_discovery"},
            ),
        ),
    ]
    return markets[:limit]


class MarketDiscoveryService:
    def __init__(self, client: PolymarketClient | None = None) -> None:
        self.client = client or PolymarketClient()

    async def discover_weather_markets(
        self,
        source: str,
        keywords: list[str] | None = None,
        limit: int = 50,
    ) -> list[DiscoveredMarket]:
        if source == "mock":
            return mock_weather_markets(limit=limit, source=source)

        search_keywords = keywords or list(WEATHER_KEYWORDS)
        events = await self.client.fetch_active_events()
        discovered: list[DiscoveredMarket] = []
        for raw_market, parent_event in _iter_candidate_markets(events):
            question = _market_question(raw_market, parent_event)
            if question is None or not _text_matches_weather(_search_context(raw_market, parent_event), search_keywords):
                continue
            normalized = normalize_polymarket_market(raw_market, parent_event)
            if normalized is not None:
                discovered.append(normalized)
            if len(discovered) >= limit:
                break
        return discovered


class MarketSourceRefreshService:
    """Fetch fresh public market data without crossing into execution APIs."""

    def __init__(self, client: PolymarketClient | None = None) -> None:
        self.client = client or PolymarketClient()

    async def fetch_price_payload(
        self,
        source: str,
        source_market_id: str,
        condition_id: str | None = None,
    ) -> dict[str, Any]:
        if source != "polymarket":
            raise ValueError(f"fresh source refresh is not supported for source {source}")

        if condition_id:
            payload = await self.client.fetch_market_prices(condition_id)
            if payload:
                return payload

        return await self.client.fetch_market(source_market_id)
