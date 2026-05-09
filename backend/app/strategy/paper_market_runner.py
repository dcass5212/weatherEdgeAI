"""One-shot real-market paper trading runner.

The runner orchestrates the existing research workflow against public market
data with conservative paper-only guardrails. It never calls authenticated
trading APIs, signs orders, or creates live execution records.
"""

from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    EVRecommendation,
    Market,
    MarketPriceSnapshot,
    PaperRunnerRun,
    ParsedMarket,
    PaperTrade,
    Prediction,
    WeatherForecastSnapshot,
    utc_now,
)
from app.db.repositories import latest_parsed_market, latest_price_snapshot
from app.markets.market_discovery import DiscoveredMarket, DiscoveredPriceSnapshot, MarketDiscoveryService, MarketSourceRefreshService, build_source_diagnostics, normalize_price_snapshot
from app.markets.market_parser import parse_precipitation_market
from app.markets.polymarket_client import PublicMarketDataError
from app.modeling.baseline import run_baseline_prediction
from app.strategy.ev import evaluate_market_edge
from app.strategy.paper_trader import create_paper_trade_from_recommendation
from app.weather.forecast_service import fetch_forecast_for_parsed_market
from app.weather.geocoding import resolve_location_for_market


ForecastProvider = Callable[[ParsedMarket], Awaitable[WeatherForecastSnapshot]]


@dataclass(frozen=True)
class PaperMarketRunnerConfig:
    source: str = "polymarket"
    keywords: list[str] = field(default_factory=lambda: ["rain", "weather", "precipitation"])
    discovery_limit: int = 25
    process_limit: int = 10
    max_trades: int = 3
    quantity: float = 1.0
    min_liquidity: float = 0.0
    max_spread: float = 0.15
    refresh_prices: bool = True
    create_trades: bool = True


@dataclass
class PaperMarketRunnerReport:
    discovered: int = 0
    created: int = 0
    updated: int = 0
    price_snapshots_created: int = 0
    processed: int = 0
    parsed: int = 0
    forecasts_created: int = 0
    predictions_created: int = 0
    recommendations_created: int = 0
    paper_trades_created: int = 0
    skipped: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def paper_runner_config_to_json(config: PaperMarketRunnerConfig) -> dict[str, Any]:
    return asdict(config)


def paper_runner_report_to_json(report: PaperMarketRunnerReport) -> dict[str, Any]:
    return asdict(report)


