import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.db.models import ParsedMarket
from app.weather.forecast_service import build_forecast_snapshot, fetch_forecast_for_parsed_market


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


def _parsed_market(threshold_unit: str = "inch") -> ParsedMarket:
    return ParsedMarket(
        id=1,
        market_id=1,
        location_name="New York City",
        latitude=40.7128,
        longitude=-74.0060,
        metric="precipitation",
        operator=">",
        threshold_value=1.0,
        threshold_unit=threshold_unit,
        parse_confidence=0.85,
        parser_version="regex_precip_v1",
    )


class RecordingForecastClient:
    def __init__(self) -> None:
        self.called = False
        self.requests: list[tuple[float, float, str, str]] = []

    async def fetch_forecast(self, latitude: float, longitude: float, start_date: str, end_date: str) -> dict:
        self.called = True
        self.requests.append((latitude, longitude, start_date, end_date))
        return {
            "daily": {"precipitation_sum": [12.7]},
            "daily_units": {"precipitation_sum": "mm"},
        }


class RecordingArchiveClient:
    def __init__(self) -> None:
        self.called = False
        self.requests: list[tuple[float, float, str, str]] = []

    async def fetch_daily_observations(self, latitude: float, longitude: float, start_date: str, end_date: str) -> dict:
        self.called = True
        self.requests.append((latitude, longitude, start_date, end_date))
        return {
            "daily": {"precipitation_sum": [12.7, 12.7]},
            "daily_units": {"precipitation_sum": "mm"},
        }


def test_build_forecast_snapshot_converts_open_meteo_mm_to_inches() -> None:
    raw_forecast = {
        "daily": {
            "precipitation_sum": [12.7, 12.7],
            "temperature_2m_max": [70.0, 72.0],
            "temperature_2m_min": [55.0, 54.0],
        },
        "daily_units": {
            "precipitation_sum": "mm",
            "temperature_2m_max": "°F",
            "temperature_2m_min": "°F",
        },
    }

    snapshot = build_forecast_snapshot(_parsed_market(), raw_forecast)

    assert snapshot.forecast_source == "open_meteo"
    assert snapshot.forecast_precip_total == 1.0
    assert snapshot.forecast_precip_unit == "inch"
    assert snapshot.forecast_temp_max == 72.0
    assert snapshot.forecast_temp_min == 54.0


def test_build_forecast_snapshot_handles_mixed_fixture_values() -> None:
    raw_forecast = _load_fixture("open_meteo_daily_mixed_values.json")

    snapshot = build_forecast_snapshot(_parsed_market(), raw_forecast)

    assert snapshot.forecast_precip_total == 1.0
    assert snapshot.forecast_precip_unit == "inch"
    assert snapshot.forecast_temp_max == 72.0
    assert snapshot.forecast_temp_min == 54.0
    assert snapshot.forecast_temp_unit == "F"
    assert snapshot.raw_json == raw_forecast


def test_build_forecast_snapshot_handles_missing_fixture_values() -> None:
    raw_forecast = _load_fixture("open_meteo_daily_missing_values.json")

    snapshot = build_forecast_snapshot(_parsed_market(), raw_forecast)

    assert snapshot.forecast_precip_total is None
    assert snapshot.forecast_precip_unit == "mm"
    assert snapshot.forecast_temp_max is None
    assert snapshot.forecast_temp_min is None


def test_build_forecast_snapshot_preserves_inch_units() -> None:
    raw_forecast = _load_fixture("open_meteo_daily_inches.json")

    snapshot = build_forecast_snapshot(_parsed_market(), raw_forecast)

    assert snapshot.forecast_precip_total == 1.0
    assert snapshot.forecast_precip_unit == "inch"


@pytest.mark.anyio
async def test_fetch_forecast_rejects_started_target_window_before_provider_call() -> None:
    parsed_market = _parsed_market()
    parsed_market.target_start = datetime.now(timezone.utc) - timedelta(days=1)
    parsed_market.target_end = datetime.now(timezone.utc) + timedelta(days=20)
    client = RecordingForecastClient()

    with pytest.raises(ValueError, match="forecast target window has already started"):
        await fetch_forecast_for_parsed_market(parsed_market, client=client, allow_started_window=False)

    assert client.called is False


@pytest.mark.anyio
async def test_fetch_forecast_combines_observed_to_date_and_remaining_forecast_for_started_window() -> None:
    parsed_market = _parsed_market()
    parsed_market.target_start = datetime.now(timezone.utc) - timedelta(days=2)
    parsed_market.target_end = datetime.now(timezone.utc) + timedelta(days=2)
    forecast_client = RecordingForecastClient()
    archive_client = RecordingArchiveClient()

    snapshot = await fetch_forecast_for_parsed_market(
        parsed_market,
        client=forecast_client,
        archive_client=archive_client,
    )

    assert forecast_client.called is True
    assert archive_client.called is True
    assert snapshot.forecast_source == "open_meteo_partial_window"
    assert snapshot.forecast_precip_total == 1.5
    assert snapshot.forecast_precip_unit == "inch"
    assert snapshot.raw_json["observed_to_date"]["precip_total"] == 1.0
    assert snapshot.raw_json["forecast_remaining"]["precip_total"] == 0.5
