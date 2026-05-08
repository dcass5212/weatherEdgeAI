from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.models import (
    EVRecommendation,
    Market,
    MarketPriceSnapshot,
    ParsedMarket,
    PaperTrade,
    Prediction,
    WeatherForecastSnapshot,
)


def get_market(db: Session, market_id: int) -> Market | None:
    return db.get(Market, market_id)


def list_markets(
    db: Session,
    active: bool | None = None,
    closed: bool | None = None,
    category: str | None = None,
    limit: int = 50,
) -> list[Market]:
    statement: Select[tuple[Market]] = select(Market).order_by(Market.created_at.desc()).limit(limit)
    if active is not None:
        statement = statement.where(Market.active.is_(active))
    if closed is not None:
        statement = statement.where(Market.closed.is_(closed))
    if category is not None:
        statement = statement.where(Market.category == category)
    return list(db.scalars(statement))


def latest_parsed_market(db: Session, market_id: int) -> ParsedMarket | None:
    return db.scalars(
        select(ParsedMarket).where(ParsedMarket.market_id == market_id).order_by(ParsedMarket.created_at.desc()).limit(1)
    ).first()


def latest_price_snapshot(db: Session, market_id: int) -> MarketPriceSnapshot | None:
    return db.scalars(
        select(MarketPriceSnapshot)
        .where(MarketPriceSnapshot.market_id == market_id)
        .order_by(MarketPriceSnapshot.timestamp.desc())
        .limit(1)
    ).first()


def latest_forecast_snapshot(db: Session, parsed_market_id: int) -> WeatherForecastSnapshot | None:
    return db.scalars(
        select(WeatherForecastSnapshot)
        .where(WeatherForecastSnapshot.parsed_market_id == parsed_market_id)
        .order_by(WeatherForecastSnapshot.forecast_timestamp.desc())
        .limit(1)
    ).first()


def latest_prediction(db: Session, market_id: int) -> Prediction | None:
    return db.scalars(
        select(Prediction).where(Prediction.market_id == market_id).order_by(Prediction.created_at.desc()).limit(1)
    ).first()


def latest_recommendation(db: Session, prediction_id: int) -> EVRecommendation | None:
    return db.scalars(
        select(EVRecommendation)
        .where(EVRecommendation.prediction_id == prediction_id)
        .order_by(EVRecommendation.created_at.desc())
        .limit(1)
    ).first()


def list_paper_trades(db: Session, status: str | None = None, limit: int = 50) -> list[PaperTrade]:
    statement = select(PaperTrade).order_by(PaperTrade.created_at.desc()).limit(limit)
    if status is not None:
        statement = statement.where(PaperTrade.status == status)
    return list(db.scalars(statement))
