"""Prediction model registry.

Routes and runner services use this small registry to choose a versioned model
without hardcoding every model implementation at the API boundary.
"""

from collections.abc import Callable

from app.db.models import ParsedMarket, WeatherForecastSnapshot
from app.modeling.baseline import MODEL_VERSION as BASELINE_MODEL_VERSION
from app.modeling.baseline import PredictionResult, run_baseline_prediction
from app.modeling.logistic_regression import MODEL_VERSION as LOGISTIC_MODEL_VERSION
from app.modeling.logistic_regression import run_logistic_regression_prediction


PredictionModel = Callable[[ParsedMarket, WeatherForecastSnapshot], PredictionResult]

DEFAULT_MODEL_VERSION = BASELINE_MODEL_VERSION

_MODELS: dict[str, PredictionModel] = {
    BASELINE_MODEL_VERSION: run_baseline_prediction,
    LOGISTIC_MODEL_VERSION: run_logistic_regression_prediction,
}


def available_model_versions() -> tuple[str, ...]:
    return tuple(_MODELS.keys())


def run_prediction_model(
    parsed_market: ParsedMarket,
    forecast: WeatherForecastSnapshot,
    model_version: str = DEFAULT_MODEL_VERSION,
) -> PredictionResult:
    try:
        model = _MODELS[model_version]
    except KeyError as exc:
        supported = ", ".join(available_model_versions())
        raise ValueError(f"Unsupported model_version '{model_version}'. Supported versions: {supported}") from exc
    return model(parsed_market, forecast)
