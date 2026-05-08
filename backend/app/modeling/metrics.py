def brier_score(probability: float, outcome: int) -> float:
    if not 0 <= probability <= 1:
        raise ValueError("probability must be between 0 and 1")
    if outcome not in (0, 1):
        raise ValueError("outcome must be 0 or 1")
    return (probability - outcome) ** 2

