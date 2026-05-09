from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaperTrade, ParsedMarket, WeatherForecastSnapshot
from app.markets.market_discovery import DiscoveredMarket, DiscoveredPriceSnapshot
from app.strategy.paper_market_runner import PaperMarketRunner, PaperMarketRunnerConfig


def _discovered_market(
    source_market_id: str = "public-nyc-rain",
    yes_price: float | None = 0.44,
    no_price: float | None = 0.56,
    liquidity: float | None = 1000.0,
    spread: float | None = 0.02,
) -> DiscoveredMarket:
    return DiscoveredMarket(
        source="polymarket",
        source_market_id=source_market_id,
        condition_id=f"condition-{source_market_id}",
        question="Will New York City get more than 1 inch of rain tomorrow?",
        slug=source_market_id,
        category="weather",
        active=True,
        closed=False,
        end_time=None,
        resolution_source=None,
        raw_json={
            "id": source_market_id,
            "question": "Will New York City get more than 1 inch of rain tomorrow?",
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
