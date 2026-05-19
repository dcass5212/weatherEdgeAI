from app.db.models import ParsedMarket, WeatherForecastSnapshot
from app.modeling.model_registry import run_prediction_model
from app.modeling.temperature_bucket import estimate_temperature_bucket_probability


def test_temperature_bucket_probability_higher_inside_range() -> None:
    p_yes, confidence = estimate_temperature_bucket_probability(80.5, 80, "between", interval_upper_value=81)

    assert p_yes == 0.62
    assert confidence == "low"


def test_temperature_bucket_probability_lower_when_far_outside_range() -> None:
    p_yes, confidence = estimate_temperature_bucket_probability(75, 80, "between", interval_upper_value=81)

    assert p_yes == 0.15
    assert confidence == "low"


def test_default_registry_dispatches_temperature_market_to_temperature_model() -> None:
    parsed_market = ParsedMarket(
        id=1,
        market_id=1,
        location_name="New York City",
        latitude=40.7128,
        longitude=-74.006,
        metric="temperature",
        operator="between",
        threshold_value=80,
        threshold_unit="F",
        parser_version="regex_weather_v1",
        parse_confidence=0.8,
        raw_parse_json={"temperature_kind": "high", "interval_upper_value": 81},
    )
    forecast = WeatherForecastSnapshot(
        id=1,
        parsed_market_id=1,
        forecast_source="test_fixture",
        forecast_timestamp=None,
        forecast_temp_max=27.0,
        forecast_temp_unit="C",
        raw_json={"test_fixture": True},
    )

    result = run_prediction_model(parsed_market, forecast)

    assert result.model_version == "baseline_temperature_bucket_v1"
    assert result.p_yes == 0.62
    assert result.features_json["forecast_temperature"] == 80.6
    assert result.features_json["temperature_kind"] == "high"
