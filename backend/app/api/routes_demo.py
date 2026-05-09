"""Paper-only demo workflow routes.

These endpoints exist to make the portfolio dashboard usable in one browser
session. They only use mock market data, fixture forecasts, stored model logic,
and simulated paper trades; they do not call external providers or live
execution adapters.
"""

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EVRecommendation, Market, MarketPriceSnapshot, ParsedMarket, PaperTrade, Prediction, WeatherForecastSnapshot, utc_now
from app.db.repositories import latest_forecast_snapshot, latest_paper_trade, latest_parsed_market, latest_prediction, latest_price_snapshot, latest_recommendation
from app.db.session import get_db
from app.markets.market_discovery import DiscoveredMarket, mock_weather_markets
from app.markets.market_parser import parse_precipitation_market
from app.modeling.baseline import run_baseline_prediction
from app.strategy.ev import evaluate_market_edge
from app.strategy.paper_trader import create_paper_trade_from_recommendation
from app.weather.geocoding import FixtureGeocoder


router = APIRouter(prefix="/demo", tags=["demo"])


class PaperWorkflowRequest(BaseModel):
    quantity: float = Field(default=10.0, gt=0)


class PaperWorkflowResponse(BaseModel):
    market_id: int
    parsed_market_id: int
    forecast_snapshot_id: int
    prediction_id: int
    recommendation_id: int
    paper_trade_id: int | None = None
    recommendation: str
    steps_completed: list[str]
    message: str


def _upsert_mock_market(db: Session, discovered: DiscoveredMarket) -> Market:
    market = db.scalars(
        select(Market)
        .where(Market.source == discovered.source)
        .where(Market.source_market_id == discovered.source_market_id)
        .limit(1)
    ).first()
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
    if market is None:
        market = Market(**item)
        db.add(market)
        db.flush()
    else:
        for key, value in item.items():
            setattr(market, key, value)

    if latest_price_snapshot(db, market.id) is None and discovered.price_snapshot is not None:
        db.add(
            MarketPriceSnapshot(
                market_id=market.id,
                yes_price=discovered.price_snapshot.yes_price,
                no_price=discovered.price_snapshot.no_price,
                best_bid_yes=discovered.price_snapshot.best_bid_yes,
                best_ask_yes=discovered.price_snapshot.best_ask_yes,
                best_bid_no=discovered.price_snapshot.best_bid_no,
                best_ask_no=discovered.price_snapshot.best_ask_no,
                spread=discovered.price_snapshot.spread,
                liquidity=discovered.price_snapshot.liquidity,
                volume=discovered.price_snapshot.volume,
                timestamp=discovered.price_snapshot.timestamp or utc_now(),
                raw_json=discovered.price_snapshot.raw_json,
            )
        )
    return market


def _select_demo_market(db: Session) -> Market:
    discovered_markets = mock_weather_markets(limit=2, source="mock")
    selected_market: Market | None = None
    for discovered in discovered_markets:
        market = _upsert_mock_market(db, discovered)
        if discovered.source_market_id == "mock-nyc-rain-tomorrow":
            selected_market = market
    return selected_market or _upsert_mock_market(db, discovered_markets[0])


def _ensure_parsed_market(db: Session, market: Market, steps: list[str]) -> ParsedMarket:
    parsed_market = latest_parsed_market(db, market.id)
    if parsed_market is not None:
        return parsed_market

    result = parse_precipitation_market(market.question)
    if not result.success or result.threshold_value is None:
        raise HTTPException(status_code=422, detail=result.error or "Demo market could not be parsed")
    geocoded_location = FixtureGeocoder().geocode(result.location_name or "")
    parsed_market = ParsedMarket(
        market_id=market.id,
        location_name=geocoded_location.name if geocoded_location else result.location_name or "",
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
            "demo_fixture": True,
        },
    )
    db.add(parsed_market)
    db.flush()
    steps.append("parsed_market")
    return parsed_market


