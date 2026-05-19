from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Market, PaperRunnerRun, PaperTrade, ParsedMarket, WeatherForecastSnapshot
from app.markets.market_discovery import DiscoveredMarket, DiscoveredPriceSnapshot
from app.markets.polymarket_client import PublicMarketDataError
from app.strategy.paper_market_runner import PaperMarketRunner, PaperMarketRunnerConfig, run_paper_market_once_recorded


def _discovered_market(
    source_market_id: str = "public-nyc-rain",
    question: str = "Will New York City get more than 1 inch of rain tomorrow?",
    yes_price: float | None = 0.44,
    no_price: float | None = 0.56,
    liquidity: float | None = 1000.0,
    spread: float | None = 0.02,
    timestamp: datetime | None = None,
) -> DiscoveredMarket:
    return DiscoveredMarket(
        source="polymarket",
        source_market_id=source_market_id,
        condition_id=f"condition-{source_market_id}",
        question=question,
        slug=source_market_id,
        category="weather",
        active=True,
        closed=False,
        end_time=None,
        resolution_source=None,
        raw_json={
            "id": source_market_id,
            "question": question,
            "outcomes": '["Yes", "No"]',
            "outcomePrices": f"[\"{yes_price}\", \"{no_price}\"]",
        },
        source_diagnostics={
            "source": "polymarket",
            "price_status": "supported" if yes_price is not None and no_price is not None else "partial",
            "unsupported_reasons": [],
        },
        price_snapshot=DiscoveredPriceSnapshot(
            yes_price=yes_price,
            no_price=no_price,
            spread=spread,
            liquidity=liquidity,
            timestamp=timestamp,
            raw_json={"source": "test_fixture"},
        ),
    )


def _discovered_chicago_market(
    source_market_id: str = "public-chicago-rain",
    yes_price: float | None = 0.44,
    no_price: float | None = 0.56,
) -> DiscoveredMarket:
    return _discovered_market(
        source_market_id=source_market_id,
        question="Will Chicago get more than 1 inch of rain tomorrow?",
        yes_price=yes_price,
        no_price=no_price,
    )


class FakeDiscoveryService:
    def __init__(self, markets: list[DiscoveredMarket]) -> None:
        self.markets = markets

    async def discover_weather_markets(self, source: str, keywords: list[str] | None = None, limit: int = 50) -> list[DiscoveredMarket]:
        assert source == "polymarket"
        return self.markets[:limit]


class FailingRefreshService:
    async def fetch_price_payload(self, source: str, source_market_id: str, condition_id: str | None) -> dict:
        raise PublicMarketDataError(
            endpoint=f"/prices/{condition_id}",
            reason="http_status_error",
            attempts=1,
            status_code=404,
            retryable=False,
        )


async def fixture_forecast(parsed_market: ParsedMarket) -> WeatherForecastSnapshot:
    precip_total = 195.0 if parsed_market.threshold_unit == "mm" else 1.6
    return WeatherForecastSnapshot(
        parsed_market_id=parsed_market.id,
        forecast_source="test_fixture",
        forecast_timestamp=datetime.now(timezone.utc),
        target_start=parsed_market.target_start,
        target_end=parsed_market.target_end,
        forecast_precip_total=precip_total,
        forecast_precip_unit=parsed_market.threshold_unit,
        raw_json={"test_fixture": True},
    )


async def stale_fixture_forecast(parsed_market: ParsedMarket) -> WeatherForecastSnapshot:
    return WeatherForecastSnapshot(
        parsed_market_id=parsed_market.id,
        forecast_source="test_fixture",
        forecast_timestamp=datetime.now(timezone.utc) - timedelta(hours=24),
        target_start=parsed_market.target_start,
        target_end=parsed_market.target_end,
        forecast_precip_total=1.6,
        forecast_precip_unit=parsed_market.threshold_unit,
        raw_json={"test_fixture": True, "stale": True},
    )


async def fixture_temperature_forecast(parsed_market: ParsedMarket) -> WeatherForecastSnapshot:
    return WeatherForecastSnapshot(
        parsed_market_id=parsed_market.id,
        forecast_source="test_fixture",
        forecast_timestamp=datetime.now(timezone.utc),
        target_start=parsed_market.target_start,
        target_end=parsed_market.target_end,
        forecast_temp_max=80.5,
        forecast_temp_min=52.0,
        forecast_temp_unit="F",
        raw_json={"test_fixture": True},
    )


