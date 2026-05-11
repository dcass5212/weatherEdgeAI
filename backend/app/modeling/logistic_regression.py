"""Fixed-coefficient logistic regression model for precipitation markets.

The model uses explicit, hand-selected coefficients over forecast-vs-threshold
features. It is a logistic-regression-shaped model for research comparison, not
a trained performance claim. Future work can replace the coefficients with
values learned from resolved outcomes once the dataset is large enough.
"""

from math import exp, log1p

from app.db.models import ParsedMarket, WeatherForecastSnapshot
from app.modeling.baseline import PredictionResult


MODEL_VERSION = "logistic_precip_v1"

_INTERCEPT = 0.0
_MARGIN_RATIO_COEFFICIENT = 2.2
_LOG_THRESHOLD_COEFFICIENT = 0.0
_LESS_THAN_OPERATOR_COEFFICIENT = -0.05

_INTERVAL_INTERCEPT = -0.25
_INTERVAL_MARGIN_RATIO_COEFFICIENT = 2.0


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = exp(-value)
        return 1 / (1 + z)
    z = exp(value)
    return z / (1 + z)


def _clamp_probability(value: float) -> float:
    return min(max(value, 0.05), 0.95)


def _threshold_in_forecast_units(threshold_value: float, threshold_unit: str | None, forecast_unit: str | None) -> float:
    threshold = float(threshold_value)
    normalized_threshold_unit = (threshold_unit or "").lower()
    normalized_forecast_unit = (forecast_unit or "").lower()
    if normalized_threshold_unit in {"mm", "millimeter", "millimeters"} and normalized_forecast_unit in {
        "inch",
        "inches",
    }:
        return threshold / 25.4
    if normalized_threshold_unit in {"inch", "inches"} and normalized_forecast_unit in {"mm", "millimeter", "millimeters"}:
        return threshold * 25.4
    return threshold


def _interval_upper_value(parsed_market: ParsedMarket, forecast_unit: str | None) -> float | None:
    raw_parse_json = parsed_market.raw_parse_json if isinstance(parsed_market.raw_parse_json, dict) else {}
    value = raw_parse_json.get("interval_upper_value")
    if value is None:
        return None
    try:
        return _threshold_in_forecast_units(float(value), parsed_market.threshold_unit, forecast_unit)
    except (TypeError, ValueError):
        return None


def _confidence_for_probability(probability: float, missing_forecast: bool = False) -> str:
    if missing_forecast:
        return "low"
    distance = abs(probability - 0.5)
    if distance >= 0.15:
        return "medium"
    return "low"


def estimate_logistic_precipitation_probability(
    forecast_precip_total: float | None,
    threshold_value: float,
    threshold_unit: str | None = "inch",
    forecast_precip_unit: str | None = "inch",
    operator: str = ">",
    interval_upper_value: float | None = None,
) -> tuple[float, str, dict]:
    if threshold_value <= 0:
        raise ValueError("threshold_value must be greater than 0")

    threshold = _threshold_in_forecast_units(threshold_value, threshold_unit, forecast_precip_unit)
    if forecast_precip_total is None:
        features = {
            "forecast_precip_total": None,
            "threshold_value_in_forecast_unit": threshold,
            "margin": None,
            "margin_ratio": None,
            "logit": 0.0,
        }
        return 0.5, "low", features

    forecast_value = float(forecast_precip_total)
    scale = max(abs(threshold), 0.25)

    if operator == "between":
        if interval_upper_value is None or interval_upper_value <= threshold:
            raise ValueError("between operator requires positive increasing interval thresholds")
        if threshold <= forecast_value <= interval_upper_value:
            margin = min(forecast_value - threshold, interval_upper_value - forecast_value)
        elif forecast_value < threshold:
            margin = forecast_value - threshold
        else:
            margin = interval_upper_value - forecast_value
        margin_ratio = margin / max(interval_upper_value - threshold, 0.25)
        logit = _INTERVAL_INTERCEPT + (_INTERVAL_MARGIN_RATIO_COEFFICIENT * margin_ratio)
    elif operator in {">", ">="}:
        margin = forecast_value - threshold
        margin_ratio = margin / scale
        logit = _INTERCEPT + (_MARGIN_RATIO_COEFFICIENT * margin_ratio) + (_LOG_THRESHOLD_COEFFICIENT * log1p(scale))
    elif operator in {"<", "<="}:
        margin = threshold - forecast_value
        margin_ratio = margin / scale
        logit = (
            _INTERCEPT
            + (_MARGIN_RATIO_COEFFICIENT * margin_ratio)
            + (_LOG_THRESHOLD_COEFFICIENT * log1p(scale))
            + _LESS_THAN_OPERATOR_COEFFICIENT
        )
    else:
        raise ValueError("logistic_precip_v1 only supports precipitation threshold operators")

    p_yes = round(_clamp_probability(_sigmoid(logit)), 6)
    features = {
        "forecast_precip_total": forecast_value,
        "forecast_precip_unit": forecast_precip_unit,
        "threshold_value": threshold_value,
        "threshold_unit": threshold_unit,
        "threshold_value_in_forecast_unit": round(threshold, 6),
        "operator": operator,
        "margin": round(margin, 6),
        "margin_ratio": round(margin_ratio, 6),
        "logit": round(logit, 6),
    }
    if operator == "between":
        features["interval_upper_value_in_forecast_unit"] = round(interval_upper_value, 6)
    return p_yes, _confidence_for_probability(p_yes), features


def run_logistic_regression_prediction(parsed_market: ParsedMarket, forecast: WeatherForecastSnapshot) -> PredictionResult:
    interval_upper_value = _interval_upper_value(parsed_market, forecast.forecast_precip_unit)
    p_yes, confidence, features = estimate_logistic_precipitation_probability(
        forecast_precip_total=forecast.forecast_precip_total,
        threshold_value=parsed_market.threshold_value,
        threshold_unit=parsed_market.threshold_unit,
        forecast_precip_unit=forecast.forecast_precip_unit,
        operator=parsed_market.operator,
        interval_upper_value=interval_upper_value,
    )
    p_no = round(1 - p_yes, 10)
    features["model_family"] = "fixed_coefficient_logistic_regression"
    features["coefficient_source"] = "hand_selected_initial_coefficients"
    return PredictionResult(
        model_version=MODEL_VERSION,
        p_yes=p_yes,
        p_no=p_no,
        confidence=confidence,
        features_json=features,
    )
