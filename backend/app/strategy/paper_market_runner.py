"""One-shot real-market paper trading runner.

The runner orchestrates the existing research workflow against public market
data with conservative paper-only guardrails. It never calls authenticated
trading APIs, signs orders, or creates live execution records.
"""

from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
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
from app.markets.market_discovery import (
    WEATHER_KEYWORDS,
    DiscoveredMarket,
    DiscoveredPriceSnapshot,
    MarketDiscoveryService,
    MarketSourceRefreshService,
    build_source_diagnostics,
    normalize_price_snapshot,
)
from app.markets.market_parser import parse_precipitation_market
from app.markets.polymarket_client import PublicMarketDataError
from app.modeling.model_registry import DEFAULT_MODEL_VERSION, run_prediction_model
from app.strategy.ev import evaluate_market_edge
from app.strategy.paper_trader import create_paper_trade_from_recommendation
from app.weather.forecast_service import fetch_forecast_for_parsed_market
from app.weather.geocoding import resolve_location_for_market


ForecastProvider = Callable[[ParsedMarket], Awaitable[WeatherForecastSnapshot]]


@dataclass(frozen=True)
class PaperMarketRunnerConfig:
    source: str = "polymarket"
    keywords: list[str] = field(default_factory=lambda: list(WEATHER_KEYWORDS))
    discovery_limit: int = 50
    process_limit: int = 25
    max_trades: int = 3
    quantity: float = 1.0
    min_liquidity: float = 0.0
    max_spread: float = 0.15
    refresh_prices: bool = True
    create_trades: bool = True
    allow_interval_contracts: bool = settings.PAPER_RUNNER_ALLOW_INTERVAL_CONTRACTS
    allow_partial_started_windows: bool = settings.PAPER_RUNNER_ALLOW_PARTIAL_STARTED_WINDOWS
    max_price_age_minutes: float | None = settings.PAPER_RUNNER_MAX_PRICE_AGE_MINUTES
    max_forecast_age_hours: float | None = settings.PAPER_RUNNER_MAX_FORECAST_AGE_HOURS
    max_open_trades: int | None = settings.PAPER_RUNNER_MAX_OPEN_TRADES
    max_total_exposure: float | None = settings.PAPER_RUNNER_MAX_TOTAL_EXPOSURE
    max_market_exposure: float | None = settings.PAPER_RUNNER_MAX_MARKET_EXPOSURE
    max_location_exposure: float | None = settings.PAPER_RUNNER_MAX_LOCATION_EXPOSURE
    entry_slippage_rate: float = settings.PAPER_RUNNER_ENTRY_SLIPPAGE_RATE
    allow_stale_price_fallback: bool = settings.PAPER_RUNNER_ALLOW_STALE_PRICE_FALLBACK
    model_version: str = DEFAULT_MODEL_VERSION


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
    actionable_recommendations: int = 0
    expected_paper_trades: int = 0
    paper_trades_created: int = 0
    stale_price_fallbacks_used: int = 0
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
        self._planned_trade_exposures: list[dict[str, Any]] = []
        self._current_report: PaperMarketRunnerReport | None = None

    async def run_once(self) -> PaperMarketRunnerReport:
        report = PaperMarketRunnerReport()
        self._current_report = report
        self._planned_trade_exposures = []
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
            if max(report.paper_trades_created, report.expected_paper_trades) >= self.config.max_trades:
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
        self._current_report = None
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
        raw_markets = list(
            self.db.scalars(
                select(Market)
                .where(Market.source == self.config.source)
                .where(Market.active.is_(True))
                .where(Market.closed.is_(False))
                .order_by(Market.updated_at.desc())
                .limit(max(self.config.process_limit * 5, self.config.process_limit))
            )
        )
        return sorted(raw_markets, key=self._candidate_sort_key)[: self.config.process_limit]

    def _candidate_sort_key(self, market: Market) -> tuple[int, float]:
        result = parse_precipitation_market(
            market.question,
            allow_interval_contracts=self.config.allow_interval_contracts,
        )
        if result.success:
            priority = 0
        elif self._parse_failure_skip_reason(result.error) == "parse_failed_interval_contract":
            priority = 1
        elif _looks_like_weather_market(market.question):
            priority = 2
        else:
            priority = 3
        return (priority, -market.updated_at.timestamp())

    async def _process_market(self, market: Market, report: PaperMarketRunnerReport) -> bool:
        if self.config.refresh_prices:
            if not await self._refresh_price_snapshot(market, report):
                return False
        price_snapshot = latest_price_snapshot(self.db, market.id)
        if not self._is_price_eligible(price_snapshot):
            return False

        parsed_market = await self._ensure_parsed_market(market, report)
        if parsed_market is None:
            return False
        if self._target_window_elapsed(parsed_market):
            self._skip("target_window_elapsed")
            return False
        if self._target_window_started(parsed_market) and not self.config.allow_partial_started_windows:
            self._skip("target_window_started")
            return False

        forecast = await self._create_forecast(parsed_market, report)
        if not self._is_forecast_eligible(forecast):
            return False
        prediction = self._create_prediction(market, parsed_market, forecast, report)
        recommendation = self._create_recommendation(market, prediction, report)
        return self._maybe_create_trade(market, recommendation)

    async def _refresh_price_snapshot(self, market: Market, report: PaperMarketRunnerReport) -> bool:
        if market.source != "polymarket":
            return True
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
                market.source_diagnostics["price_status"] = (
                    "stale_supported" if self.config.allow_stale_price_fallback else "fresh_price_required"
                )
                market.source_diagnostics["fallback_price_snapshot_id"] = fallback_snapshot.id
                market.source_diagnostics["fallback_price_snapshot_used"] = self.config.allow_stale_price_fallback
                market.source_diagnostics["stale_price_fallback_allowed"] = self.config.allow_stale_price_fallback
                if self.config.allow_stale_price_fallback:
                    report.stale_price_fallbacks_used += 1
                    self._skip("price_refresh_failed_used_stored_snapshot")
                else:
                    market.source_diagnostics["unsupported_reasons"].append("stale_price_fallback_requires_opt_in")
                    self._skip("price_refresh_failed_fresh_price_required")
                return self.config.allow_stale_price_fallback
            self._skip("price_refresh_failed")
            return False

        raw_payload = self._merge_price_payload_with_context(self._source_price_payload(market), fresh_payload)
        normalized = normalize_price_snapshot(raw_payload)
        market.source_diagnostics = build_source_diagnostics(raw_payload, price_snapshot=normalized, source=market.source)
        if normalized is None:
            self._skip("price_refresh_unsupported")
            return False
        self._add_price_snapshot(market, normalized)
        report.price_snapshots_created += 1
        self.db.flush()
        return True

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
        if self._is_older_than(price_snapshot.timestamp, self.config.max_price_age_minutes, unit_seconds=60):
            self._skip("price_snapshot_stale")
            return False
        if price_snapshot.liquidity is not None and price_snapshot.liquidity < self.config.min_liquidity:
            self._skip("liquidity_below_min")
            return False
        if price_snapshot.spread is not None and price_snapshot.spread > self.config.max_spread:
            self._skip("spread_above_max")
            return False
        return True

    def _is_forecast_eligible(self, forecast: WeatherForecastSnapshot) -> bool:
        if self._is_older_than(forecast.forecast_timestamp, self.config.max_forecast_age_hours, unit_seconds=3600):
            self._skip("forecast_snapshot_stale")
            return False
        return True

    @staticmethod
    def _target_window_elapsed(parsed_market: ParsedMarket) -> bool:
        target_end = parsed_market.target_end or parsed_market.target_start
        if target_end is None:
            return False
        return _aware_datetime(target_end) < utc_now()

    @staticmethod
    def _target_window_started(parsed_market: ParsedMarket) -> bool:
        target_start = parsed_market.target_start
        if target_start is None:
            return False
        return _aware_datetime(target_start) < utc_now()

    @staticmethod
    def _is_older_than(value: datetime | None, max_age: float | None, *, unit_seconds: int) -> bool:
        if value is None or max_age is None:
            return False
        if max_age <= 0:
            return False
        age_seconds = (utc_now() - _aware_datetime(value)).total_seconds()
        return age_seconds > max_age * unit_seconds

    async def _ensure_parsed_market(self, market: Market, report: PaperMarketRunnerReport) -> ParsedMarket | None:
        parsed_market = latest_parsed_market(self.db, market.id)
        if parsed_market is not None:
            if parsed_market.operator == "between" and not self.config.allow_interval_contracts:
                self._skip_parse_failure(
                    "Unsupported precipitation interval contract: interval thresholds require interval probability modeling."
                )
                return None
            if (
                parsed_market.target_start is not None
                and parsed_market.latitude is not None
                and parsed_market.longitude is not None
            ):
                return parsed_market

        result = parse_precipitation_market(
            market.question,
            allow_interval_contracts=self.config.allow_interval_contracts,
        )
        if not result.success or result.threshold_value is None:
            self._skip_parse_failure(result.error)
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
            raw_parse_json={**result.model_dump(mode="json"), **(result.raw_parse_json or {}), "geocoding": geocoded_location.__dict__},
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
        result = run_prediction_model(parsed_market, forecast, model_version=self.config.model_version)
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
        if recommendation.recommendation not in {"PAPER_BUY_YES", "PAPER_BUY_NO"}:
            self._skip("not_actionable")
            return False
        if self._current_report is not None:
            self._current_report.actionable_recommendations += 1

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
        entry_price = recommendation.market_price_yes if side == "YES" else recommendation.market_price_no
        if entry_price is None:
            self._skip("missing_binary_prices")
            return False
        fill_entry_price = min(entry_price + self.config.entry_slippage_rate, 1.0)
        proposed_exposure = fill_entry_price * quantity
        if not self._portfolio_limits_allow_trade(market, proposed_exposure):
            return False

        if not self.config.create_trades:
            self._planned_trade_exposures.append(
                {
                    "market_id": market.id,
                    "location_name": self._latest_location_name(market.id),
                    "exposure": proposed_exposure,
                }
            )
            if self._current_report is not None:
                self._current_report.expected_paper_trades += 1
            self._skip("trade_creation_disabled")
            return False

        trade = create_paper_trade_from_recommendation(
            recommendation,
            quantity,
            runner_config=paper_runner_config_to_json(self.config),
            entry_slippage_rate=self.config.entry_slippage_rate,
        )
        self.db.add(trade)
        self.db.flush()
        return True

    def _portfolio_limits_allow_trade(self, market: Market, proposed_exposure: float) -> bool:
        open_trades = self._open_paper_trades()
        if (
            self.config.max_open_trades is not None
            and len(open_trades) + len(self._planned_trade_exposures) >= self.config.max_open_trades
        ):
            self._skip("portfolio_open_trade_limit")
            return False

        total_exposure = sum(_trade_exposure(trade) for trade in open_trades) + sum(
            float(item["exposure"]) for item in self._planned_trade_exposures
        )
        if _limit_exceeded(total_exposure + proposed_exposure, self.config.max_total_exposure):
            self._skip("portfolio_total_exposure_limit")
            return False

        market_exposure = sum(_trade_exposure(trade) for trade in open_trades if trade.market_id == market.id) + sum(
            float(item["exposure"]) for item in self._planned_trade_exposures if item["market_id"] == market.id
        )
        if _limit_exceeded(market_exposure + proposed_exposure, self.config.max_market_exposure):
            self._skip("portfolio_market_exposure_limit")
            return False

        location_name = self._latest_location_name(market.id)
        if location_name is not None:
            location_exposure = 0.0
            for trade in open_trades:
                if self._latest_location_name(trade.market_id) == location_name:
                    location_exposure += _trade_exposure(trade)
            location_exposure += sum(
                float(item["exposure"])
                for item in self._planned_trade_exposures
                if item.get("location_name") == location_name
            )
            if _limit_exceeded(location_exposure + proposed_exposure, self.config.max_location_exposure):
                self._skip("portfolio_location_exposure_limit")
                return False

        return True

    def _open_paper_trades(self) -> list[PaperTrade]:
        return list(
            self.db.scalars(
                select(PaperTrade)
                .where(PaperTrade.status == "OPEN")
                .order_by(PaperTrade.entry_time.asc(), PaperTrade.id.asc())
            )
        )

    def _latest_location_name(self, market_id: int) -> str | None:
        parsed_market = latest_parsed_market(self.db, market_id)
        if parsed_market is None:
            return None
        return parsed_market.location_name.strip().lower()

    def _skip(self, reason: str) -> None:
        self._skipped[reason] += 1

    def _skip_parse_failure(self, error: str | None) -> None:
        reason = self._parse_failure_skip_reason(error)
        if reason != "parse_failed_interval_contract":
            self._skip("parse_failed")
        self._skip(reason)

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
        if "interval thresholds require interval probability modeling" in lowered:
            return "parse_failed_interval_contract"
        if "unsupported precipitation question wording" in lowered:
            return "parse_failed_unsupported_wording"
        if "unsupported temperature question wording" in lowered:
            return "parse_failed_unsupported_temperature_wording"
        return "parse_failed_unknown"


def _looks_like_weather_market(question: str) -> bool:
    lowered = question.lower()
    return any(term in lowered for term in ("rain", "precipitation", "precip", "temperature", "temp"))


def _aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _trade_exposure(trade: PaperTrade) -> float:
    return trade.entry_price * trade.quantity


def _limit_exceeded(value: float, limit: float | None) -> bool:
    if limit is None or limit <= 0:
        return False
    return value > limit