async def unexpected_forecast_provider(parsed_market: ParsedMarket) -> WeatherForecastSnapshot:
    raise AssertionError("forecast provider should not be called")


@pytest.mark.anyio
async def test_paper_market_runner_creates_guarded_paper_trade(db_session: Session) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(refresh_prices=False, max_trades=1, quantity=2.0),
        discovery_service=FakeDiscoveryService([_discovered_market()]),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.discovered == 1
    assert report.created == 1
    assert report.processed == 1
    assert report.parsed == 1
    assert report.forecasts_created == 1
    assert report.predictions_created == 1
    assert report.recommendations_created == 1
    assert report.paper_trades_created == 1
    assert report.skipped == {}
    assert report.stale_price_fallbacks_used == 0

    trade = db_session.scalars(select(PaperTrade)).one()
    assert trade.side == "YES"
    assert trade.entry_price == 0.44
    assert trade.quantity == 2.0
    assert trade.status == "OPEN"
    assert trade.signal_snapshot_json["runner_config"]["max_trades"] == 1
    assert trade.signal_snapshot_json["runner_config"]["quantity"] == 2.0
    assert trade.signal_snapshot_json["market_price"]["liquidity"] == 1000.0
    assert trade.signal_snapshot_json["market_price"]["spread"] == 0.02
    assert trade.signal_snapshot_json["recommendation"]["recommendation"] == "PAPER_BUY_YES"
    assert trade.signal_snapshot_json["paper_trade"]["quoted_entry_price"] == 0.44
    assert trade.signal_snapshot_json["paper_trade"]["fill_entry_price"] == 0.44
    assert trade.signal_snapshot_json["paper_trade"]["entry_slippage_rate"] == 0.0


@pytest.mark.anyio
async def test_paper_market_runner_applies_entry_slippage_to_fill_price(db_session: Session) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(
            refresh_prices=False,
            max_trades=1,
            quantity=2.0,
            entry_slippage_rate=0.02,
        ),
        discovery_service=FakeDiscoveryService([_discovered_market()]),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.paper_trades_created == 1
    trade = db_session.scalars(select(PaperTrade)).one()
    assert trade.entry_price == 0.46
    assert trade.signal_snapshot_json["paper_trade"]["quoted_entry_price"] == 0.44
    assert trade.signal_snapshot_json["paper_trade"]["fill_entry_price"] == 0.46
    assert trade.signal_snapshot_json["paper_trade"]["entry_slippage_rate"] == 0.02
    assert trade.signal_snapshot_json["paper_trade"]["entry_slippage_cost"] == 0.04


@pytest.mark.anyio
async def test_paper_market_runner_uses_slipped_fill_for_exposure_limits(db_session: Session) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(
            refresh_prices=False,
            max_trades=1,
            quantity=10.0,
            entry_slippage_rate=0.02,
            max_total_exposure=4.5,
            max_market_exposure=25.0,
            max_location_exposure=25.0,
        ),
        discovery_service=FakeDiscoveryService([_discovered_market()]),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.paper_trades_created == 0
    assert report.skipped["portfolio_total_exposure_limit"] == 1


@pytest.mark.anyio
async def test_paper_market_runner_does_not_duplicate_open_side_trade(db_session: Session) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(refresh_prices=False, max_trades=1, quantity=2.0),
        discovery_service=FakeDiscoveryService([_discovered_market()]),
        forecast_provider=fixture_forecast,
    )

    first_report = await runner.run_once()
    second_report = await runner.run_once()

    assert first_report.paper_trades_created == 1
    assert second_report.paper_trades_created == 0
    assert second_report.skipped["open_trade_exists"] == 1
    assert len(list(db_session.scalars(select(PaperTrade)))) == 1


@pytest.mark.anyio
async def test_paper_market_runner_enforces_open_trade_portfolio_limit(db_session: Session) -> None:
    first_runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(refresh_prices=False, max_trades=1, quantity=2.0, max_open_trades=1),
        discovery_service=FakeDiscoveryService([_discovered_market()]),
        forecast_provider=fixture_forecast,
    )
    second_runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(refresh_prices=False, max_trades=1, quantity=2.0, max_open_trades=1),
        discovery_service=FakeDiscoveryService([_discovered_chicago_market()]),
        forecast_provider=fixture_forecast,
    )

    assert (await first_runner.run_once()).paper_trades_created == 1
    second_report = await second_runner.run_once()

    assert second_report.paper_trades_created == 0
    assert second_report.skipped["portfolio_open_trade_limit"] == 1


