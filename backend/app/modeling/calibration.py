from dataclasses import dataclass


DEFAULT_BUCKETS = (
    (0.0, 0.2),
    (0.2, 0.4),
    (0.4, 0.6),
    (0.6, 0.8),
    (0.8, 1.0),
)


@dataclass(frozen=True)
class CalibrationBucketResult:
    lower_bound: float
    upper_bound: float
    count: int
    average_predicted_probability: float | None
    observed_yes_rate: float | None
    calibration_gap: float | None


def _bucket_index(probability: float, buckets: tuple[tuple[float, float], ...]) -> int:
    if not 0 <= probability <= 1:
        raise ValueError("probability must be between 0 and 1")

    for index, (lower, upper) in enumerate(buckets):
        if lower <= probability < upper:
            return index
    return len(buckets) - 1


def calibration_summary(
    probability_outcomes: list[tuple[float, int]],
    buckets: tuple[tuple[float, float], ...] = DEFAULT_BUCKETS,
) -> list[CalibrationBucketResult]:
    grouped: list[list[tuple[float, int]]] = [[] for _ in buckets]
    for probability, outcome in probability_outcomes:
        if outcome not in (0, 1):
            raise ValueError("outcome must be 0 or 1")
        grouped[_bucket_index(probability, buckets)].append((probability, outcome))

    results: list[CalibrationBucketResult] = []
    for (lower, upper), values in zip(buckets, grouped):
        if not values:
            results.append(
                CalibrationBucketResult(
                    lower_bound=lower,
                    upper_bound=upper,
                    count=0,
                    average_predicted_probability=None,
                    observed_yes_rate=None,
                    calibration_gap=None,
                )
            )
            continue

        average_probability = sum(probability for probability, _ in values) / len(values)
        observed_yes_rate = sum(outcome for _, outcome in values) / len(values)
        results.append(
            CalibrationBucketResult(
                lower_bound=lower,
                upper_bound=upper,
                count=len(values),
                average_predicted_probability=round(average_probability, 6),
                observed_yes_rate=round(observed_yes_rate, 6),
                calibration_gap=round(observed_yes_rate - average_probability, 6),
            )
        )
    return results
