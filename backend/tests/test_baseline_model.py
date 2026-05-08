from app.modeling.baseline import estimate_precipitation_probability


def test_forecast_above_threshold_returns_higher_yes_probability() -> None:
    p_yes, confidence = estimate_precipitation_probability(1.6, 1.0, ">")

    assert p_yes == 0.75
    assert confidence == "medium"


def test_forecast_below_threshold_returns_lower_yes_probability() -> None:
    p_yes, confidence = estimate_precipitation_probability(0.2, 1.0, ">")

    assert p_yes == 0.25
    assert confidence == "medium"


def test_missing_forecast_returns_uncertain_probability() -> None:
    p_yes, confidence = estimate_precipitation_probability(None, 1.0, ">")

    assert p_yes == 0.5
    assert confidence == "low"
