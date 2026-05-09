from datetime import datetime, timezone

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
            raw_json={"source": "test_fixture"},
        ),
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
    return WeatherForecastSnapshot(
        parsed_market_id=parsed_market.id,
        forecast_source="test_fixture",
        forecast_timestamp=datetime(2026, 5, 9, 12, tzinfo=timezone.utc),
        target_start=parsed_market.target_start,
        target_end=parsed_market.target_end,
        forecast_precip_total=1.6,
        forecast_precip_unit="inch",
        raw_json={"test_fixture": True},
    )


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

    trade = db_session.scalars(select(PaperTrade)).one()
    assert trade.side == "YES"
    assert trade.entry_price == 0.44
    assert trade.quantity == 2.0
    assert trade.status == "OPEN"


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
async def test_paper_market_runner_uses_stored_price_snapshot_when_refresh_404s(db_session: Session) -> None:
    runner = PaperMarketRunner(
        db=db_session,
        config=PaperMarketRunnerConfig(max_trades=1, quantity=2.0, refresh_prices=True),
        discovery_service=FakeDiscoveryService([_discovered_market()]),
        refresh_service=FailingRefreshService(),
        forecast_provider=fixture_forecast,
    )

    report = await runner.run_once()

    assert report.processed == 1
    assert report.paper_trades_created == 1
    assert report.skipped["price_refresh_failed_used_stored_snapshot"] == 1
    assert "price_refresh_failed" not in report.skipped

    market = db_session.query(Market).one()
    assert market.source_diagnostics["price_status"] == "stale_supported"
    assert market.source_diagnostics["fallback_price_snapshot_used"] is True
    assert market.source_diagnostics["public_source_error"]["status_code"] == 404


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