def create_paper_runner_run(db: Session, config: PaperMarketRunnerConfig) -> PaperRunnerRun:
    run = PaperRunnerRun(
        status="running",
        source=config.source,
        started_at=utc_now(),
        config_json=paper_runner_config_to_json(config),
        skipped_json={},
        errors_json=[],
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def complete_paper_runner_run(db: Session, run: PaperRunnerRun, report: PaperMarketRunnerReport) -> PaperRunnerRun:
    report_json = paper_runner_report_to_json(report)
    run.status = "completed"
    run.completed_at = utc_now()
    run.discovered = report.discovered
    run.created = report.created
    run.updated = report.updated
    run.price_snapshots_created = report.price_snapshots_created
    run.processed = report.processed
    run.parsed = report.parsed
    run.forecasts_created = report.forecasts_created
    run.predictions_created = report.predictions_created
    run.recommendations_created = report.recommendations_created
    run.paper_trades_created = report.paper_trades_created
    run.skipped_json = report.skipped
    run.errors_json = report.errors
    run.report_json = report_json
    db.commit()
    db.refresh(run)
    return run


def fail_paper_runner_run(db: Session, run: PaperRunnerRun, exc: Exception) -> PaperRunnerRun:
    message = str(exc) or exc.__class__.__name__
    run.status = "failed"
    run.completed_at = utc_now()
    run.errors_json = [message]
    run.report_json = {"errors": [message]}
    db.commit()
    db.refresh(run)
    return run


async def run_paper_market_once_recorded(
    db: Session,
    config: PaperMarketRunnerConfig | None = None,
    runner: "PaperMarketRunner | None" = None,
) -> PaperRunnerRun:
    effective_config = config or PaperMarketRunnerConfig()
    run = create_paper_runner_run(db, effective_config)
    try:
        report = await (runner or PaperMarketRunner(db=db, config=effective_config)).run_once()
    except Exception as exc:
        db.rollback()
        fail_paper_runner_run(db, run, exc)
        raise
    return complete_paper_runner_run(db, run, report)


class PaperMarketRunner:
    def __init__(
        self,
        db: Session,
        config: PaperMarketRunnerConfig | None = None,
        discovery_service: MarketDiscoveryService | None = None,
        refresh_service: MarketSourceRefreshService | None = None,
        forecast_provider: ForecastProvider | None = None,
    ) -> None:
        self.db = db
        self.config = config or PaperMarketRunnerConfig()
        self.discovery_service = discovery_service or MarketDiscoveryService()
        self.refresh_service = refresh_service or MarketSourceRefreshService()
        self.forecast_provider = forecast_provider or fetch_forecast_for_parsed_market
        self._skipped: Counter[str] = Counter()

    async def run_once(self) -> PaperMarketRunnerReport:
        report = PaperMarketRunnerReport()
        discovered = await self.discovery_service.discover_weather_markets(
            source=self.config.source,
            keywords=self.config.keywords,
            limit=self.config.discovery_limit,
        )
        report.discovered = len(discovered)
        for discovered_market in discovered:
            market, created = self._upsert_market(discovered_market)
            report.created += 1 if created else 0
            report.updated += 0 if created else 1
            if self._add_price_snapshot(market, discovered_market.price_snapshot):
                report.price_snapshots_created += 1
        self.db.commit()

        markets = self._candidate_markets()
        for market in markets:
            if report.paper_trades_created >= self.config.max_trades:
                self._skip("max_trades_reached")
                break
            report.processed += 1
            try:
                created_trade = await self._process_market(market, report)
                if created_trade:
                    report.paper_trades_created += 1
                self.db.commit()
            except (ValueError, httpx.HTTPError, PublicMarketDataError) as exc:
                self.db.rollback()
                self._skip("workflow_error")
                report.errors.append(f"market_id={market.id}: {exc}")

        report.skipped = dict(self._skipped)
        self.db.commit()
        return report

    def _upsert_market(self, discovered: DiscoveredMarket) -> tuple[Market, bool]:
        market = self.db.scalars(
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
            self.db.add(market)
            self.db.flush()
            return market, True

        for key, value in item.items():
            setattr(market, key, value)
        return market, False

    def _add_price_snapshot(self, market: Market, discovered_price: DiscoveredPriceSnapshot | None) -> bool:
        if discovered_price is None:
            return False
        self.db.add(
            MarketPriceSnapshot(
                market_id=market.id,
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
        )
        return True

    def _candidate_markets(self) -> list[Market]:
        return list(
            self.db.scalars(
                select(Market)
                .where(Market.source == self.config.source)
                .where(Market.active.is_(True))
                .where(Market.closed.is_(False))
                .order_by(Market.updated_at.desc())
                .limit(self.config.process_limit)
            )
        )

    async def _process_market(self, market: Market, report: PaperMarketRunnerReport) -> bool:
        if self.config.refresh_prices:
            await self._refresh_price_snapshot(market, report)
        price_snapshot = latest_price_snapshot(self.db, market.id)
        if not self._is_price_eligible(price_snapshot):
            return False

        parsed_market = await self._ensure_parsed_market(market, report)
        if parsed_market is None:
            return False

        forecast = await self._create_forecast(parsed_market, report)
        prediction = self._create_prediction(market, parsed_market, forecast, report)
        recommendation = self._create_recommendation(market, prediction, report)
        return self._maybe_create_trade(market, recommendation)

    async def _refresh_price_snapshot(self, market: Market, report: PaperMarketRunnerReport) -> None:
        if market.source != "polymarket":
            return
        try:
            fresh_payload = await self.refresh_service.fetch_price_payload(
                source=market.source,
                source_market_id=market.source_market_id,
                condition_id=market.condition_id,
            )
        except PublicMarketDataError as exc:
            fallback_snapshot = latest_price_snapshot(self.db, market.id)
            market.source_diagnostics = {
                "source": market.source,
                "price_status": "unsupported",
                "unsupported_reasons": ["source_refresh_failed"],
                "public_source_error": exc.to_diagnostics(),
            }
            if fallback_snapshot is not None and fallback_snapshot.yes_price is not None and fallback_snapshot.no_price is not None:
                market.source_diagnostics["price_status"] = "stale_supported"
                market.source_diagnostics["fallback_price_snapshot_id"] = fallback_snapshot.id
                market.source_diagnostics["fallback_price_snapshot_used"] = True
                self._skip("price_refresh_failed_used_stored_snapshot")
                return
            self._skip("price_refresh_failed")
            return

        raw_payload = self._merge_price_payload_with_context(self._source_price_payload(market), fresh_payload)
        normalized = normalize_price_snapshot(raw_payload)
        market.source_diagnostics = build_source_diagnostics(raw_payload, price_snapshot=normalized, source=market.source)
        if normalized is None:
            self._skip("price_refresh_unsupported")
            return
        self._add_price_snapshot(market, normalized)
        report.price_snapshots_created += 1
        self.db.flush()

    @staticmethod
    def _source_price_payload(market: Market) -> dict | None:
        if not isinstance(market.raw_json, dict):
            return None
        raw_market = market.raw_json.get("market")
        return raw_market if isinstance(raw_market, dict) else market.raw_json

    @staticmethod
    def _merge_price_payload_with_context(stored_payload: dict | None, fresh_payload: dict) -> dict:
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
        return {**context, **fresh_payload} if context else fresh_payload

    def _is_price_eligible(self, price_snapshot: MarketPriceSnapshot | None) -> bool:
        if price_snapshot is None:
            self._skip("missing_price_snapshot")
            return False
        if price_snapshot.yes_price is None or price_snapshot.no_price is None:
            self._skip("missing_binary_prices")
            return False
        if price_snapshot.liquidity is not None and price_snapshot.liquidity < self.config.min_liquidity:
            self._skip("liquidity_below_min")
            return False
        if price_snapshot.spread is not None and price_snapshot.spread > self.config.max_spread:
            self._skip("spread_above_max")
            return False
        return True

    async def _ensure_parsed_market(self, market: Market, report: PaperMarketRunnerReport) -> ParsedMarket | None:
        parsed_market = latest_parsed_market(self.db, market.id)
        if parsed_market is not None:
            return parsed_market

        result = parse_precipitation_market(market.question)
        if not result.success or result.threshold_value is None:
            self._skip("parse_failed")
            self._skip(self._parse_failure_skip_reason(result.error))
            return None
        geocoded_location = await resolve_location_for_market(result.location_name or "")
        if geocoded_location is None:
            self._skip("missing_coordinates")
            return None

        parsed_market = ParsedMarket(
            market_id=market.id,
            location_name=geocoded_location.name,
            latitude=geocoded_location.latitude,
            longitude=geocoded_location.longitude,
            metric=result.metric or "precipitation",
            operator=result.operator or ">",
            threshold_value=result.threshold_value,
            threshold_unit=result.threshold_unit or "inch",
            target_start=result.target_start,
            target_end=result.target_end,
            parse_confidence=result.parse_confidence,
            parser_version=result.parser_version,
            raw_parse_json={**result.model_dump(mode="json"), "geocoding": geocoded_location.__dict__},
        )
        self.db.add(parsed_market)
        self.db.flush()
        report.parsed += 1
        return parsed_market

    async def _create_forecast(self, parsed_market: ParsedMarket, report: PaperMarketRunnerReport) -> WeatherForecastSnapshot:
        forecast = await self.forecast_provider(parsed_market)
        self.db.add(forecast)
        self.db.flush()
        report.forecasts_created += 1
        return forecast

    def _create_prediction(
        self,
        market: Market,
        parsed_market: ParsedMarket,
        forecast: WeatherForecastSnapshot,
        report: PaperMarketRunnerReport,
    ) -> Prediction:
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
        self.db.add(prediction)
        self.db.flush()
        report.predictions_created += 1
        return prediction

    def _create_recommendation(self, market: Market, prediction: Prediction, report: PaperMarketRunnerReport) -> EVRecommendation:
        price_snapshot = latest_price_snapshot(self.db, market.id)
        if price_snapshot is None:
            raise ValueError("price snapshot disappeared before strategy evaluation")
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
        self.db.add(recommendation)
        self.db.flush()
        report.recommendations_created += 1
        return recommendation

    def _maybe_create_trade(self, market: Market, recommendation: EVRecommendation) -> bool:
        if not self.config.create_trades:
            self._skip("trade_creation_disabled")
            return False
        if recommendation.recommendation not in {"PAPER_BUY_YES", "PAPER_BUY_NO"}:
            self._skip("not_actionable")
            return False

        side = "YES" if recommendation.recommendation == "PAPER_BUY_YES" else "NO"
        existing_open = self.db.scalars(
            select(PaperTrade)
            .where(PaperTrade.market_id == market.id)
            .where(PaperTrade.side == side)
            .where(PaperTrade.status == "OPEN")
            .limit(1)
        ).first()
        if existing_open is not None:
            self._skip("open_trade_exists")
            return False

        quantity = min(self.config.quantity, recommendation.paper_position_size or self.config.quantity)
        trade = create_paper_trade_from_recommendation(recommendation, quantity)
        self.db.add(trade)
        self.db.flush()
        return True

    def _skip(self, reason: str) -> None:
        self._skipped[reason] += 1

    @staticmethod
    def _parse_failure_skip_reason(error: str | None) -> str:
        if not error:
            return "parse_failed_unknown"
        lowered = error.lower()
        if "expected a precipitation threshold question" in lowered:
            return "parse_failed_not_precipitation"
        if "missing numeric threshold" in lowered:
            return "parse_failed_missing_threshold"
        if "threshold unit must be inches or millimeters" in lowered:
            return "parse_failed_unsupported_unit"
        if "unsupported precipitation question wording" in lowered:
            return "parse_failed_unsupported_wording"
        return "parse_failed_unknown"
