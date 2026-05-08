"""Strategy API routes.

These endpoints turn stored model predictions and market price snapshots into
expected-value recommendations. Responses expose the input record IDs so a
paper-trading decision can be traced back to the exact prediction, parsed
market, forecast snapshot, and price snapshot used.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EVRecommendation, Market, Prediction
from app.db.repositories import latest_prediction, latest_price_snapshot
from app.db.session import get_db
from app.strategy.ev import evaluate_market_edge
from app.strategy.schemas import OpportunityRead, StrategyEvaluationRead


router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.post("/evaluate/{market_id}", response_model=StrategyEvaluationRead)
def evaluate_strategy(market_id: int, db: Session = Depends(get_db)) -> StrategyEvaluationRead:
    prediction = latest_prediction(db, market_id)
    if prediction is None:
        raise HTTPException(status_code=409, detail="Prediction required before strategy evaluation")

    price_snapshot = latest_price_snapshot(db, market_id)
    if price_snapshot is None:
        raise HTTPException(status_code=409, detail="Market price snapshot required before strategy evaluation")

    result = evaluate_market_edge(prediction, price_snapshot)
    recommendation = EVRecommendation(
        prediction_id=prediction.id,
        price_snapshot_id=price_snapshot.id,
        market_price_yes=result.market_price_yes,
        market_price_no=result.market_price_no,
        edge_yes=result.edge_yes,
        edge_no=result.edge_no,
        ev_yes=result.ev_yes,
        ev_no=result.ev_no,
        recommendation=result.recommendation,
        paper_position_size=result.paper_position_size,
        reason=result.reason,
    )
    db.add(recommendation)
    db.commit()
    db.refresh(recommendation)

    data = recommendation.__dict__.copy()
    data["market_id"] = market_id
    data["parsed_market_id"] = prediction.parsed_market_id
    data["forecast_snapshot_id"] = prediction.forecast_snapshot_id
    data["model_probability_yes"] = prediction.p_yes
    return StrategyEvaluationRead.model_validate(data)


@router.get("/opportunities", response_model=list[OpportunityRead])
def list_opportunities(
    min_edge: float = Query(default=0.03, ge=0, le=1),
    limit: int = Query(default=20, gt=0, le=100),
    db: Session = Depends(get_db),
) -> list[OpportunityRead]:
    rows = db.execute(
        select(EVRecommendation, Prediction, Market)
        .join(Prediction, EVRecommendation.prediction_id == Prediction.id)
        .join(Market, Prediction.market_id == Market.id)
        .where(EVRecommendation.recommendation.in_(["PAPER_BUY_YES", "PAPER_BUY_NO"]))
        .where((EVRecommendation.edge_yes >= min_edge) | (EVRecommendation.edge_no >= min_edge))
        .order_by(EVRecommendation.created_at.desc())
        .limit(limit)
    ).all()

    return [
        OpportunityRead(
            market_id=market.id,
            prediction_id=prediction.id,
            price_snapshot_id=recommendation.price_snapshot_id,
            question=market.question,
            model_probability_yes=prediction.p_yes,
            market_price_yes=recommendation.market_price_yes,
            edge_yes=recommendation.edge_yes,
            recommendation=recommendation.recommendation,
            created_at=recommendation.created_at,
        )
        for recommendation, prediction, market in rows
    ]
