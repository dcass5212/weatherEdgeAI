from fastapi import APIRouter, Depends, HTTPException, Query
import httpx
from datetime import datetime, timezone
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.backtesting.backtest_runner import BacktestRunner
from app.backtesting.outcome_resolver import resolve_weather_outcome_for_parsed_market
from app.backtesting.settlement import settle_open_paper_trades_for_outcome
from app.backtesting.schemas import (
    BacktestRunRequest,
    BacktestRunResponse,
    OutcomeEligibilityPreviewItem,
    OutcomeEligibilityPreviewResponse,
    ResolvedOutcomeCreate,
    ResolvedOutcomeRead,
    WeatherOutcomeBatchItem,
    WeatherOutcomeBatchResolveRequest,
    WeatherOutcomeBatchResolveResponse,
    WeatherOutcomeResolveRequest,
)
from app.db.models import Market, ParsedMarket, ResolvedOutcome, utc_now
from app.db.repositories import get_market, latest_parsed_market
from app.db.session import get_db


router = APIRouter(prefix="/backtests", tags=["backtests"])


def _latest_outcome_for_provider(
    db: Session,
    market_id: int,
    resolution_provider: str,
) -> ResolvedOutcome | None:
    return db.scalars(
        select(ResolvedOutcome)
        .where(ResolvedOutcome.market_id == market_id)
        .where(ResolvedOutcome.resolution_source == resolution_provider)
        .order_by(ResolvedOutcome.resolved_at.desc().nullslast(), ResolvedOutcome.id.desc())
        .limit(1)
    ).first()


def _completed_target_filter(now):
    return or_(
        and_(ParsedMarket.target_end.is_(None), ParsedMarket.target_start <= now),
        ParsedMarket.target_end <= now,
    )


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
    db.flush()
    settle_open_paper_trades_for_outcome(db, outcome)
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
        outcome = await resolve_weather_outcome_for_parsed_market(
            parsed_market,
            provider=payload.resolution_provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"{payload.resolution_provider} observed-weather request failed: {exc}",
        ) from exc

    db.add(outcome)
    db.flush()
    if payload.settle_open_trades:
        settle_open_paper_trades_for_outcome(db, outcome)
    db.commit()
    db.refresh(outcome)
    return outcome


@router.post("/resolved-outcomes/resolve-weather-batch", response_model=WeatherOutcomeBatchResolveResponse)
async def resolve_weather_outcomes_batch(
    payload: WeatherOutcomeBatchResolveRequest,
    db: Session = Depends(get_db),
) -> WeatherOutcomeBatchResolveResponse:
    now = utc_now()
    parsed_markets = list(
        db.scalars(
            select(ParsedMarket)
            .where(ParsedMarket.latitude.is_not(None))
            .where(ParsedMarket.longitude.is_not(None))
            .where(ParsedMarket.target_start.is_not(None))
            .where(_completed_target_filter(now))
            .order_by(ParsedMarket.created_at.desc(), ParsedMarket.id.desc())
            .limit(payload.limit)
        )
    )

    results: list[WeatherOutcomeBatchItem] = []
    resolved = 0
    skipped = 0
    errors = 0
    settled_trades = 0
    seen_market_ids: set[int] = set()
    for parsed_market in parsed_markets:
        if parsed_market.market_id in seen_market_ids:
            skipped += 1
            results.append(
                WeatherOutcomeBatchItem(
                    market_id=parsed_market.market_id,
                    parsed_market_id=parsed_market.id,
                    status="skipped",
                    reason="older parsed market for already-scanned market",
                )
            )
            continue
        seen_market_ids.add(parsed_market.market_id)

        if payload.skip_existing_outcomes:
            existing = db.scalars(
                select(ResolvedOutcome.id)
                .where(ResolvedOutcome.market_id == parsed_market.market_id)
                .where(ResolvedOutcome.resolution_source == payload.resolution_provider)
                .limit(1)
            ).first()
            if existing is not None:
                skipped += 1
                results.append(
                    WeatherOutcomeBatchItem(
                        market_id=parsed_market.market_id,
                        parsed_market_id=parsed_market.id,
                        status="skipped",
                        reason="resolved outcome already exists for provider",
                    )
                )
                continue

        try:
            outcome = await resolve_weather_outcome_for_parsed_market(
                parsed_market,
                provider=payload.resolution_provider,
            )
        except (ValueError, httpx.HTTPError) as exc:
            errors += 1
            results.append(
                WeatherOutcomeBatchItem(
                    market_id=parsed_market.market_id,
                    parsed_market_id=parsed_market.id,
                    status="error",
                    reason=str(exc),
                )
            )
            continue

        db.add(outcome)
        db.flush()
        settlement = None
        if payload.settle_open_trades:
            settlement = settle_open_paper_trades_for_outcome(db, outcome)
            settled_trades += settlement.settled_count
        resolved += 1
        results.append(
            WeatherOutcomeBatchItem(
                market_id=parsed_market.market_id,
                parsed_market_id=parsed_market.id,
                status="resolved",
                outcome_id=outcome.id,
                settled_count=settlement.settled_count if settlement is not None else 0,
            )
        )

    db.commit()
    return WeatherOutcomeBatchResolveResponse(
        resolution_provider=payload.resolution_provider,
        requested_limit=payload.limit,
        scanned=len(parsed_markets),
        resolved=resolved,
        skipped=skipped,
        errors=errors,
        settled_trades=settled_trades,
        results=results,
    )


