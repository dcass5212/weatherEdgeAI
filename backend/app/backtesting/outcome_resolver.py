"""Observed-weather outcome resolution.

Resolved outcomes close the loop between predictions and evaluation. This
module turns observed daily precipitation payloads into YES/NO outcomes for
parsed precipitation markets while preserving provider payloads for auditability.
"""

from datetime import date
from typing import Any

from app.db.models import ParsedMarket, ResolvedOutcome, utc_now
from app.backtesting.noaa_client import NoaaCdoClient
from app.weather.open_meteo_client import OpenMeteoArchiveClient


def _date_string(value: object) -> str:
    if hasattr(value, "date"):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raise ValueError("parsed market must include target dates before resolving observed weather")


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


def _daily_list(raw_observations: dict[str, Any], key: str) -> list[Any]:
    daily = raw_observations.get("daily") if isinstance(raw_observations.get("daily"), dict) else {}
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


def _observed_precip_total(raw_observations: dict[str, Any], threshold_unit: str) -> tuple[float, str | None]:
    if _looks_like_noaa_daily_payload(raw_observations):
        return _noaa_daily_observed_precip_total(raw_observations, threshold_unit)

    values = [_as_float(value) for value in _daily_list(raw_observations, "precipitation_sum")]
    numeric_values = [value for value in values if value is not None]
    if not numeric_values:
        raise ValueError("observed weather payload did not include usable precipitation totals")

    daily_units = raw_observations.get("daily_units") if isinstance(raw_observations.get("daily_units"), dict) else {}
    source_unit = _normalize_precip_unit(daily_units.get("precipitation_sum"))
    target_unit = _target_precip_unit(threshold_unit)
    if source_unit is None:
        raise ValueError("observed weather payload did not include precipitation units")
    total = round(sum(numeric_values), 4)
    if source_unit == "mm" and target_unit == "inch":
        return round(total / 25.4, 4), target_unit
    if source_unit != target_unit:
        raise ValueError(f"observed precipitation unit {source_unit} is not comparable to threshold unit {target_unit}")
    return total, source_unit


def _looks_like_noaa_daily_payload(raw_observations: dict[str, Any]) -> bool:
    return isinstance(raw_observations.get("results"), list) or raw_observations.get("source") in {
        "noaa_cdo_daily",
        "ncei_daily_summaries",
    }


def _record_unit(record: dict[str, Any], raw_observations: dict[str, Any]) -> str | None:
    for value in (
        record.get("unit"),
        record.get("units"),
        raw_observations.get("precipitation_unit"),
        raw_observations.get("unit"),
    ):
        normalized = _normalize_precip_unit(value)
        if normalized is not None:
            return normalized

    attributes = record.get("attributes")
    if isinstance(attributes, dict):
        return _normalize_precip_unit(attributes.get("unit") or attributes.get("units"))
    return None


def _noaa_daily_observed_precip_total(raw_observations: dict[str, Any], threshold_unit: str) -> tuple[float, str | None]:
    results = raw_observations.get("results")
    if not isinstance(results, list):
        raise ValueError("NOAA daily payload did not include results")

    values: list[float] = []
    source_unit: str | None = None
    for record in results:
        if not isinstance(record, dict):
            continue
        datatype = record.get("datatype") or record.get("dataType") or record.get("name")
        if not isinstance(datatype, str) or datatype.upper() != "PRCP":
            continue
        value = _as_float(record.get("value"))
        if value is None:
            continue
        record_unit = _record_unit(record, raw_observations)
        if record_unit is None:
            raise ValueError("NOAA daily PRCP record did not include precipitation units")
        if source_unit is not None and record_unit != source_unit:
            raise ValueError("NOAA daily PRCP records used mixed precipitation units")
        source_unit = record_unit
        values.append(value)

    if not values:
        raise ValueError("NOAA daily payload did not include usable PRCP totals")

    target_unit = _target_precip_unit(threshold_unit)
    total = round(sum(values), 4)
    if source_unit == "mm" and target_unit == "inch":
        return round(total / 25.4, 4), target_unit
    if source_unit != target_unit:
        raise ValueError(f"NOAA daily precipitation unit {source_unit} is not comparable to threshold unit {target_unit}")
    return total, source_unit


def build_resolved_outcome_from_observations(
    parsed_market: ParsedMarket,
    raw_observations: dict[str, Any],
    resolution_source: str = "open_meteo_archive",
) -> ResolvedOutcome:
    if parsed_market.metric != "precipitation":
        raise ValueError("only precipitation parsed markets can be resolved from observed precipitation")

    actual_value, actual_unit = _observed_precip_total(raw_observations, parsed_market.threshold_unit)
    if parsed_market.operator == ">=":
        actual_outcome = "YES" if actual_value >= parsed_market.threshold_value else "NO"
    elif parsed_market.operator == ">":
        actual_outcome = "YES" if actual_value > parsed_market.threshold_value else "NO"
    else:
        raise ValueError(f"unsupported parsed market operator for observed weather resolution: {parsed_market.operator}")

    return ResolvedOutcome(
        market_id=parsed_market.market_id,
        actual_outcome=actual_outcome,
        actual_value=actual_value,
        actual_unit=actual_unit,
        resolution_source=resolution_source,
        resolved_at=utc_now(),
        raw_json={
            "source": resolution_source,
            "parsed_market_id": parsed_market.id,
            "threshold": {
                "operator": parsed_market.operator,
                "value": parsed_market.threshold_value,
                "unit": parsed_market.threshold_unit,
            },
            "provider_payload": raw_observations,
        },
    )


async def resolve_weather_outcome_for_parsed_market(
    parsed_market: ParsedMarket,
    provider: str = "open_meteo_archive",
    client: OpenMeteoArchiveClient | None = None,
    noaa_client: NoaaCdoClient | None = None,
) -> ResolvedOutcome:
    if parsed_market.latitude is None or parsed_market.longitude is None:
        raise ValueError("parsed market must include latitude and longitude before resolving observed weather")
    if parsed_market.target_start is None:
        raise ValueError("parsed market must include target dates before resolving observed weather")

    start_date = _date_string(parsed_market.target_start)
    end_date = _date_string(parsed_market.target_end or parsed_market.target_start)
    if provider == "open_meteo_archive":
        raw_observations = await (client or OpenMeteoArchiveClient()).fetch_daily_observations(
            latitude=parsed_market.latitude,
            longitude=parsed_market.longitude,
            start_date=start_date,
            end_date=end_date,
        )
        return build_resolved_outcome_from_observations(parsed_market, raw_observations, resolution_source=provider)

    if provider == "noaa_cdo_daily":
        raw_observations = await (noaa_client or NoaaCdoClient()).fetch_daily_precipitation(
            latitude=parsed_market.latitude,
            longitude=parsed_market.longitude,
            start_date=start_date,
            end_date=end_date,
        )
        return build_resolved_outcome_from_observations(parsed_market, raw_observations, resolution_source=provider)

    raise ValueError(f"unsupported observed-weather resolution provider: {provider}")