@pytest.mark.anyio
async def test_paper_market_runner_enforces_total_exposure_limit(db_session: Session) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(
            refresh_prices=False,
            max_trades=2,
            quantity=10.0,
            max_total_exposure=5.0,
            max_market_exposure=25.0,
            max_location_exposure=25.0,
        ),
        discovery_service=FakeDiscoveryService([_discovered_market(), _discovered_chicago_market()]),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.paper_trades_created == 1
    assert report.skipped["portfolio_total_exposure_limit"] == 1


@pytest.mark.anyio
async def test_paper_market_runner_rehearsal_estimates_expected_trades_without_creating(
    db_session: Session,
) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(
            refresh_prices=False,
            create_trades=False,
            max_trades=2,
            quantity=2.0,
            max_total_exposure=25.0,
            max_market_exposure=25.0,
            max_location_exposure=25.0,
        ),
        discovery_service=FakeDiscoveryService([_discovered_market(), _discovered_chicago_market()]),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.actionable_recommendations == 2
    assert report.expected_paper_trades == 2
    assert report.paper_trades_created == 0
    assert report.skipped["trade_creation_disabled"] == 2
    assert list(db_session.scalars(select(PaperTrade))) == []


@pytest.mark.anyio
async def test_paper_market_runner_rehearsal_expected_trades_respect_portfolio_limits(
    db_session: Session,
) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(
            refresh_prices=False,
            create_trades=False,
            max_trades=3,
            quantity=10.0,
            max_total_exposure=5.0,
            max_market_exposure=25.0,
            max_location_exposure=25.0,
        ),
        discovery_service=FakeDiscoveryService([_discovered_market(), _discovered_chicago_market()]),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.actionable_recommendations == 2
    assert report.expected_paper_trades == 1
    assert report.paper_trades_created == 0
    assert report.skipped["portfolio_total_exposure_limit"] == 1


@pytest.mark.anyio
async def test_paper_market_runner_enforces_market_exposure_limit(db_session: Session) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(
            refresh_prices=False,
            max_trades=1,
            quantity=10.0,
            max_total_exposure=25.0,
            max_market_exposure=3.0,
            max_location_exposure=25.0,
        ),
        discovery_service=FakeDiscoveryService([_discovered_market()]),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.paper_trades_created == 0
    assert report.skipped["portfolio_market_exposure_limit"] == 1


@pytest.mark.anyio
async def test_paper_market_runner_enforces_location_exposure_limit(db_session: Session) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(
            refresh_prices=False,
            max_trades=2,
            quantity=10.0,
            max_total_exposure=25.0,
            max_market_exposure=25.0,
            max_location_exposure=6.0,
        ),
        discovery_service=FakeDiscoveryService([
            _discovered_market(source_market_id="nyc-rain-1"),
            _discovered_market(source_market_id="nyc-rain-2", question="Will NYC get more than 1 inch of rain tomorrow?"),
        ]),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.paper_trades_created == 1
    assert report.skipped["portfolio_location_exposure_limit"] == 1


@pytest.mark.anyio
async def test_paper_market_runner_skips_ineligible_prices(db_session: Session) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(refresh_prices=False, min_liquidity=100.0),
        discovery_service=FakeDiscoveryService([
            _discovered_market(source_market_id="missing-binary", yes_price=None, no_price=None, liquidity=1000.0),
            _discovered_market(source_market_id="thin-market", liquidity=10.0),
            _discovered_market(source_market_id="wide-market", spread=0.4),
        ]),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.discovered == 3
    assert report.processed == 3
    assert report.paper_trades_created == 0
    assert report.skipped["missing_binary_prices"] == 1
    assert report.skipped["liquidity_below_min"] == 1
    assert report.skipped["spread_above_max"] == 1


