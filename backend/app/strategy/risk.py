def calculate_paper_position_size(edge: float, max_size: float = 10.0) -> float:
    if max_size < 0:
        raise ValueError("max_size must be non-negative")
    if edge <= 0:
        return 0.0
    return min(max_size, edge * max_size)

