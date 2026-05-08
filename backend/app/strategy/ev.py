from dataclasses import dataclass

from app.db.models import MarketPriceSnapshot, Prediction


RECOMMENDATIONS = {"AVOID", "WATCH", "PAPER_BUY_YES", "PAPER_BUY_NO"}
DEFAULT_EDGE_THRESHOLD = 0.03


@dataclass(frozen=True)
class EVRecommendationResult:
    market_price_yes: float | None
    market_price_no: float | None
    edge_yes: float | None
    edge_no: float | None
    ev_yes: float | None
    ev_no: float | None
    recommendation: str
    paper_position_size: float | None
    reason: str


def _validate_probability(name: str, value: float) -> None:
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be between 0 and 1")


def calculate_binary_yes_edge(model_probability_yes: float, market_price_yes: float) -> float:
    _validate_probability("model_probability_yes", model_probability_yes)
    _validate_probability("market_price_yes", market_price_yes)
    return model_probability_yes - market_price_yes


def calculate_binary_yes_ev(model_probability_yes: float, market_price_yes: float) -> float:
    _validate_probability("model_probability_yes", model_probability_yes)
    _validate_probability("market_price_yes", market_price_yes)
    return model_probability_yes * (1 - market_price_yes) - (1 - model_probability_yes) * market_price_yes


def evaluate_market_edge(
    prediction: Prediction,
    price_snapshot: MarketPriceSnapshot,
    edge_threshold: float = DEFAULT_EDGE_THRESHOLD,
) -> EVRecommendationResult:
    _validate_probability("p_yes", prediction.p_yes)
    _validate_probability("p_no", prediction.p_no)
    if price_snapshot.yes_price is None:
        return EVRecommendationResult(None, None, None, None, None, None, "WATCH", None, "Missing YES market price.")

    yes_price = price_snapshot.yes_price
    no_price = price_snapshot.no_price if price_snapshot.no_price is not None else round(1 - yes_price, 10)
    _validate_probability("yes_price", yes_price)
    _validate_probability("no_price", no_price)

    edge_yes = prediction.p_yes - yes_price
    edge_no = prediction.p_no - no_price
    ev_yes = calculate_binary_yes_ev(prediction.p_yes, yes_price)
    ev_no = calculate_binary_yes_ev(prediction.p_no, no_price)

    if max(edge_yes, edge_no) < edge_threshold:
        recommendation = "AVOID"
        reason = "No edge exceeds the configured threshold."
        paper_position_size = None
    elif edge_yes >= edge_no and edge_yes >= edge_threshold:
        recommendation = "PAPER_BUY_YES"
        reason = f"Model probability exceeds market-implied probability by {edge_yes:.0%}."
        paper_position_size = min(10.0, round(edge_yes * 100, 2))
    elif edge_no > edge_yes and edge_no >= edge_threshold:
        recommendation = "PAPER_BUY_NO"
        reason = f"Model NO probability exceeds market-implied probability by {edge_no:.0%}."
        paper_position_size = min(10.0, round(edge_no * 100, 2))
    else:
        recommendation = "WATCH"
        reason = "Edge is near threshold but not actionable."
        paper_position_size = None

    return EVRecommendationResult(
        market_price_yes=yes_price,
        market_price_no=no_price,
        edge_yes=edge_yes,
        edge_no=edge_no,
        ev_yes=ev_yes,
        ev_no=ev_no,
        recommendation=recommendation,
        paper_position_size=paper_position_size,
        reason=reason,
    )