@pytest.mark.anyio
async def test_paper_market_runner_skips_stale_price_snapshot(db_session: Session) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(refresh_prices=False, max_price_age_minutes=30),
        discovery_service=FakeDiscoveryService([
            _discovered_market(timestamp=datetime.now(timezone.utc) - timedelta(hours=2))
        ]),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.processed == 1
    assert report.paper_trades_created == 0
    assert report.skipped["price_snapshot_stale"] == 1
    assert report.forecasts_created == 0


@pytest.mark.anyio
async def test_paper_market_runner_skips_stale_forecast_snapshot(db_session: Session) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(refresh_prices=False, max_forecast_age_hours=1),
        discovery_service=FakeDiscoveryService([_discovered_market()]),
        forecast_provider=stale_fixture_forecast,
    )

    report = await runner.run_once()

    assert report.processed == 1
    assert report.forecasts_created == 1
    assert report.predictions_created == 0
    assert report.paper_trades_created == 0
    assert report.skipped["forecast_snapshot_stale"] == 1


@pytest.mark.anyio
async def test_paper_market_runner_skips_started_target_window_before_forecast(db_session: Session) -> None:
    market = Market(
        source="polymarket",
        source_market_id="started-month-window",
        condition_id="condition-started-month-window",
        question="Will New York City get more than 1 inch of rain in May?",
        active=True,
        closed=False,
    )
    db_session.add(market)
    db_session.flush()
    db_session.add(
        ParsedMarket(
            market_id=market.id,
            location_name="New York City",
            latitude=40.7128,
            longitude=-74.006,
            metric="precipitation",
            operator=">",
            threshold_value=1.0,
            threshold_unit="inch",
            target_start=datetime.now(timezone.utc) - timedelta(days=10),
            target_end=datetime.now(timezone.utc) + timedelta(days=20),
            parser_version="regex_precip_v1",
            parse_confidence=0.85,
            raw_parse_json={"test_fixture": "started_month_window"},
        )
    )
    db_session.commit()

    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(refresh_prices=False, allow_partial_started_windows=False),
        discovery_service=FakeDiscoveryService([
            _discovered_market(
                source_market_id="started-month-window",
                question="Will New York City get more than 1 inch of rain in May?",
            )
        ]),
        forecast_provider=unexpected_forecast_provider,
    )

    report = await runner.run_once()

    assert report.processed == 1
    assert report.forecasts_created == 0
    assert report.predictions_created == 0
    assert report.paper_trades_created == 0
    assert report.skipped["target_window_started"] == 1


@pytest.mark.anyio
async def test_paper_market_runner_allows_started_target_window_with_partial_weather_input(db_session: Session) -> None:
    market = Market(
        source="polymarket",
        source_market_id="started-month-window",
        condition_id="condition-started-month-window",
        question="Will New York City get more than 1 inch of rain in May?",
        active=True,
        closed=False,
    )
    db_session.add(market)
    db_session.flush()
    db_session.add(
        ParsedMarket(
            market_id=market.id,
            location_name="New York City",
            latitude=40.7128,
            longitude=-74.006,
            metric="precipitation",
            operator=">",
            threshold_value=1.0,
            threshold_unit="inch",
            target_start=datetime.now(timezone.utc) - timedelta(days=10),
            target_end=datetime.now(timezone.utc) + timedelta(days=20),
            parser_version="regex_precip_v1",
            parse_confidence=0.85,
            raw_parse_json={"test_fixture": "started_month_window"},
        )
    )
    db_session.commit()

    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(refresh_prices=False, create_trades=False),
        discovery_service=FakeDiscoveryService([
            _discovered_market(
                source_market_id="started-month-window",
                question="Will New York City get more than 1 inch of rain in May?",
            )
        ]),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.processed == 1
    assert report.forecasts_created == 1
    assert report.predictions_created == 1
    assert report.recommendations_created == 1
    assert "target_window_started" not in report.skipped


@pytest.mark.anyio
async def test_paper_market_runner_records_detailed_parse_failure_skip(db_session: Session) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(refresh_prices=False),
        discovery_service=FakeDiscoveryService([
            _discovered_market(source_market_id="temperature-market", question="Will New York City be above 90 degrees tomorrow?")
        ]),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.processed == 1
    assert report.paper_trades_created == 0
    assert report.skipped["parse_failed"] == 1
    assert report.skipped["parse_failed_not_precipitation"] == 1


