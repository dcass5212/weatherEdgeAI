"""Rule-based weather market parser.

V1 keeps parsing explicit and testable for precipitation threshold markets.
The parser favors narrow, explainable coverage over broad guesses because its
outputs drive forecast requests, probability modeling, and paper-trading EV.
"""

import re
from calendar import monthrange
from datetime import datetime, time, timedelta, timezone

from app.markets.schemas import ParsedMarketResult


PARSER_VERSION = "regex_weather_v1"
PRECIP_PARSER_VERSION = "regex_precip_v1"

THRESHOLD_PATTERN = r"(?P<threshold>\d+(?:\.\d+)?)"
UPPER_THRESHOLD_PATTERN = r"(?P<upper_threshold>\d+(?:\.\d+)?)"
UNIT_PATTERN = r"(?P<unit>inch|inches|in|mm|millimeter|millimeters)"
THRESHOLD_UNIT_PATTERN = rf"{THRESHOLD_PATTERN}\s*{UNIT_PATTERN}"
INTERVAL_THRESHOLD_UNIT_PATTERN = rf"{THRESHOLD_PATTERN}\s*(?:-|to|and)\s*{UPPER_THRESHOLD_PATTERN}\s*{UNIT_PATTERN}"
PRECIP_WORD_PATTERN = r"(?:rain|precipitation|precip)"
TEMP_WORD_PATTERN = r"(?:temperature|temp)"
TEMP_UNIT_PATTERN = r"(?P<unit>(?:\u00b0)?f|f|fahrenheit|(?:\u00b0)?c|c|celsius)"
TEMP_VALUE_PATTERN = r"(?P<threshold>\d+(?:\.\d+)?)"
TEMP_UPPER_VALUE_PATTERN = r"(?P<upper_threshold>\d+(?:\.\d+)?)"
TEMP_RANGE_PATTERN = rf"{TEMP_VALUE_PATTERN}\s*(?:-|to|and)\s*{TEMP_UPPER_VALUE_PATTERN}\s*{TEMP_UNIT_PATTERN}"
TEMP_SINGLE_PATTERN = rf"{TEMP_VALUE_PATTERN}\s*{TEMP_UNIT_PATTERN}"
DATE_PATTERN = r"(?:\s+(?:on\s+)?(?P<date>.+?))?"
LOCATION_DATE_PATTERN = r"(?:\s+on\s+(?P<date>.+?))?"

OPERATOR_PHRASES = {
    "more than": ">",
    "over": ">",
    "above": ">",
    "greater than": ">",
    "at least": ">=",
    "no less than": ">=",
    "less than": "<",
    "under": "<",
    "below": "<",
    "at most": "<=",
    "no more than": "<=",
}

PRECIPITATION_PATTERNS: list[tuple[re.Pattern[str], str | None]] = [
    (
        re.compile(
            rf"^Will (?P<location>.+?) (?:get|receive|see|record|have) "
            rf"(?P<operator_phrase>more than|over|above|greater than|at least|no less than|less than|under|below|at most|no more than) "
            rf"{THRESHOLD_UNIT_PATTERN} of {PRECIP_WORD_PATTERN}{DATE_PATTERN}\??$",
            re.IGNORECASE,
        ),
        None,
    ),
    (
        re.compile(
            rf"^Will (?P<location>.+?) (?:get|receive|see|record|have) "
            rf"{THRESHOLD_UNIT_PATTERN} or more of {PRECIP_WORD_PATTERN}{DATE_PATTERN}\??$",
            re.IGNORECASE,
        ),
        ">=",
    ),
    (
        re.compile(
            rf"^Will there be (?P<operator_phrase>more than|over|above|greater than|at least|no less than|less than|under|below|at most|no more than) "
            rf"{THRESHOLD_UNIT_PATTERN} of {PRECIP_WORD_PATTERN} in (?P<location>.+?){LOCATION_DATE_PATTERN}\??$",
            re.IGNORECASE,
        ),
        None,
    ),
]

