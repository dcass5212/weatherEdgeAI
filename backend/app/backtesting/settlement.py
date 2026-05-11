"""Paper-trade settlement from resolved outcomes.

This module closes the research loop after observed weather outcomes arrive.
It only mutates simulated paper trades and never touches live execution state.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaperTrade, ResolvedOutcome
from app.strategy.paper_trader import settle_paper_trade_from_outcome


@dataclass(frozen=True)
class SettlementSummary:
    market_id: int
    outcome_id: int
    settled_trade_ids: list[int]

    @property
    def settled_count(self) -> int:
        return len(self.settled_trade_ids)


def settle_open_paper_trades_for_outcome(db: Session, outcome: ResolvedOutcome) -> SettlementSummary:
    trades = list(
        db.scalars(
            select(PaperTrade)
            .where(PaperTrade.market_id == outcome.market_id)
            .where(PaperTrade.status == "OPEN")
            .order_by(PaperTrade.entry_time.asc(), PaperTrade.id.asc())
        )
    )
    settled_ids: list[int] = []
    for trade in trades:
        settle_paper_trade_from_outcome(trade, outcome)
        settled_ids.append(trade.id)

    return SettlementSummary(
        market_id=outcome.market_id,
        outcome_id=outcome.id,
        settled_trade_ids=settled_ids,
    )
