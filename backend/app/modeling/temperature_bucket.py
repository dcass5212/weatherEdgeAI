"""Baseline model for daily high/low temperature bucket markets.

Temperature bucket markets are binary contracts over a range, such as
`highest temperature in NYC on May 17 between 80-81F`. This model is a
transparent first pass around the point forecast; it is not trained evidence.
"""

from app.db.models import ParsedMarket, WeatherForecastSnapshot
from app.modeling.baseline import PredictionResult


MODEL_VERSION = "baseline_temperature_bucket_v1"


def _raw_parse_json(parsed_market: ParsedMarket) -> dict:
    return parsed_market.raw_parse_json if isinstance(parsed_market.raw_parse_json, dict) else {}


def _interval_upper_value(parsed_market: ParsedMarket) -> float | None:
    value = _raw_parse_json(parsed_market).get("interval_upper_value")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _temperature_kind(parsed_market: ParsedMarket) -> str:
    value = _raw_parse_json(parsed_market).get("temperature_kind")
    return "low" if isinstance(value, str) and value.lower() == "low" else "high"


def _normalize_unit(value: str | None) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().lower().replace("\u00b0", "")
    if normalized in {"f", "fahrenheit"}:
        return "F"
    if normalized in {"c", "celsius"}:
        return "C"
    return value


def _convert_temperature(value: float, source_unit: str | None, target_unit: str | None) -> float:
    source = _normalize_unit(source_unit)
    target = _normalize_unit(target_unit)
    if source == target or source is None or target is None:
        return value
    if source == "C" and target == "F":
        return (value * 9 / 5) + 32
    if source == "F" and target == "C":
        return (value - 32) * 5 / 9
    return value


def _forecast_temperature(parsed_market: ParsedMarket, forecast: WeatherForecastSnapshot) -> float | None:
    value = forecast.forecast_temp_min if _temperature_kind(parsed_market) == "low" else forecast.forecast_temp_max
    if value is None:
        return None
    return round(_convert_temperature(float(value), forecast.forecast_temp_unit, parsed_market.threshold_unit), 4)


def estimate_temperature_bucket_probability(
    forecast_temperature: float | None,
    threshold_value: float,
    operator: str,
    interval_upper_value: float | None = None,
) -> tuple[float, str]:
    if threshold_value <= 0:
        raise ValueError("temperature threshold_value must be greater than 0")
    if forecast_temperature is None:
        return 0.5, "low"

    if operator == "between":
        if interval_upper_value is None or interval_upper_value <= threshold_value:
            raise ValueError("temperature bucket markets require a positive increasing interval_upper_value")
        if threshold_value <= forecast_temperature <= interval_upper_value:
            return 0.62, "low"
        distance = threshold_value - forecast_temperature if forecast_temperature < threshold_value else forecast_temperature - interval_upper_value
        if distance <= 1:
            return 0.42, "low"
        if distance <= 3:
            return 0.28, "low"
        return 0.15, "low"

    if operator in {">", ">="}:
        margin = forecast_temperature - threshold_value
    elif operator in {"<", "<="}:
        margin = threshold_value - forecast_temperature
    elif operator == "=":
        distance = abs(forecast_temperature - threshold_value)
        if distance <= 0.5:
            return 0.45, "low"
        if distance <= 1.5:
            return 0.28, "low"
        return 0.12, "low"
    else:
        raise ValueError("baseline_temperature_bucket_v1 only supports temperature bucket or threshold operators")

    if margin >= 3:
        return 0.75, "medium"
    if margin >= 1:
        return 0.60, "medium"
    if margin >= -1:
        return 0.50, "low"
    if margin >= -3:
        return 0.35, "medium"
    return 0.20, "medium"


def run_temperature_bucket_prediction(parsed_market: ParsedMarket, forecast: WeatherForecastSnapshot) -> PredictionResult:
    forecast_temperature = _forecast_temperature(parsed_market, forecast)
    interval_upper_value = _interval_upper_value(parsed_market)
    p_yes, confidence = estimate_temperature_bucket_probability(
        forecast_temperature=forecast_temperature,
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
            "temperature_kind": _temperature_kind(parsed_market),
            "forecast_temperature": forecast_temperature,
            "forecast_temperature_source_unit": forecast.forecast_temp_unit,
            "threshold_value": parsed_market.threshold_value,
            "interval_upper_value": interval_upper_value,
            "threshold_unit": parsed_market.threshold_unit,
            "operator": parsed_market.operator,
            "model_family": "temperature_bucket_baseline",
            "model_limitations": "Point-forecast bucket baseline; not trained or calibrated.",
        },
    )
