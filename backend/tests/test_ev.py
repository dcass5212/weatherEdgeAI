import pytest

from app.db.models import MarketPriceSnapshot, Prediction
from app.strategy.ev import calculate_binary_yes_edge, calculate_binary_yes_ev
from app.strategy.ev import evaluate_market_edge
from app.strategy.risk import calculate_paper_position_size


def test_calculate_binary_yes_edge() -> None:
    assert calculate_binary_yes_edge(0.61, 0.44) == pytest.approx(0.17)


def test_calculate_binary_yes_ev() -> None:
    assert calculate_binary_yes_ev(0.65, 0.50) == pytest.approx(0.15)


@pytest.mark.parametrize("model_probability_yes,market_price_yes", [(-0.1, 0.5), (1.1, 0.5), (0.5, -0.1), (0.5, 1.1)])
def test_ev_inputs_must_be_probabilities(model_probability_yes: float, market_price_yes: float) -> None:
    with pytest.raises(ValueError):
        calculate_binary_yes_edge(model_probability_yes, market_price_yes)


@pytest.mark.parametrize(
    "edge,max_size,expected",
    [
        (-0.05, 10.0, 0.0),
        (0.0, 10.0, 0.0),
        (0.025, 10.0, 2.5),
        (0.03125, 10.0, 3.12),
        (0.31, 10.0, 10.0),
        (0.31, 5.0, 5.0),
        (0.31, 0.0, 0.0),
    ],
)
def test_calculate_paper_position_size_scales_positive_edge_and_caps_size(
    edge: float,
    max_size: float,
    expected: float,
) -> None:
    assert calculate_paper_position_size(edge, max_size=max_size) == pytest.approx(expected)


def test_calculate_paper_position_size_rejects_negative_max_size() -> None:
    with pytest.raises(ValueError, match="max_size must be non-negative"):
        calculate_paper_position_size(0.1, max_size=-1.0)


def test_evaluate_market_edge_uses_capped_paper_size_for_yes_edge() -> None:
    prediction = Prediction(p_yes=0.75, p_no=0.25)
    price_snapshot = MarketPriceSnapshot(yes_price=0.44, no_price=0.56)

    result = evaluate_market_edge(prediction, price_snapshot)

    assert result.recommendation == "PAPER_BUY_YES"
    assert result.edge_yes == pytest.approx(0.31)
    assert result.paper_position_size == pytest.approx(10.0)
    assert "paper size is 10.00 with a 10.00 max" in result.reason


def test_evaluate_market_edge_uses_capped_paper_size_for_no_edge() -> None:
    prediction = Prediction(p_yes=0.25, p_no=0.75)
    price_snapshot = MarketPriceSnapshot(yes_price=0.56, no_price=0.44)

    result = evaluate_market_edge(prediction, price_snapshot)

    assert result.recommendation == "PAPER_BUY_NO"
    assert result.edge_no == pytest.approx(0.31)
    assert result.paper_position_size == pytest.approx(10.0)
    assert "paper size is 10.00 with a 10.00 max" in result.reason


def test_evaluate_market_edge_leaves_size_empty_when_edge_is_not_actionable() -> None:
    prediction = Prediction(p_yes=0.51, p_no=0.49)
    price_snapshot = MarketPriceSnapshot(yes_price=0.50, no_price=0.50)

    result = evaluate_market_edge(prediction, price_snapshot)

    assert result.recommendation == "AVOID"
    assert result.paper_position_size is None
