"""Transparent precipitation baseline model.

This module keeps the original deterministic probability bands for weather
threshold markets. It remains the default model because it is simple,
inspectable, and useful as a comparison point for newer model versions.
"""

from dataclasses import dataclass

from app.db.models import ParsedMarket, WeatherForecastSnapshot


MODEL_VERSION = "baseline_precip_v1"


@dataclass(frozen=True)
class PredictionResult:
    model_version: str
    p_yes: float
    p_no: float
    confidence: str
    features_json: dict


def estimate_precipitation_probability(
    forecast_precip_total: float | None,
    threshold_value: float,
    operator: str = ">",
    interval_upper_value: float | None = None,
) -> tuple[float, str]:
    if threshold_value <= 0:
        raise ValueError("threshold_value must be greater than 0")

    if forecast_precip_total is None:
        return 0.5, "low"

    if operator == "between":
        return estimate_interval_precipitation_probability(
            forecast_precip_total=forecast_precip_total,
            lower_threshold=threshold_value,
            upper_threshold=interval_upper_value,
        )

    if operator not in {">", ">=", "<", "<="}:
        raise ValueError("baseline_precip_v1 only supports one-sided threshold operators")

    if operator in {"<", "<="}:
        difference = threshold_value - forecast_precip_total
    else:
        difference = forecast_precip_total - threshold_value
    if difference >= 0.5:
        return 0.75, "medium"
    if difference >= 0.1:
        return 0.60, "medium"
    if difference >= -0.1:
        return 0.50, "low"
    if difference >= -0.5:
        return 0.40, "medium"
    return 0.25, "medium"


def estimate_interval_precipitation_probability(
    forecast_precip_total: float,
    lower_threshold: float,
    upper_threshold: float | None,
) -> tuple[float, str]:
    if upper_threshold is None:
        raise ValueError("between operator requires interval_upper_value")
    if lower_threshold <= 0 or upper_threshold <= lower_threshold:
        raise ValueError("interval thresholds must be positive and increasing")

    interval_width = upper_threshold - lower_threshold
    if lower_threshold <= forecast_precip_total <= upper_threshold:
        return 0.65, "low"

    if forecast_precip_total < lower_threshold:
        distance = lower_threshold - forecast_precip_total
    else:
        distance = forecast_precip_total - upper_threshold

    near_margin = max(interval_width, 0.1)
    if distance <= near_margin:
        return 0.35, "low"
    return 0.20, "low"


def _interval_upper_value(parsed_market: ParsedMarket) -> float | None:
    raw_parse_json = parsed_market.raw_parse_json if isinstance(parsed_market.raw_parse_json, dict) else {}
    value = raw_parse_json.get("interval_upper_value")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def run_baseline_prediction(parsed_market: ParsedMarket, forecast: WeatherForecastSnapshot) -> PredictionResult:
    interval_upper_value = _interval_upper_value(parsed_market)
    p_yes, confidence = estimate_precipitation_probability(
        forecast_precip_total=forecast.forecast_precip_total,
        threshold_value=parsed_market.threshold_value,
        operator=parsed_market.operator,
        interval_upper_value=interval_upper_value,
    )
    p_no = round(1 - p_yes, 10)
    return PredictionResult(
        model_version=MODEL_VERSION,
        p_yes=p_yes,
        p_no=p_no,
        confidence=confidence,
        features_json={
            "forecast_precip_total": forecast.forecast_precip_total,
            "forecast_precip_unit": forecast.forecast_precip_unit,
            "threshold_value": parsed_market.threshold_value,
            "interval_upper_value": interval_upper_value,
            "threshold_unit": parsed_market.threshold_unit,
            "operator": parsed_market.operator,
        },
    )
