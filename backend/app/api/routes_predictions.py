from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Prediction
from app.db.repositories import get_market, latest_forecast_snapshot, latest_parsed_market, latest_prediction
from app.db.session import get_db
from app.modeling.model_registry import DEFAULT_MODEL_VERSION, available_model_versions, run_prediction_model
from app.modeling.schemas import PredictionRead


router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post("/run/{market_id}", response_model=PredictionRead)
def run_prediction(
    market_id: int,
    model_version: str = Query(default=DEFAULT_MODEL_VERSION),
    db: Session = Depends(get_db),
) -> Prediction:
    market = get_market(db, market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")

    parsed_market = latest_parsed_market(db, market_id)
    if parsed_market is None:
        raise HTTPException(status_code=409, detail="Market must be parsed before prediction")

    forecast = latest_forecast_snapshot(db, parsed_market.id)
    if forecast is None:
        raise HTTPException(status_code=409, detail="Forecast snapshot required before prediction")

    try:
        result = run_prediction_model(parsed_market, forecast, model_version=model_version)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(exc),
                "supported_model_versions": list(available_model_versions()),
            },
        ) from exc
    prediction = Prediction(
        market_id=market.id,
        parsed_market_id=parsed_market.id,
        forecast_snapshot_id=forecast.id,
        model_version=result.model_version,
        p_yes=result.p_yes,
        p_no=result.p_no,
        confidence=result.confidence,
        features_json=result.features_json,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


@router.get("/{market_id}", response_model=list[PredictionRead])
def list_predictions(market_id: int, limit: int = Query(default=20, gt=0, le=100), db: Session = Depends(get_db)) -> list[Prediction]:
    return list(
        db.scalars(
            select(Prediction).where(Prediction.market_id == market_id).order_by(Prediction.created_at.desc()).limit(limit)
        )
    )


@router.get("/{market_id}/latest", response_model=PredictionRead)
def get_latest_prediction(market_id: int, db: Session = Depends(get_db)) -> Prediction:
    prediction = latest_prediction(db, market_id)
    if prediction is None:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return prediction