INTERVAL_PRECIPITATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        rf"^Will (?P<location>.+?) (?:get|receive|see|record|have) between "
        rf"{INTERVAL_THRESHOLD_UNIT_PATTERN} of {PRECIP_WORD_PATTERN}{DATE_PATTERN}\??$",
        re.IGNORECASE,
    ),
    re.compile(
        rf"^Will there be between {INTERVAL_THRESHOLD_UNIT_PATTERN} of {PRECIP_WORD_PATTERN} "
        rf"in (?P<location>.+?){LOCATION_DATE_PATTERN}\??$",
        re.IGNORECASE,
    ),
]

TEMPERATURE_BUCKET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        rf"^(?:Will\s+)?(?:the\s+)?(?P<kind>highest|high|max|maximum|lowest|low|min|minimum) "
        rf"{TEMP_WORD_PATTERN} in (?P<location>.+?) on (?P<date>.+?) "
        rf"(?:be|to be)?\s*(?:between\s+)?{TEMP_RANGE_PATTERN}\??$",
        re.IGNORECASE,
    ),
    re.compile(
        rf"^(?:Will\s+)?(?P<location>.+?) "
        rf"(?:have|record|see|reach) (?:a\s+)?(?P<kind>high|highest|max|maximum|low|lowest|min|minimum) "
        rf"{TEMP_WORD_PATTERN} (?:of|between)\s+{TEMP_RANGE_PATTERN}(?:\s+on\s+(?P<date>.+?))?\??$",
        re.IGNORECASE,
    ),
]

TEMPERATURE_THRESHOLD_PATTERNS: list[tuple[re.Pattern[str], str | None]] = [
    (
        re.compile(
            rf"^(?:Will\s+)?(?:the\s+)?(?P<kind>highest|high|max|maximum|lowest|low|min|minimum) "
            rf"{TEMP_WORD_PATTERN} in (?P<location>.+?) on (?P<date>.+?) "
            rf"(?:be|to be)?\s*(?P<operator_phrase>at least|above|over|more than|greater than|or higher|no less than) "
            rf"{TEMP_SINGLE_PATTERN}\??$",
            re.IGNORECASE,
        ),
        ">=",
    ),
    (
        re.compile(
            rf"^(?:Will\s+)?(?:the\s+)?(?P<kind>highest|high|max|maximum|lowest|low|min|minimum) "
            rf"{TEMP_WORD_PATTERN} in (?P<location>.+?) on (?P<date>.+?) "
            rf"(?:be|to be)?\s*{TEMP_SINGLE_PATTERN}\s*(?:or higher|or more|and above)\??$",
            re.IGNORECASE,
        ),
        ">=",
    ),
    (
        re.compile(
            rf"^(?:Will\s+)?(?:the\s+)?(?P<kind>highest|high|max|maximum|lowest|low|min|minimum) "
            rf"{TEMP_WORD_PATTERN} in (?P<location>.+?) on (?P<date>.+?) "
            rf"(?:be|to be)?\s*{TEMP_SINGLE_PATTERN}\s*(?:or lower|or less|and below)\??$",
            re.IGNORECASE,
        ),
        "<=",
    ),
    (
        re.compile(
            rf"^(?:Will\s+)?(?:the\s+)?(?P<kind>highest|high|max|maximum|lowest|low|min|minimum) "
            rf"{TEMP_WORD_PATTERN} in (?P<location>.+?) on (?P<date>.+?) "
            rf"(?:be|to be)?\s*(?P<operator_phrase>at most|below|under|less than|no more than|or lower) "
            rf"{TEMP_SINGLE_PATTERN}\??$",
            re.IGNORECASE,
        ),
        "<=",
    ),
    (
        re.compile(
            rf"^(?:Will\s+)?(?:the\s+)?(?P<kind>highest|high|max|maximum|lowest|low|min|minimum) "
            rf"{TEMP_WORD_PATTERN} in (?P<location>.+?) on (?P<date>.+?) "
            rf"(?:be|to be)?\s*{TEMP_SINGLE_PATTERN}\??$",
            re.IGNORECASE,
        ),
        "=",
    ),
]


