import pytest

from app.modeling.calibration import calibration_summary


def test_calibration_summary_buckets_probability_outcomes() -> None:
    buckets = calibration_summary([(0.15, 0), (0.45, 1), (0.55, 0), (1.0, 1)])

    assert len(buckets) == 5
    assert buckets[0].count == 1
    assert buckets[0].average_predicted_probability == 0.15
    assert buckets[0].observed_yes_rate == 0.0
    assert buckets[0].calibration_gap == -0.15
    assert buckets[2].count == 2
    assert buckets[2].average_predicted_probability == 0.5
    assert buckets[2].observed_yes_rate == 0.5
    assert buckets[4].count == 1
    assert buckets[4].average_predicted_probability == 1.0
    assert buckets[4].observed_yes_rate == 1.0


def test_calibration_summary_rejects_invalid_probability() -> None:
    with pytest.raises(ValueError, match="probability must be between 0 and 1"):
        calibration_summary([(1.1, 1)])
