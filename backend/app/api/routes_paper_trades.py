from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import EVRecommendation, PaperTrade
from app.db.repositories import list_paper_trades
from app.db.session import get_db
from app.strategy.paper_trader import close_paper_trade, create_paper_trade_from_recommendation
from app.strategy.schemas import PaperTradeClose, PaperTradeCreate, PaperTradeRead


router = APIRouter(prefix="/paper-trades", tags=["paper-trades"])


@router.post("", response_model=PaperTradeRead, status_code=201)
def create_paper_trade(payload: PaperTradeCreate, db: Session = Depends(get_db)) -> PaperTrade:
    recommendation = db.get(EVRecommendation, payload.recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=404, detail="EV recommendation not found")

    try:
        trade = create_paper_trade_from_recommendation(recommendation, payload.quantity)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


@router.get("", response_model=list[PaperTradeRead])
def get_paper_trades(
    status: str | None = None,
    limit: int = Query(default=50, gt=0, le=200),
    db: Session = Depends(get_db),
) -> list[PaperTrade]:
    return list_paper_trades(db, status=status, limit=limit)


@router.post("/{paper_trade_id}/close", response_model=PaperTradeRead)
def close_trade(paper_trade_id: int, payload: PaperTradeClose, db: Session = Depends(get_db)) -> PaperTrade:
    trade = db.get(PaperTrade, paper_trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Paper trade not found")

    try:
        close_paper_trade(trade, payload.exit_price)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    db.commit()
    db.refresh(trade)
    return trade
