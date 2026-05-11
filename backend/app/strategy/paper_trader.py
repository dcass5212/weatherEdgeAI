from typing import Any

from app.db.models import EVRecommendation, PaperTrade, ResolvedOutcome, utc_now


OPEN_STATUS = "OPEN"


def create_paper_trade_from_recommendation(
    recommendation: EVRecommendation,
    quantity: float,
    *,
    runner_config: dict[str, Any] | None = None,
    entry_slippage_rate: float = 0.0,
) -> PaperTrade:
    if quantity <= 0:
        raise ValueError("quantity must be greater than 0")
    if recommendation.recommendation not in {"PAPER_BUY_YES", "PAPER_BUY_NO"}:
        raise ValueError("recommendation is not a paper buy signal")

    side = "YES" if recommendation.recommendation == "PAPER_BUY_YES" else "NO"
    entry_price = recommendation.market_price_yes if side == "YES" else recommendation.market_price_no
    if entry_price is None:
        raise ValueError("recommendation is missing an entry price")
    if entry_slippage_rate < 0:
        raise ValueError("entry_slippage_rate cannot be negative")
    quoted_entry_price = entry_price
    fill_entry_price = min(quoted_entry_price + entry_slippage_rate, 1.0)

    trade = PaperTrade(
        market_id=recommendation.prediction.market_id,
        recommendation_id=recommendation.id,
        side=side,
        entry_price=fill_entry_price,
        quantity=quantity,
        entry_time=utc_now(),
        status="OPEN",
    )
    trade.signal_snapshot_json = build_paper_trade_signal_snapshot(
        recommendation,
        side,
        quantity,
        runner_config,
        quoted_entry_price=quoted_entry_price,
        fill_entry_price=fill_entry_price,
        entry_slippage_rate=entry_slippage_rate,
    )
    return trade


def build_paper_trade_signal_snapshot(
    recommendation: EVRecommendation,
    side: str,
    quantity: float,
    runner_config: dict[str, Any] | None = None,
    *,
    quoted_entry_price: float | None = None,
    fill_entry_price: float | None = None,
    entry_slippage_rate: float = 0.0,
) -> dict[str, Any]:
    prediction = recommendation.prediction
    parsed_market = prediction.parsed_market
    forecast = prediction.forecast_snapshot
    price_snapshot = recommendation.price_snapshot
    market = prediction.market

    snapshot: dict[str, Any] = {
        "market": {
            "id": market.id if market is not None else prediction.market_id,
            "question": market.question if market is not None else None,
            "source": market.source if market is not None else None,
            "source_market_id": market.source_market_id if market is not None else None,
        },
        "paper_trade": {
            "side": side,
            "quantity": quantity,
            "quoted_entry_price": quoted_entry_price,
            "fill_entry_price": fill_entry_price,
            "entry_slippage_rate": entry_slippage_rate,
            "entry_slippage_cost": (
                round((fill_entry_price - quoted_entry_price) * quantity, 10)
                if fill_entry_price is not None and quoted_entry_price is not None
                else None
            ),
        },
        "recommendation": {
            "id": recommendation.id,
            "recommendation": recommendation.recommendation,
            "reason": recommendation.reason,
            "paper_position_size": recommendation.paper_position_size,
        },
        "prediction": {
            "id": prediction.id,
            "model_version": prediction.model_version,
            "p_yes": prediction.p_yes,
            "p_no": prediction.p_no,
            "confidence": prediction.confidence,
        },
        "market_price": {
            "price_snapshot_id": recommendation.price_snapshot_id,
            "yes_price": recommendation.market_price_yes,
            "no_price": recommendation.market_price_no,
            "edge_yes": recommendation.edge_yes,
            "edge_no": recommendation.edge_no,
            "ev_yes": recommendation.ev_yes,
            "ev_no": recommendation.ev_no,
            "liquidity": price_snapshot.liquidity if price_snapshot is not None else None,
            "spread": price_snapshot.spread if price_snapshot is not None else None,
            "timestamp": price_snapshot.timestamp.isoformat() if price_snapshot is not None else None,
        },
        "parsed_target": None,
        "forecast": None,
        "runner_config": runner_config,
    }
    if parsed_market is not None:
        snapshot["parsed_target"] = {
            "parsed_market_id": parsed_market.id,
            "location_name": parsed_market.location_name,
            "metric": parsed_market.metric,
            "operator": parsed_market.operator,
            "threshold_value": parsed_market.threshold_value,
            "threshold_unit": parsed_market.threshold_unit,
            "target_start": parsed_market.target_start.isoformat() if parsed_market.target_start is not None else None,
            "target_end": parsed_market.target_end.isoformat() if parsed_market.target_end is not None else None,
        }
    if forecast is not None:
        snapshot["forecast"] = {
            "forecast_snapshot_id": forecast.id,
            "forecast_source": forecast.forecast_source,
            "forecast_timestamp": forecast.forecast_timestamp.isoformat(),
            "forecast_precip_total": forecast.forecast_precip_total,
            "forecast_precip_unit": forecast.forecast_precip_unit,
        }
    return snapshot


def close_paper_trade(trade: PaperTrade, exit_price: float) -> PaperTrade:
    if not 0 <= exit_price <= 1:
        raise ValueError("exit_price must be between 0 and 1")
    if trade.status != "OPEN":
        raise ValueError("only OPEN paper trades can be closed")

    multiplier = 1 if trade.side == "YES" else -1
    trade.exit_price = exit_price
    trade.exit_time = utc_now()
    trade.pnl = (exit_price - trade.entry_price) * trade.quantity * multiplier
    trade.status = "CLOSED"
    return trade


def settlement_price_for_outcome(side: str, actual_outcome: str) -> float:
    normalized_side = side.upper()
    normalized_outcome = actual_outcome.upper()
    if normalized_side not in {"YES", "NO"}:
        raise ValueError("paper trade side must be YES or NO")
    if normalized_outcome not in {"YES", "NO"}:
        raise ValueError("actual_outcome must be YES or NO")
    return 1.0 if normalized_side == normalized_outcome else 0.0


def settle_paper_trade_from_outcome(trade: PaperTrade, outcome: ResolvedOutcome) -> PaperTrade:
    if trade.status != OPEN_STATUS:
        raise ValueError("only OPEN paper trades can be settled")

    exit_price = settlement_price_for_outcome(trade.side, outcome.actual_outcome)
    trade.exit_price = exit_price
    trade.exit_time = outcome.resolved_at or utc_now()
    trade.pnl = (exit_price - trade.entry_price) * trade.quantity
    trade.status = "RESOLVED"
    return trade
