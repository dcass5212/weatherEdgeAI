from fastapi import APIRouter, Depends, HTTPException, Query
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtesting.backtest_runner import BacktestRunner
from app.backtesting.outcome_resolver import resolve_weather_outcome_for_parsed_market
from app.backtesting.schemas import (
    BacktestRunRequest,
    BacktestRunResponse,
    ResolvedOutcomeCreate,
    ResolvedOutcomeRead,
    WeatherOutcomeResolveRequest,
)
from app.db.models import ResolvedOutcome
from app.db.repositories import get_market, latest_parsed_market
from app.db.session import get_db


router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("/run", response_model=BacktestRunResponse)
def run_backtest(payload: BacktestRunRequest, db: Session = Depends(get_db)) -> BacktestRunResponse:
    try:
        return BacktestRunner(db).run(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/resolved-outcomes", response_model=ResolvedOutcomeRead, status_code=201)
def create_resolved_outcome(payload: ResolvedOutcomeCreate, db: Session = Depends(get_db)) -> ResolvedOutcome:
    market = get_market(db, payload.market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")

    outcome = ResolvedOutcome(**payload.model_dump())
    db.add(outcome)
    db.commit()
    db.refresh(outcome)
    return outcome


@router.post("/resolved-outcomes/resolve-weather", response_model=ResolvedOutcomeRead, status_code=201)
async def resolve_weather_outcome(
    payload: WeatherOutcomeResolveRequest,
    db: Session = Depends(get_db),
) -> ResolvedOutcome:
    market = get_market(db, payload.market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")

    parsed_market = latest_parsed_market(db, payload.market_id)
    if parsed_market is None:
        raise HTTPException(status_code=409, detail="Market must be parsed before observed weather can be resolved")

    try:
        outcome = await resolve_weather_outcome_for_parsed_market(parsed_market)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Open-Meteo archive request failed: {exc}") from exc

    db.add(outcome)
    db.commit()
    db.refresh(outcome)
    return outcome


@router.get("/resolved-outcomes", response_model=list[ResolvedOutcomeRead])
def list_resolved_outcomes(
    market_id: int | None = None,
    limit: int = Query(default=50, gt=0, le=200),
    db: Session = Depends(get_db),
) -> list[ResolvedOutcome]:
    statement = select(ResolvedOutcome).order_by(ResolvedOutcome.created_at.desc()).limit(limit)
    if market_id is not None:
        statement = statement.where(ResolvedOutcome.market_id == market_id)
    return list(db.scalars(statement))
