"""Paper-mode risk sizing helpers.

The sizing policy is intentionally simple: it turns model edge into a simulated
paper position for research and demos. It is not live-execution risk control.
"""


def calculate_paper_position_size(edge: float, max_size: float = 10.0) -> float:
    """Scale positive probability edge into a capped paper position size."""
    if max_size < 0:
        raise ValueError("max_size must be non-negative")
    if edge <= 0 or max_size == 0:
        return 0.0
    return min(max_size, round(edge * 100, 2))