@router.get("/resolved-outcomes/eligibility-preview", response_model=OutcomeEligibilityPreviewResponse)
def preview_outcome_resolution_eligibility(
    resolution_provider: str = Query(default="open_meteo_archive", pattern="^(open_meteo_archive|noaa_cdo_daily)$"),
    limit: int = Query(default=100, gt=0, le=500),
    db: Session = Depends(get_db),
) -> OutcomeEligibilityPreviewResponse:
    now = utc_now()
    parsed_markets = list(
        db.scalars(
            select(ParsedMarket)
            .join(Market, Market.id == ParsedMarket.market_id)
            .order_by(ParsedMarket.created_at.desc(), ParsedMarket.id.desc())
            .limit(limit)
        )
    )

    seen_market_ids: set[int] = set()
    results: list[OutcomeEligibilityPreviewItem] = []
    counts: dict[str, int] = {}
    for parsed_market in parsed_markets:
        market = parsed_market.market
        if parsed_market.market_id in seen_market_ids:
            status = "skipped"
            reason = "older parsed market for already-previewed market"
            latest_outcome = None
        else:
            seen_market_ids.add(parsed_market.market_id)
            latest_outcome = _latest_outcome_for_provider(db, parsed_market.market_id, resolution_provider)
            status, reason = _outcome_eligibility_status(parsed_market, latest_outcome, now)

        counts[status] = counts.get(status, 0) + 1
        results.append(
            OutcomeEligibilityPreviewItem(
                market_id=parsed_market.market_id,
                parsed_market_id=parsed_market.id,
                question=market.question if market is not None else "",
                location_name=parsed_market.location_name,
                target_start=parsed_market.target_start,
                target_end=parsed_market.target_end,
                status=status,
                reason=reason,
                latest_outcome_id=latest_outcome.id if latest_outcome is not None else None,
                latest_outcome_source=latest_outcome.resolution_source if latest_outcome is not None else None,
            )
        )

    return OutcomeEligibilityPreviewResponse(
        resolution_provider=resolution_provider,
        limit=limit,
        counts=counts,
        results=results,
    )


def _outcome_eligibility_status(
    parsed_market: ParsedMarket,
    latest_outcome: ResolvedOutcome | None,
    now,
) -> tuple[str, str | None]:
    if latest_outcome is not None:
        return "already_resolved", "resolved outcome already exists for provider"
    if parsed_market.latitude is None or parsed_market.longitude is None:
        return "missing_coordinates", "parsed market is missing latitude or longitude"
    if parsed_market.target_start is None:
        return "missing_target_window", "parsed market is missing target dates"
    target_end = parsed_market.target_end or parsed_market.target_start
    if _as_aware_datetime(target_end) > now:
        return "not_ready", "target weather window has not completed"
    return "ready", None


def _as_aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


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
