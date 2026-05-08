import pytest

from app.strategy.ev import calculate_binary_yes_edge, calculate_binary_yes_ev


def test_calculate_binary_yes_edge() -> None:
    assert calculate_binary_yes_edge(0.61, 0.44) == pytest.approx(0.17)


def test_calculate_binary_yes_ev() -> None:
    assert calculate_binary_yes_ev(0.65, 0.50) == pytest.approx(0.15)


@pytest.mark.parametrize("model_probability_yes,market_price_yes", [(-0.1, 0.5), (1.1, 0.5), (0.5, -0.1), (0.5, 1.1)])
def test_ev_inputs_must_be_probabilities(model_probability_yes: float, market_price_yes: float) -> None:
    with pytest.raises(ValueError):
        calculate_binary_yes_edge(model_probability_yes, market_price_yes)