def _parse_target_window(
    date_text: str | None,
    reference_datetime: datetime | None = None,
) -> tuple[datetime | None, datetime | None]:
    if not date_text:
        return None, None

    normalized = date_text.strip().rstrip("?").lower()
    if normalized.startswith("in "):
        normalized = normalized[3:].strip()
    now = reference_datetime or datetime.now(timezone.utc)
    if normalized == "tomorrow":
        target_date = (now + timedelta(days=1)).date()
        start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
        end = datetime.combine(target_date, time.max, tzinfo=timezone.utc)
        return start, end

    for month_format in ("%B", "%b"):
        try:
            parsed_month = datetime.strptime(normalized.title(), month_format)
        except ValueError:
            continue
        year = now.year + 1 if parsed_month.month < now.month else now.year
        start = datetime(year, parsed_month.month, 1, tzinfo=timezone.utc)
        end_day = monthrange(year, parsed_month.month)[1]
        end = datetime.combine(start.date().replace(day=end_day), time.max, tzinfo=timezone.utc)
        return start, end

    parsed = None
    for date_format in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y", "%B %d", "%b %d"):
        try:
            parsed = datetime.strptime(normalized.title(), date_format)
            break
        except ValueError:
            continue
    if parsed is None:
        return None, None
    has_explicit_year = parsed.year != 1900
    target_date = parsed.date() if has_explicit_year else parsed.replace(year=now.year).date()
    if not has_explicit_year and target_date < now.date():
        target_date = target_date.replace(year=now.year + 1)

    start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(target_date, time.max, tzinfo=timezone.utc)
    return start, end


def _operator(match: re.Match[str], fallback: str | None) -> str:
    if fallback is not None:
        return fallback
    phrase = match.groupdict().get("operator_phrase")
    return OPERATOR_PHRASES.get(phrase.lower(), ">") if phrase else ">"


def _unsupported_reason(question: str) -> str:
    lowered = question.lower()
    precipitation_terms = ("rain", "precipitation", "precip")
    if any(term in lowered for term in ("temperature", "temp")):
        return (
            "Unsupported temperature question wording. Supported examples include "
            "'highest temperature in NYC on May 17 80-81F' and 'lowest temperature in London on May 17 10C or lower'."
        )
    if not any(term in lowered for term in precipitation_terms):
        return "Unsupported market question format: expected a precipitation threshold question."
    if not re.search(r"\d+(?:\.\d+)?", lowered):
        return "Unsupported precipitation question: missing numeric threshold."
    if not re.search(r"\b(inch|inches|in|mm|millimeter|millimeters)\b", lowered):
        return "Unsupported precipitation question: threshold unit must be inches or millimeters."
    if re.search(
        rf"\bbetween\s+\d+(?:\.\d+)?\s*(?:-|to|and)\s*\d+(?:\.\d+)?\s*{UNIT_PATTERN}\b",
        lowered,
    ):
        return "Unsupported precipitation interval contract: interval thresholds require interval probability modeling."
    return (
        "Unsupported precipitation question wording. Supported examples include "
        "'more than 1 inch of rain', 'at least 0.5 inches of rain', and '1 inch or more of rain'."
    )


def _temperature_kind(value: str) -> str:
    return "low" if value.lower() in {"lowest", "low", "min", "minimum"} else "high"


def _temperature_unit(value: str) -> str:
    normalized = value.strip().lower().replace("\u00b0", "")
    if normalized in {"f", "fahrenheit"}:
        return "F"
    if normalized in {"c", "celsius"}:
        return "C"
    return value


