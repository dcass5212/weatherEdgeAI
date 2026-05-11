"""Rule-based weather market parser.

V1 keeps parsing explicit and testable for precipitation threshold markets.
The parser favors narrow, explainable coverage over broad guesses because its
outputs drive forecast requests, probability modeling, and paper-trading EV.
"""

import re
from calendar import monthrange
from datetime import datetime, time, timedelta, timezone

from app.markets.schemas import ParsedMarketResult


PARSER_VERSION = "regex_precip_v1"

THRESHOLD_PATTERN = r"(?P<threshold>\d+(?:\.\d+)?)"
UPPER_THRESHOLD_PATTERN = r"(?P<upper_threshold>\d+(?:\.\d+)?)"
UNIT_PATTERN = r"(?P<unit>inch|inches|in|mm|millimeter|millimeters)"
THRESHOLD_UNIT_PATTERN = rf"{THRESHOLD_PATTERN}\s*{UNIT_PATTERN}"
INTERVAL_THRESHOLD_UNIT_PATTERN = rf"{THRESHOLD_PATTERN}\s*(?:-|to|and)\s*{UPPER_THRESHOLD_PATTERN}\s*{UNIT_PATTERN}"
PRECIP_WORD_PATTERN = r"(?:rain|precipitation|precip)"
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


def parse_precipitation_market(
    question: str,
    reference_datetime: datetime | None = None,
    allow_interval_contracts: bool = False,
) -> ParsedMarketResult:
    """Parse simple precipitation threshold market questions using regex."""
    normalized_question = question.strip()

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
                parser_version=PARSER_VERSION,
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
            parser_version=PARSER_VERSION,
            parse_confidence=0.85,
        )

    return ParsedMarketResult(
        success=False,
        parser_version=PARSER_VERSION,
        parse_confidence=0.0,
        error=_unsupported_reason(normalized_question),
    )
