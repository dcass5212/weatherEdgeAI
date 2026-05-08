from app.db.models import EVRecommendation, PaperTrade, utc_now


OPEN_STATUSES = {"OPEN", "CLOSED", "CANCELLED", "RESOLVED"}


def create_paper_trade_from_recommendation(recommendation: EVRecommendation, quantity: float) -> PaperTrade:
    if quantity <= 0:
        raise ValueError("quantity must be greater than 0")
    if recommendation.recommendation not in {"PAPER_BUY_YES", "PAPER_BUY_NO"}:
        raise ValueError("recommendation is not a paper buy signal")

    side = "YES" if recommendation.recommendation == "PAPER_BUY_YES" else "NO"
    entry_price = recommendation.market_price_yes if side == "YES" else recommendation.market_price_no
    if entry_price is None:
        raise ValueError("recommendation is missing an entry price")

    return PaperTrade(
        market_id=recommendation.prediction.market_id,
        recommendation_id=recommendation.id,
        side=side,
        entry_price=entry_price,
        quantity=quantity,
        entry_time=utc_now(),
        status="OPEN",
    )


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
