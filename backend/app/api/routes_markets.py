"""Market API routes.

These endpoints expose the market workflow: manual market creation, source
discovery, parsing, and detail reads with the latest workflow snapshots.
Discovery also stores source price snapshots so strategy evaluation can use
persisted market data instead of transient route state.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Market, MarketPriceSnapshot, ParsedMarket, utc_now
from app.db.repositories import (
    get_market,
    latest_parsed_market,
    latest_prediction,
    latest_price_snapshot,
    latest_recommendation,
    list_markets,
)
from app.db.session import get_db
from app.markets.market_discovery import (
    DiscoveredPriceSnapshot,
    MarketDiscoveryService,
    MarketSourceRefreshService,
    build_source_diagnostics,
    normalize_price_snapshot,
)
from app.markets.market_parser import parse_precipitation_market
from app.markets.schemas import (
    MarketCreate,
    MarketDetailRead,
    MarketDiscoveryRequest,
    MarketDiscoveryResponse,
    MarketPriceSnapshotRead,
    MarketRead,
    ParsedMarketRead,
)
from app.weather.geocoding import resolve_location_for_market


router = APIRouter(prefix="/markets", tags=["markets"])


def _add_discovered_price_snapshot(
    db: Session,
    market: Market,
    discovered_price: DiscoveredPriceSnapshot | None,
) -> bool:
    if discovered_price is None:
        return False

    snapshot = MarketPriceSnapshot(
        market=market,
        yes_price=discovered_price.yes_price,
        no_price=discovered_price.no_price,
        best_bid_yes=discovered_price.best_bid_yes,
        best_ask_yes=discovered_price.best_ask_yes,
        best_bid_no=discovered_price.best_bid_no,
        best_ask_no=discovered_price.best_ask_no,
        spread=discovered_price.spread,
        liquidity=discovered_price.liquidity,
        volume=discovered_price.volume,
        timestamp=discovered_price.timestamp or utc_now(),
        raw_json=discovered_price.raw_json,
    )
    db.add(snapshot)
    return True


def _source_price_payload(market: Market) -> dict | None:
    if not isinstance(market.raw_json, dict):
        return None
    raw_market = market.raw_json.get("market")
    return raw_market if isinstance(raw_market, dict) else market.raw_json


def _merge_price_payload_with_market_context(stored_payload: dict | None, fresh_payload: dict) -> dict:
    if stored_payload is None:
        return fresh_payload

    context_keys = (
        "id",
        "marketId",
        "conditionId",
        "condition_id",
        "question",
        "title",
        "slug",
        "outcomes",
        "clobTokenIds",
        "clob_token_ids",
        "tokenIds",
    )
    context = {key: stored_payload[key] for key in context_keys if key in stored_payload and key not in fresh_payload}
    if not context:
        return fresh_payload
    return {**context, **fresh_payload}


def _source_refresh_error_diagnostics(market: Market, error: str) -> dict:
    return {
        "source": market.source,
        "capabilities": {
            "market_metadata": False,
            "condition_id": bool(market.condition_id),
            "prices": False,
            "top_of_book": False,
            "liquidity": False,
            "volume": False,
            "status": False,
            "resolution_metadata": False,
        },
        "price_status": "unsupported",
        "unsupported_reasons": ["source_refresh_failed"],
        "source_error": error,
    }


def _persist_price_snapshot_from_payload(
    db: Session,
    market: Market,
    raw_payload: dict,
    refresh_source: str,
) -> MarketPriceSnapshot | None:
    normalized = normalize_price_snapshot(raw_payload)
    market.source_diagnostics = build_source_diagnostics(raw_payload, price_snapshot=normalized, source=market.source)
    if normalized is None:
        return None

    snapshot = MarketPriceSnapshot(
        market_id=market.id,
        yes_price=normalized.yes_price,
        no_price=normalized.no_price,
        best_bid_yes=normalized.best_bid_yes,
        best_ask_yes=normalized.best_ask_yes,
        best_bid_no=normalized.best_bid_no,
        best_ask_no=normalized.best_ask_no,
        spread=normalized.spread,
        liquidity=normalized.liquidity,
        volume=normalized.volume,
        timestamp=normalized.timestamp or utc_now(),
        raw_json={
            "source": refresh_source,
            "payload": raw_payload,
            "source_diagnostics": market.source_diagnostics,
        },
    )
    db.add(snapshot)
    return snapshot


@router.get("", response_model=list[MarketRead])
def get_markets(
    active: bool | None = None,
    closed: bool | None = None,
    category: str | None = None,
    limit: int = Query(default=50, gt=0, le=200),
    db: Session = Depends(get_db),
) -> list[Market]:
    return list_markets(db, active=active, closed=closed, category=category, limit=limit)


@router.post("", response_model=MarketRead, status_code=201)
def create_market(payload: MarketCreate, db: Session = Depends(get_db)) -> Market:
    market = Market(**payload.model_dump())
    db.add(market)
    db.commit()
    db.refresh(market)
    return market


@router.post("/discover", response_model=MarketDiscoveryResponse)
async def discover_markets(payload: MarketDiscoveryRequest, db: Session = Depends(get_db)) -> MarketDiscoveryResponse:
    try:
        discovered_markets = await MarketDiscoveryService().discover_weather_markets(
            source=payload.source,
            keywords=payload.keywords,
            limit=payload.limit,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Market data source request failed: {exc}") from exc

    created = 0
    updated = 0
    price_snapshots_created = 0
    for discovered in discovered_markets:
        item = {
            "source": discovered.source,
            "source_market_id": discovered.source_market_id,
            "condition_id": discovered.condition_id,
            "question": discovered.question,
            "slug": discovered.slug,
            "category": discovered.category,
            "active": discovered.active,
            "closed": discovered.closed,
            "end_time": discovered.end_time,
            "resolution_source": discovered.resolution_source,
            "raw_json": discovered.raw_json,
            "source_diagnostics": discovered.source_diagnostics,
        }
        existing = db.scalars(
            select(Market).where(Market.source == item["source"], Market.source_market_id == item["source_market_id"])
        ).first()
        if existing is None:
            market = Market(**item)
            db.add(market)
            created += 1
        else:
            for key, value in item.items():
                setattr(existing, key, value)
            market = existing
            updated += 1
        if _add_discovered_price_snapshot(db, market, discovered.price_snapshot):
            price_snapshots_created += 1

    db.commit()
    return MarketDiscoveryResponse(
        discovered=len(discovered_markets),
        created=created,
        updated=updated,
        price_snapshots_created=price_snapshots_created,
    )


@router.get("/{market_id}", response_model=MarketDetailRead)
def get_market_detail(market_id: int, db: Session = Depends(get_db)) -> MarketDetailRead:
    market = get_market(db, market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")

    prediction = latest_prediction(db, market_id)
    ev_recommendation = latest_recommendation(db, prediction.id) if prediction else None
    data = MarketRead.model_validate(market).model_dump()
    data["latest_parsed_market"] = latest_parsed_market(db, market_id)
    data["latest_price_snapshot"] = latest_price_snapshot(db, market_id)
    data["latest_prediction"] = prediction
    data["latest_ev_recommendation"] = ev_recommendation
    return MarketDetailRead.model_validate(data)


@router.post("/{market_id}/price-snapshots/refresh", response_model=MarketPriceSnapshotRead)
async def refresh_market_price_snapshot(market_id: int, db: Session = Depends(get_db)) -> MarketPriceSnapshot:
    market = get_market(db, market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")

    refresh_source = "stored_market_payload_refresh"
    if market.source == "polymarket":
        try:
            fresh_payload = await MarketSourceRefreshService().fetch_price_payload(
                source=market.source,
                source_market_id=market.source_market_id,
                condition_id=market.condition_id,
            )
        except httpx.HTTPError as exc:
            market.source_diagnostics = _source_refresh_error_diagnostics(market, str(exc))
            db.commit()
            raise HTTPException(status_code=502, detail=f"Market data source request failed: {exc}") from exc
        except ValueError as exc:
            market.source_diagnostics = _source_refresh_error_diagnostics(market, str(exc))
            db.commit()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raw_payload = _merge_price_payload_with_market_context(_source_price_payload(market), fresh_payload)
        refresh_source = "public_source_refresh"
    else:
        raw_payload = _source_price_payload(market)
        if raw_payload is None:
            raise HTTPException(status_code=409, detail="Market has no stored source payload to refresh prices from")

    snapshot = _persist_price_snapshot_from_payload(db, market, raw_payload, refresh_source=refresh_source)
    if snapshot is None:
        db.commit()
        raise HTTPException(status_code=409, detail="Source payload does not include supported price fields")

    db.commit()
    db.refresh(snapshot)
    return snapshot


@router.post("/{market_id}/parse", response_model=ParsedMarketRead)
async def parse_market(market_id: int, db: Session = Depends(get_db)) -> ParsedMarket:
    market = get_market(db, market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")

    result = parse_precipitation_market(market.question)
    if not result.success:
        raise HTTPException(status_code=422, detail=result.error)
    if result.threshold_value is None or result.threshold_value <= 0:
        raise HTTPException(status_code=422, detail="Parsed threshold must be positive")

    try:
        geocoded_location = await resolve_location_for_market(result.location_name or "")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Geocoding provider request failed: {exc}") from exc
    location_name = geocoded_location.name if geocoded_location else result.location_name or ""
    parsed_market = ParsedMarket(
        market_id=market.id,
        location_name=location_name,
        latitude=geocoded_location.latitude if geocoded_location else None,
        longitude=geocoded_location.longitude if geocoded_location else None,
        metric=result.metric or "precipitation",
        operator=result.operator or ">",
        threshold_value=result.threshold_value,
        threshold_unit=result.threshold_unit or "inch",
        target_start=result.target_start,
        target_end=result.target_end,
        parse_confidence=result.parse_confidence,
        parser_version=result.parser_version,
        raw_parse_json={
            **result.model_dump(mode="json"),
            "geocoding": geocoded_location.__dict__ if geocoded_location else None,
        },
    )
    db.add(parsed_market)

    if latest_price_snapshot(db, market.id) is None:
        db.add(
            MarketPriceSnapshot(
                market_id=market.id,
                yes_price=0.44,
                no_price=0.56,
                spread=0.02,
                liquidity=1000.0,
                volume=2500.0,
                timestamp=utc_now(),
                raw_json={"mock": True, "source": "parse_route_demo_fallback"},
            )
        )

    db.commit()
    db.refresh(parsed_market)
    return parsed_market