def _parse_temperature_market(
    question: str,
    reference_datetime: datetime | None = None,
) -> ParsedMarketResult | None:
    for pattern in TEMPERATURE_BUCKET_PATTERNS:
        match = pattern.search(question)
        if not match:
            continue
        lower_threshold = float(match.group("threshold"))
        upper_threshold = float(match.group("upper_threshold"))
        if upper_threshold <= lower_threshold:
            return ParsedMarketResult(
                success=False,
                parser_version=PARSER_VERSION,
                parse_confidence=0.0,
                error="Unsupported temperature bucket: upper threshold must exceed lower threshold.",
            )
        target_start, target_end = _parse_target_window(match.groupdict().get("date"), reference_datetime)
        return ParsedMarketResult(
            success=True,
            location_name=match.group("location").strip(),
            metric="temperature",
            operator="between",
            threshold_value=lower_threshold,
            interval_upper_value=upper_threshold,
            threshold_unit=_temperature_unit(match.group("unit")),
            target_start=target_start,
            target_end=target_end,
            parser_version=PARSER_VERSION,
            parse_confidence=0.8,
            raw_parse_json={"temperature_kind": _temperature_kind(match.group("kind"))},
        )

    for pattern, operator in TEMPERATURE_THRESHOLD_PATTERNS:
        match = pattern.search(question)
        if not match:
            continue
        target_start, target_end = _parse_target_window(match.groupdict().get("date"), reference_datetime)
        return ParsedMarketResult(
            success=True,
            location_name=match.group("location").strip(),
            metric="temperature",
            operator=operator or "=",
            threshold_value=float(match.group("threshold")),
            threshold_unit=_temperature_unit(match.group("unit")),
            target_start=target_start,
            target_end=target_end,
            parser_version=PARSER_VERSION,
            parse_confidence=0.75,
            raw_parse_json={"temperature_kind": _temperature_kind(match.group("kind"))},
        )
    return None


def parse_precipitation_market(
    question: str,
    reference_datetime: datetime | None = None,
    allow_interval_contracts: bool = False,
) -> ParsedMarketResult:
    """Parse simple weather market questions using regex.

    The public API name is retained for compatibility with older route and
    runner code, but the parser now also handles temperature bucket markets.
    """
    normalized_question = question.strip()

    temperature_result = _parse_temperature_market(normalized_question, reference_datetime)
    if temperature_result is not None:
        return temperature_result

    if allow_interval_contracts:
        for pattern in INTERVAL_PRECIPITATION_PATTERNS:
            match = pattern.search(normalized_question)
            if not match:
                continue

            lower_threshold = float(match.group("threshold"))
            upper_threshold = float(match.group("upper_threshold"))
            if upper_threshold <= lower_threshold:
                break
            location_name = match.group("location").strip()
            target_start, target_end = _parse_target_window(match.groupdict().get("date"), reference_datetime)
            return ParsedMarketResult(
                success=True,
                location_name=location_name,
                metric="precipitation",
                operator="between",
                threshold_value=lower_threshold,
                interval_upper_value=upper_threshold,
                threshold_unit=match.group("unit").lower(),
                target_start=target_start,
                target_end=target_end,
                parser_version=PRECIP_PARSER_VERSION,
                parse_confidence=0.75,
            )

    for pattern, fallback_operator in PRECIPITATION_PATTERNS:
        match = pattern.search(normalized_question)
        if not match:
            continue

        operator = _operator(match, fallback_operator)
        location_name = match.group("location").strip()
        target_start, target_end = _parse_target_window(match.groupdict().get("date"), reference_datetime)
        return ParsedMarketResult(
            success=True,
            location_name=location_name,
            metric="precipitation",
            operator=operator,
            threshold_value=float(match.group("threshold")),
            threshold_unit=match.group("unit").lower(),
            target_start=target_start,
            target_end=target_end,
            parser_version=PRECIP_PARSER_VERSION,
            parse_confidence=0.85,
        )

    return ParsedMarketResult(
        success=False,
        parser_version=PRECIP_PARSER_VERSION,
        parse_confidence=0.0,
        error=_unsupported_reason(normalized_question),
    )