@pytest.mark.anyio
async def test_paper_market_runner_records_interval_contract_parse_skip(db_session: Session) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(refresh_prices=False),
        discovery_service=FakeDiscoveryService([
            _discovered_market(
                source_market_id="interval-market",
                question="Will Hong Kong have between 190-200mm of precipitation in June?",
            )
        ]),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.processed == 1
    assert report.paper_trades_created == 0
    assert report.skipped["parse_failed_interval_contract"] == 1
    assert "parse_failed" not in report.skipped


@pytest.mark.anyio
async def test_paper_market_runner_interval_contracts_are_opt_in(db_session: Session) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(refresh_prices=False, create_trades=False, allow_interval_contracts=True),
        discovery_service=FakeDiscoveryService([
            _discovered_market(
                source_market_id="interval-market",
                question="Will Hong Kong have between 190-200mm of precipitation in June?",
            )
        ]),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.processed == 1
    assert "parse_failed_interval_contract" not in report.skipped
    assert report.parsed == 1
    assert report.predictions_created == 1
    assert report.recommendations_created == 1
    assert report.skipped["trade_creation_disabled"] == 1


@pytest.mark.anyio
async def test_paper_market_runner_processes_temperature_bucket_market(db_session: Session) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(refresh_prices=False, create_trades=False),
        discovery_service=FakeDiscoveryService([
            _discovered_market(
                source_market_id="nyc-high-temp-bucket",
                question="Highest temperature in NYC on May 17, 2099 80-81F?",
                yes_price=0.44,
                no_price=0.56,
            )
        ]),
        forecast_provider=fixture_temperature_forecast,
    )

    report = await runner.run_once()

    assert report.processed == 1
    assert report.parsed == 1
    assert report.forecasts_created == 1
    assert report.predictions_created == 1
    assert report.recommendations_created == 1
    assert report.actionable_recommendations == 1
    assert report.expected_paper_trades == 1
    assert report.skipped["trade_creation_disabled"] == 1


@pytest.mark.anyio
async def test_paper_market_runner_does_not_reuse_interval_parse_when_disabled(db_session: Session) -> None:
    market = Market(
        source="polymarket",
        source_market_id="stored-interval",
        condition_id="condition-stored-interval",
        question="Will Hong Kong have between 190-200mm of precipitation in May?",
        active=True,
        closed=False,
    )
    db_session.add(market)
    db_session.flush()
    db_session.add(
        ParsedMarket(
            market_id=market.id,
            location_name="Hong Kong",
            latitude=22.3193,
            longitude=114.1694,
            metric="precipitation",
            operator="between",
            threshold_value=190.0,
            threshold_unit="mm",
            parser_version="regex_precip_v1",
            parse_confidence=0.75,
            raw_parse_json={"interval_upper_value": 200.0},
        )
    )
    db_session.commit()

    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(refresh_prices=False, allow_interval_contracts=False),
        discovery_service=FakeDiscoveryService([
            _discovered_market(
                source_market_id="stored-interval",
                question="Will Hong Kong have between 190-200mm of precipitation in May?",
            )
        ]),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.processed == 1
    assert report.forecasts_created == 0
    assert report.skipped["parse_failed_interval_contract"] == 1


@pytest.mark.anyio
async def test_paper_market_runner_reparses_incomplete_existing_parse(db_session: Session) -> None:
    market = Market(
        source="polymarket",
        source_market_id="incomplete-parse",
        condition_id="condition-incomplete-parse",
        question="Will Chicago get more than 1 inch of rain tomorrow?",
        active=True,
        closed=False,
    )
    db_session.add(market)
    db_session.flush()
    db_session.add(
        ParsedMarket(
            market_id=market.id,
            location_name="Chicago",
            latitude=41.8781,
            longitude=-87.6298,
            metric="precipitation",
            operator=">",
            threshold_value=1.0,
            threshold_unit="inch",
            parser_version="regex_precip_v1",
            parse_confidence=0.75,
            raw_parse_json={"legacy": "missing_target_window"},
        )
    )
    db_session.commit()

    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(refresh_prices=False, create_trades=False),
        discovery_service=FakeDiscoveryService([
            _discovered_market(
                source_market_id="incomplete-parse",
                question="Will Chicago get more than 1 inch of rain tomorrow?",
            )
        ]),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    parsed_records = list(
        db_session.scalars(select(ParsedMarket).where(ParsedMarket.market_id == market.id).order_by(ParsedMarket.id.asc()))
    )
    assert report.parsed == 1
    assert report.forecasts_created == 1
    assert len(parsed_records) == 2
    assert parsed_records[-1].target_start is not None


