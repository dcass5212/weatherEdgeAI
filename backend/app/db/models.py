from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class Market(TimestampMixin, Base):
    __tablename__ = "markets"
    __table_args__ = (UniqueConstraint("source", "source_market_id", name="uq_market_source_source_market_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_market_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    condition_id: Mapped[str | None] = mapped_column(String(255), index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(100), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_source: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[dict | None] = mapped_column(JSON)
    source_diagnostics: Mapped[dict | None] = mapped_column(JSON)

    parsed_markets: Mapped[list["ParsedMarket"]] = relationship(back_populates="market", cascade="all, delete-orphan")
    price_snapshots: Mapped[list["MarketPriceSnapshot"]] = relationship(back_populates="market", cascade="all, delete-orphan")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="market", cascade="all, delete-orphan")
    resolved_outcomes: Mapped[list["ResolvedOutcome"]] = relationship(back_populates="market", cascade="all, delete-orphan")
    paper_trades: Mapped[list["PaperTrade"]] = relationship(back_populates="market", cascade="all, delete-orphan")


class ParsedMarket(TimestampMixin, Base):
    __tablename__ = "parsed_markets"
    __table_args__ = (CheckConstraint("threshold_value > 0", name="ck_parsed_market_threshold_positive"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    location_name: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    metric: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str] = mapped_column(String(10), nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_unit: Mapped[str] = mapped_column(String(50), nullable=False)
    target_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    target_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parse_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    parser_version: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_parse_json: Mapped[dict | None] = mapped_column(JSON)

    market: Mapped["Market"] = relationship(back_populates="parsed_markets")
    forecast_snapshots: Mapped[list["WeatherForecastSnapshot"]] = relationship(
        back_populates="parsed_market", cascade="all, delete-orphan"
    )
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="parsed_market")


class MarketPriceSnapshot(Base):
    __tablename__ = "market_price_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    yes_price: Mapped[float | None] = mapped_column(Float)
    no_price: Mapped[float | None] = mapped_column(Float)
    best_bid_yes: Mapped[float | None] = mapped_column(Float)
    best_ask_yes: Mapped[float | None] = mapped_column(Float)
    best_bid_no: Mapped[float | None] = mapped_column(Float)
    best_ask_no: Mapped[float | None] = mapped_column(Float)
    spread: Mapped[float | None] = mapped_column(Float)
    liquidity: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    raw_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    market: Mapped["Market"] = relationship(back_populates="price_snapshots")
    ev_recommendations: Mapped[list["EVRecommendation"]] = relationship(back_populates="price_snapshot")


class WeatherForecastSnapshot(Base):
    __tablename__ = "weather_forecast_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    parsed_market_id: Mapped[int] = mapped_column(ForeignKey("parsed_markets.id"), nullable=False, index=True)
    forecast_source: Mapped[str] = mapped_column(String(100), nullable=False)
    forecast_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    target_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    target_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    forecast_precip_total: Mapped[float | None] = mapped_column(Float)
    forecast_precip_unit: Mapped[str | None] = mapped_column(String(50))
    forecast_temp_max: Mapped[float | None] = mapped_column(Float)
    forecast_temp_min: Mapped[float | None] = mapped_column(Float)
    forecast_temp_unit: Mapped[str | None] = mapped_column(String(50))
    raw_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    parsed_market: Mapped["ParsedMarket"] = relationship(back_populates="forecast_snapshots")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="forecast_snapshot")


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint("p_yes >= 0 AND p_yes <= 1", name="ck_prediction_p_yes_probability"),
        CheckConstraint("p_no >= 0 AND p_no <= 1", name="ck_prediction_p_no_probability"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    parsed_market_id: Mapped[int | None] = mapped_column(ForeignKey("parsed_markets.id"), index=True)
    forecast_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("weather_forecast_snapshots.id"), index=True)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    p_yes: Mapped[float] = mapped_column(Float, nullable=False)
    p_no: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[str | None] = mapped_column(String(50))
    features_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    market: Mapped["Market"] = relationship(back_populates="predictions")
    parsed_market: Mapped["ParsedMarket | None"] = relationship(back_populates="predictions")
    forecast_snapshot: Mapped["WeatherForecastSnapshot | None"] = relationship(back_populates="predictions")
    ev_recommendations: Mapped[list["EVRecommendation"]] = relationship(
        back_populates="prediction", cascade="all, delete-orphan"
    )


class EVRecommendation(Base):
    __tablename__ = "ev_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id"), nullable=False, index=True)
    price_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("market_price_snapshots.id"), index=True)
    market_price_yes: Mapped[float | None] = mapped_column(Float)
    market_price_no: Mapped[float | None] = mapped_column(Float)
    edge_yes: Mapped[float | None] = mapped_column(Float)
    edge_no: Mapped[float | None] = mapped_column(Float)
    ev_yes: Mapped[float | None] = mapped_column(Float)
    ev_no: Mapped[float | None] = mapped_column(Float)
    recommendation: Mapped[str] = mapped_column(String(50), nullable=False)
    paper_position_size: Mapped[float | None] = mapped_column(Float)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    prediction: Mapped["Prediction"] = relationship(back_populates="ev_recommendations")
    price_snapshot: Mapped["MarketPriceSnapshot | None"] = relationship(back_populates="ev_recommendations")
    paper_trades: Mapped[list["PaperTrade"]] = relationship(back_populates="recommendation")


class ResolvedOutcome(Base):
    __tablename__ = "resolved_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    actual_outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    actual_value: Mapped[float | None] = mapped_column(Float)
    actual_unit: Mapped[str | None] = mapped_column(String(50))
    resolution_source: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    market: Mapped["Market"] = relationship(back_populates="resolved_outcomes")


class PaperTrade(TimestampMixin, Base):
    __tablename__ = "paper_trades"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_paper_trade_quantity_positive"),
        CheckConstraint("entry_price >= 0 AND entry_price <= 1", name="ck_paper_trade_entry_price_probability"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    recommendation_id: Mapped[int | None] = mapped_column(ForeignKey("ev_recommendations.id"), index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    exit_price: Mapped[float | None] = mapped_column(Float)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pnl: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50), default="OPEN", nullable=False, index=True)

    market: Mapped["Market"] = relationship(back_populates="paper_trades")
    recommendation: Mapped["EVRecommendation | None"] = relationship(back_populates="paper_trades")
