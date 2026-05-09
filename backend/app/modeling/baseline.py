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
) -> tuple[float, str]:
    if threshold_value <= 0:
        raise ValueError("threshold_value must be greater than 0")

    if forecast_precip_total is None:
        return 0.5, "low"

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


def run_baseline_prediction(parsed_market: ParsedMarket, forecast: WeatherForecastSnapshot) -> PredictionResult:
    p_yes, confidence = estimate_precipitation_probability(
        forecast_precip_total=forecast.forecast_precip_total,
        threshold_value=parsed_market.threshold_value,
        operator=parsed_market.operator,
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
            "threshold_unit": parsed_market.threshold_unit,
            "operator": parsed_market.operator,
        },
    )
