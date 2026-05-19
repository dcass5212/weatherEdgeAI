"""Forecast normalization and snapshot creation.

Weather providers return nested, provider-specific payloads. This module turns
Open-Meteo daily forecasts into stored snapshots with normalized precipitation
units and defensive handling for missing or malformed values.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.db.models import ParsedMarket, WeatherForecastSnapshot, utc_now
from app.weather.open_meteo_client import OpenMeteoArchiveClient, OpenMeteoClient


def _date_string(value: object) -> str:
    if hasattr(value, "date"):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return utc_now().date().isoformat()


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _numeric_values(values: list[Any]) -> list[float]:
    return [parsed for value in values if (parsed := _as_float(value)) is not None]


def _sum_numeric(values: list[Any]) -> float | None:
    numeric = _numeric_values(values)
    if not numeric:
        return None
    return round(sum(numeric), 4)


def _max_numeric(values: list[Any]) -> float | None:
    numeric = _numeric_values(values)
    return max(numeric) if numeric else None


def _min_numeric(values: list[Any]) -> float | None:
    numeric = _numeric_values(values)
    return min(numeric) if numeric else None


def _daily_list(daily: dict[str, Any], key: str) -> list[Any]:
    value = daily.get(key)
    return value if isinstance(value, list) else []


def _normalize_precip_unit(unit: Any) -> str | None:
    if not isinstance(unit, str) or not unit.strip():
        return None
    normalized = unit.strip().lower()
    if normalized in {"mm", "millimeter", "millimeters"}:
        return "mm"
    if normalized in {"inch", "inches", "in"}:
        return "inch"
    return normalized


def _target_precip_unit(threshold_unit: str) -> str:
    return "inch" if threshold_unit.lower() in {"inch", "inches", "in"} else threshold_unit.lower()


def _aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _precip_total_in_target_unit(raw_weather: dict[str, Any], target_unit: str) -> tuple[float | None, str | None]:
    daily = raw_weather.get("daily") if isinstance(raw_weather.get("daily"), dict) else {}
    units = raw_weather.get("daily_units") if isinstance(raw_weather.get("daily_units"), dict) else {}
    source_unit = _normalize_precip_unit(units.get("precipitation_sum"))
    total = _sum_numeric(_daily_list(daily, "precipitation_sum"))
    if total is None:
        return None, source_unit
    if source_unit == "mm" and target_unit == "inch":
        return round(total / 25.4, 4), target_unit
    return total, source_unit


def build_forecast_snapshot(parsed_market: ParsedMarket, raw_forecast: dict[str, Any]) -> WeatherForecastSnapshot:
    daily = raw_forecast.get("daily") if isinstance(raw_forecast.get("daily"), dict) else {}
    units = raw_forecast.get("daily_units") if isinstance(raw_forecast.get("daily_units"), dict) else {}
    precipitation = _daily_list(daily, "precipitation_sum")
    temp_max = _daily_list(daily, "temperature_2m_max")
    temp_min = _daily_list(daily, "temperature_2m_min")

    forecast_precip_total = _sum_numeric(precipitation)
    forecast_precip_unit = _normalize_precip_unit(units.get("precipitation_sum"))
    target_precip_unit = _target_precip_unit(parsed_market.threshold_unit)
    if forecast_precip_total is not None and forecast_precip_unit == "mm" and target_precip_unit == "inch":
        forecast_precip_total = round(forecast_precip_total / 25.4, 4)
        forecast_precip_unit = target_precip_unit

    return WeatherForecastSnapshot(
        parsed_market_id=parsed_market.id,
        forecast_source="open_meteo",
        forecast_timestamp=utc_now(),
        target_start=parsed_market.target_start,
        target_end=parsed_market.target_end,
        forecast_precip_total=forecast_precip_total,
        forecast_precip_unit=forecast_precip_unit,
        forecast_temp_max=_max_numeric(temp_max),
        forecast_temp_min=_min_numeric(temp_min),
        forecast_temp_unit=units.get("temperature_2m_max") or units.get("temperature_2m_min"),
        raw_json=raw_forecast,
    )


def build_partial_window_forecast_snapshot(
    parsed_market: ParsedMarket,
    raw_observations: dict[str, Any] | None,
    raw_forecast: dict[str, Any],
    *,
    observation_start_date: str | None,
    observation_end_date: str | None,
    forecast_start_date: str,
    forecast_end_date: str,
) -> WeatherForecastSnapshot:
    """Build a full-window precipitation estimate for an already-started target."""
    target_unit = _target_precip_unit(parsed_market.threshold_unit)
    observed_total, observed_unit = (
        _precip_total_in_target_unit(raw_observations, target_unit) if raw_observations is not None else (0.0, target_unit)
    )
    forecast_total, forecast_unit = _precip_total_in_target_unit(raw_forecast, target_unit)
    if observed_total is None:
        observed_total = 0.0
    forecast_precip_total = None if forecast_total is None else round(observed_total + forecast_total, 4)
    forecast_snapshot = build_forecast_snapshot(parsed_market, raw_forecast)
    forecast_snapshot.forecast_source = "open_meteo_partial_window"
    forecast_snapshot.forecast_precip_total = forecast_precip_total
    forecast_snapshot.forecast_precip_unit = forecast_unit or observed_unit or target_unit
    forecast_snapshot.raw_json = {
        "source": "open_meteo_partial_window",
        "observed_to_date": {
            "start_date": observation_start_date,
            "end_date": observation_end_date,
            "precip_total": observed_total,
            "precip_unit": observed_unit,
            "provider_payload": raw_observations,
        },
        "forecast_remaining": {
            "start_date": forecast_start_date,
            "end_date": forecast_end_date,
            "precip_total": forecast_total,
            "precip_unit": forecast_unit,
            "provider_payload": raw_forecast,
        },
        "combined_precip_total": forecast_precip_total,
        "combined_precip_unit": forecast_snapshot.forecast_precip_unit,
    }
    return forecast_snapshot


async def fetch_forecast_for_parsed_market(
    parsed_market: ParsedMarket,
    client: OpenMeteoClient | None = None,
    archive_client: OpenMeteoArchiveClient | None = None,
    allow_started_window: bool = True,
) -> WeatherForecastSnapshot:
    if parsed_market.latitude is None or parsed_market.longitude is None:
        raise ValueError("parsed market must include latitude and longitude before fetching a forecast")
    now = utc_now()
    target_start = _aware_datetime(parsed_market.target_start) if parsed_market.target_start is not None else None
    target_end = _aware_datetime(parsed_market.target_end) if parsed_market.target_end is not None else target_start
    if target_end is not None and target_end < now:
        raise ValueError("forecast target window has already elapsed; use observed-outcome/archive workflows")

    if target_start is not None and target_start < now:
        if not allow_started_window:
            raise ValueError(
                "forecast target window has already started; use observed-outcome/archive workflows or a future target window"
            )
        today = now.date()
        target_start_date = target_start.date()
        target_end_date = (target_end or now).date()
        observation_end_date = min(today - timedelta(days=1), target_end_date)
        raw_observations = None
        observation_start_string = None
        observation_end_string = None
        if observation_end_date >= target_start_date:
            observation_start_string = target_start_date.isoformat()
            observation_end_string = observation_end_date.isoformat()
            raw_observations = await (archive_client or OpenMeteoArchiveClient()).fetch_daily_observations(
                latitude=parsed_market.latitude,
                longitude=parsed_market.longitude,
                start_date=observation_start_string,
                end_date=observation_end_string,
            )

        forecast_start_date = max(today, target_start_date)
        forecast_end_date = target_end_date
        raw_forecast = await (client or OpenMeteoClient()).fetch_forecast(
            latitude=parsed_market.latitude,
            longitude=parsed_market.longitude,
            start_date=forecast_start_date.isoformat(),
            end_date=forecast_end_date.isoformat(),
        )
        return build_partial_window_forecast_snapshot(
            parsed_market,
            raw_observations,
            raw_forecast,
            observation_start_date=observation_start_string,
            observation_end_date=observation_end_string,
            forecast_start_date=forecast_start_date.isoformat(),
            forecast_end_date=forecast_end_date.isoformat(),
        )

    start_date = _date_string(parsed_market.target_start)
    end_date = _date_string(parsed_market.target_end or parsed_market.target_start)
    raw_forecast = await (client or OpenMeteoClient()).fetch_forecast(
        latitude=parsed_market.latitude,
        longitude=parsed_market.longitude,
        start_date=start_date,
        end_date=end_date,
    )
    return build_forecast_snapshot(parsed_market, raw_forecast)