@pytest.mark.anyio
async def test_paper_market_runner_prioritizes_precipitation_candidates(db_session: Session) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(refresh_prices=False, process_limit=1),
        discovery_service=FakeDiscoveryService([
            _discovered_market(
                source_market_id="space-weather",
                question="Will there be exactly 3 major space weather events this week?",
            ),
            _discovered_market(
                source_market_id="london-rain",
                question="Will London have less than 5mm of precipitation in June?",
            ),
        ]),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.processed == 1
    assert report.parsed == 1
    assert report.predictions_created == 1
    assert "parse_failed_not_precipitation" not in report.skipped


@pytest.mark.anyio
async def test_paper_market_runner_uses_stored_price_snapshot_when_refresh_404s(db_session: Session) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(max_trades=1, quantity=2.0, refresh_prices=True, allow_stale_price_fallback=True),
        discovery_service=FakeDiscoveryService([_discovered_market()]),
        refresh_service=FailingRefreshService(),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.processed == 1
    assert report.paper_trades_created == 1
    assert report.skipped["price_refresh_failed_used_stored_snapshot"] == 1
    assert "price_refresh_failed" not in report.skipped
    assert report.stale_price_fallbacks_used == 1

    market = db_session.query(Market).one()
    assert market.source_diagnostics["price_status"] == "stale_supported"
    assert market.source_diagnostics["fallback_price_snapshot_used"] is True
    assert market.source_diagnostics["public_source_error"]["status_code"] == 404


@pytest.mark.anyio
async def test_paper_market_runner_requires_fresh_prices_when_refresh_404s(db_session: Session) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(max_trades=1, quantity=2.0, refresh_prices=True),
        discovery_service=FakeDiscoveryService([_discovered_market()]),
        refresh_service=FailingRefreshService(),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.processed == 1
    assert report.paper_trades_created == 0
    assert report.skipped["price_refresh_failed_fresh_price_required"] == 1
    assert "price_refresh_failed_used_stored_snapshot" not in report.skipped
    assert report.stale_price_fallbacks_used == 0

    market = db_session.query(Market).one()
    assert market.source_diagnostics["price_status"] == "fresh_price_required"
    assert market.source_diagnostics["fallback_price_snapshot_used"] is False
    assert "stale_price_fallback_requires_opt_in" in market.source_diagnostics["unsupported_reasons"]


@pytest.mark.anyio
async def test_recorded_paper_market_runner_persists_run_report(db_session: Session) -> None:
    config = PaperMarketRunnerConfig(refresh_prices=False, max_trades=1, quantity=2.0)
    runner = PaperMarketRunner(
        db=db_session,
        config=config,
        discovery_service=FakeDiscoveryService([_discovered_market()]),
        forecast_provider=fixture_forecast,
    )

    run = await run_paper_market_once_recorded(db_session, config=config, runner=runner)

    assert run.status == "completed"
    assert run.source == "polymarket"
    assert run.completed_at is not None
    assert run.config_json["max_trades"] == 1
    assert run.config_json["create_trades"] is True
    assert run.discovered == 1
    assert run.paper_trades_created == 1
    assert run.skipped_json == {}
    assert run.errors_json == []

    stored_run = db_session.get(PaperRunnerRun, run.id)
    assert stored_run is not None
    assert stored_run.report_json["paper_trades_created"] == 1


@pytest.mark.anyio
async def test_recorded_paper_market_runner_persists_failed_run(db_session: Session) -> None:
    class FailingRunner:
        async def run_once(self):
            raise RuntimeError("source unavailable")

    with pytest.raises(RuntimeError):
        await run_paper_market_once_recorded(
            db_session,
            config=PaperMarketRunnerConfig(refresh_prices=False),
            runner=FailingRunner(),
        )

    stored_run = db_session.scalars(select(PaperRunnerRun)).one()
    assert stored_run.status == "failed"
    assert stored_run.completed_at is not None
    assert stored_run.errors_json == ["source unavailable"]
