from datetime import datetime, timezone

from app.markets.market_parser import parse_precipitation_market


def test_parse_more_than_one_inch() -> None:
    result = parse_precipitation_market("Will New York City get more than 1 inch of rain on May 5?")

    assert result.success is True
    assert result.location_name == "New York City"
    assert result.metric == "precipitation"
    assert result.operator == ">"
    assert result.threshold_value == 1
    assert result.threshold_unit == "inch"
    assert result.latitude is None
    assert result.longitude is None
    assert result.target_start is not None
    assert result.parser_version == "regex_precip_v1"
    assert result.parse_confidence > 0


def test_parse_at_least_half_inch() -> None:
    result = parse_precipitation_market("Will Chicago receive at least 0.5 inches of rain tomorrow?")

    assert result.success is True
    assert result.location_name == "Chicago"
    assert result.operator == ">="
    assert result.threshold_value == 0.5
    assert result.threshold_unit == "inches"


def test_parse_over_precipitation_wording() -> None:
    result = parse_precipitation_market("Will NYC have over 1.25 inches of precipitation on May 5?")

    assert result.success is True
    assert result.location_name == "NYC"
    assert result.operator == ">"
    assert result.threshold_value == 1.25
    assert result.threshold_unit == "inches"
    assert result.latitude is None
    assert result.longitude is None


def test_parse_or_more_wording() -> None:
    result = parse_precipitation_market("Will Chicago get 0.5 inches or more of rain tomorrow?")

    assert result.success is True
    assert result.location_name == "Chicago"
    assert result.operator == ">="
    assert result.threshold_value == 0.5


def test_parse_there_be_rain_in_location_wording() -> None:
    result = parse_precipitation_market("Will there be more than 1 inch of rain in New York City on May 5?")

    assert result.success is True
    assert result.location_name == "New York City"
    assert result.operator == ">"
    assert result.threshold_value == 1
    assert result.target_start is not None


def test_parse_tomorrow_uses_reference_datetime() -> None:
    result = parse_precipitation_market(
        "Will Chicago receive at least 0.5 inches of rain tomorrow?",
        reference_datetime=datetime(2026, 5, 9, 12, tzinfo=timezone.utc),
    )

    assert result.success is True
    assert result.target_start is not None
    assert result.target_start.date().isoformat() == "2026-05-10"


def test_parse_explicit_year_is_not_rolled_forward() -> None:
    result = parse_precipitation_market(
        "Will New York City get more than 1 inch of rain on May 5, 2026?",
        reference_datetime=datetime(2026, 5, 9, 12, tzinfo=timezone.utc),
    )

    assert result.success is True
    assert result.target_start is not None
    assert result.target_start.date().isoformat() == "2026-05-05"


def test_unsupported_question_returns_safe_failure() -> None:
    result = parse_precipitation_market("Will a hurricane make landfall this season?")

    assert result.success is False
    assert result.location_name is None
    assert result.parse_confidence == 0
    assert result.error == "Unsupported market question format: expected a precipitation threshold question."


def test_precipitation_question_without_threshold_returns_clear_failure() -> None:
    result = parse_precipitation_market("Will it rain in Chicago tomorrow?")

    assert result.success is False
    assert result.error == "Unsupported precipitation question: missing numeric threshold."


def test_precipitation_question_without_supported_unit_returns_clear_failure() -> None:
    result = parse_precipitation_market("Will Chicago get more than 10 millimeters of rain tomorrow?")

    assert result.success is False
    assert result.error == "Unsupported precipitation question: threshold unit must be inches."