def _ensure_fixture_forecast(db: Session, parsed_market: ParsedMarket, steps: list[str]) -> WeatherForecastSnapshot:
    forecast = latest_forecast_snapshot(db, parsed_market.id)
    if forecast is not None:
        return forecast

    forecast = WeatherForecastSnapshot(
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
        raw_json={"demo_fixture": True, "note": "Fixture forecast created by POST /demo/paper-workflow."},
    )
    db.add(forecast)
    db.flush()
    steps.append("fixture_forecast")
    return forecast


def _ensure_prediction(db: Session, market: Market, parsed_market: ParsedMarket, forecast: WeatherForecastSnapshot, steps: list[str]) -> Prediction:
    prediction = latest_prediction(db, market.id)
    if prediction is not None:
        return prediction

    result = run_baseline_prediction(parsed_market, forecast)
    prediction = Prediction(
        market_id=market.id,
        parsed_market_id=parsed_market.id,
        forecast_snapshot_id=forecast.id,
        model_version=result.model_version,
        p_yes=result.p_yes,
        p_no=result.p_no,
        confidence=result.confidence,
        features_json=result.features_json,
    )
    db.add(prediction)
    db.flush()
    steps.append("prediction")
    return prediction


def _ensure_recommendation(db: Session, market: Market, prediction: Prediction, steps: list[str]) -> EVRecommendation:
    recommendation = latest_recommendation(db, prediction.id)
    if recommendation is not None:
        return recommendation

    price_snapshot = latest_price_snapshot(db, market.id)
    if price_snapshot is None:
        raise HTTPException(status_code=409, detail="Demo market is missing a price snapshot")
    result = evaluate_market_edge(prediction, price_snapshot)
    recommendation = EVRecommendation(
        prediction_id=prediction.id,
        price_snapshot_id=price_snapshot.id,
        market_price_yes=result.market_price_yes,
        market_price_no=result.market_price_no,
        edge_yes=result.edge_yes,
        edge_no=result.edge_no,
        ev_yes=result.ev_yes,
        ev_no=result.ev_no,
        recommendation=result.recommendation,
        paper_position_size=result.paper_position_size,
        reason=result.reason,
    )
    db.add(recommendation)
    db.flush()
    steps.append("ev_recommendation")
    return recommendation


def _ensure_paper_trade(db: Session, market: Market, recommendation: EVRecommendation, quantity: float, steps: list[str]) -> PaperTrade | None:
    paper_trade = latest_paper_trade(db, market.id)
    if paper_trade is not None:
        return paper_trade
    if recommendation.recommendation not in {"PAPER_BUY_YES", "PAPER_BUY_NO"}:
        return None

    paper_trade = create_paper_trade_from_recommendation(recommendation, quantity)
    db.add(paper_trade)
    db.flush()
    steps.append("paper_trade")
    return paper_trade


@router.post("/paper-workflow", response_model=PaperWorkflowResponse)
def run_paper_demo_workflow(payload: PaperWorkflowRequest, db: Session = Depends(get_db)) -> PaperWorkflowResponse:
    steps = ["mock_discovery"]
    market = _select_demo_market(db)
    parsed_market = _ensure_parsed_market(db, market, steps)
    forecast = _ensure_fixture_forecast(db, parsed_market, steps)
    prediction = _ensure_prediction(db, market, parsed_market, forecast, steps)
    recommendation = _ensure_recommendation(db, market, prediction, steps)
    paper_trade = _ensure_paper_trade(db, market, recommendation, payload.quantity, steps)
    db.commit()

    return PaperWorkflowResponse(
        market_id=market.id,
        parsed_market_id=parsed_market.id,
        forecast_snapshot_id=forecast.id,
        prediction_id=prediction.id,
        recommendation_id=recommendation.id,
        paper_trade_id=paper_trade.id if paper_trade else None,
        recommendation=recommendation.recommendation,
        steps_completed=steps,
        message="Paper demo workflow complete.",
    )
