import json
from pathlib import Path

from app.db.models import ParsedMarket
from app.weather.forecast_service import build_forecast_snapshot


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
