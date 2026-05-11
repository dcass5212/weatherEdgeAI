from app.db.models import ParsedMarket, WeatherForecastSnapshot
from app.modeling.logistic_regression import (
    MODEL_VERSION,
    estimate_logistic_precipitation_probability,
    run_logistic_regression_prediction,
)


def test_logistic_probability_increases_when_forecast_is_above_greater_than_threshold() -> None:
    low_probability, _, low_features = estimate_logistic_precipitation_probability(
        forecast_precip_total=0.2,
        threshold_value=1.0,
        operator=">",
    )
    high_probability, confidence, high_features = estimate_logistic_precipitation_probability(
        forecast_precip_total=1.6,
        threshold_value=1.0,
        operator=">",
    )

    assert high_probability > 0.75
    assert low_probability < 0.25
    assert high_probability > low_probability
    assert confidence == "medium"
    assert high_features["margin"] == 0.6
    assert high_features["margin_ratio"] == 0.6
    assert low_features["margin"] == -0.8


def test_logistic_less_than_operator_uses_yes_side_margin() -> None:
    p_yes, confidence, features = estimate_logistic_precipitation_probability(
        forecast_precip_total=1.2,
        threshold_value=2.0,
        operator="<",
    )

    assert p_yes > 0.65
    assert confidence == "medium"
    assert features["margin"] == 0.8


def test_logistic_model_converts_millimeter_thresholds_to_forecast_inches() -> None:
    p_yes, _, features = estimate_logistic_precipitation_probability(
        forecast_precip_total=10.0,
        threshold_value=240.0,
        threshold_unit="mm",
        forecast_precip_unit="inch",
        operator=">=",
    )

    assert p_yes > 0.5
    assert features["threshold_value_in_forecast_unit"] == 9.448819


def test_run_logistic_prediction_returns_versioned_feature_payload() -> None:
    parsed_market = ParsedMarket(
        market_id=1,
        location_name="New York City",
        metric="precipitation",
        operator=">",
        threshold_value=1.0,
        threshold_unit="inch",
        parse_confidence=0.8,
        parser_version="regex_precip_v1",
    )
    forecast = WeatherForecastSnapshot(
        parsed_market_id=1,
        forecast_source="fixture",
        forecast_precip_total=1.6,
        forecast_precip_unit="inch",
    )

    result = run_logistic_regression_prediction(parsed_market, forecast)

    assert result.model_version == MODEL_VERSION
    assert result.p_yes > 0.75
    assert result.p_no == round(1 - result.p_yes, 10)
    assert result.features_json["model_family"] == "fixed_coefficient_logistic_regression"
    assert result.features_json["coefficient_source"] == "hand_selected_initial_coefficients"
