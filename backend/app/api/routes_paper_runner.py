"""Paper runner API routes.

These endpoints expose the public-market paper runner as an auditable one-shot
workflow. They create simulated paper trades only; live execution remains out
of scope for this API.
"""

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaperRunnerRun
from app.db.session import get_db
from app.strategy.paper_market_runner import PaperMarketRunnerConfig, run_paper_market_once_recorded


router = APIRouter(prefix="/paper-runner", tags=["paper-runner"])


class PaperRunnerRunRequest(BaseModel):
    source: str = "polymarket"
    keywords: list[str] = Field(default_factory=lambda: ["rain", "weather", "precipitation"])
    discovery_limit: int = Field(default=25, gt=0, le=100)
    process_limit: int = Field(default=10, gt=0, le=100)
    max_trades: int = Field(default=3, ge=0, le=25)
    quantity: float = Field(default=1.0, gt=0)
    min_liquidity: float = Field(default=0.0, ge=0)
    max_spread: float = Field(default=0.15, ge=0)
    refresh_prices: bool = True
    dry_run: bool = False


class PaperRunnerRunRead(BaseModel):
    id: int
    status: str
    source: str
    started_at: str
    completed_at: str | None
    config: dict
    discovered: int
    created: int
    updated: int
    price_snapshots_created: int
    processed: int
    parsed: int
    forecasts_created: int
    predictions_created: int
    recommendations_created: int
    paper_trades_created: int
    skipped: dict
    errors: list[str]
    report: dict | None


def _config_from_request(payload: PaperRunnerRunRequest) -> PaperMarketRunnerConfig:
    return PaperMarketRunnerConfig(
        source=payload.source,
        keywords=payload.keywords,
        discovery_limit=payload.discovery_limit,
        process_limit=payload.process_limit,
        max_trades=payload.max_trades,
        quantity=payload.quantity,
        min_liquidity=payload.min_liquidity,
        max_spread=payload.max_spread,
        refresh_prices=payload.refresh_prices,
        create_trades=not payload.dry_run,
    )


def _read_model(run: PaperRunnerRun) -> PaperRunnerRunRead:
    return PaperRunnerRunRead(
        id=run.id,
        status=run.status,
        source=run.source,
        started_at=run.started_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        config=run.config_json,
        discovered=run.discovered,
        created=run.created,
        updated=run.updated,
        price_snapshots_created=run.price_snapshots_created,
        processed=run.processed,
        parsed=run.parsed,
        forecasts_created=run.forecasts_created,
        predictions_created=run.predictions_created,
        recommendations_created=run.recommendations_created,
        paper_trades_created=run.paper_trades_created,
        skipped=run.skipped_json,
        errors=run.errors_json,
        report=run.report_json,
    )


@router.post("/run-once", response_model=PaperRunnerRunRead, status_code=201)
async def run_paper_runner_once(payload: PaperRunnerRunRequest, db: Session = Depends(get_db)) -> PaperRunnerRunRead:
    try:
        run = await run_paper_market_once_recorded(db, _config_from_request(payload))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Paper runner failed: {exc}") from exc
    return _read_model(run)


@router.get("/runs", response_model=list[PaperRunnerRunRead])
def list_paper_runner_runs(
    limit: int = Query(default=20, gt=0, le=100),
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[PaperRunnerRunRead]:
    query = select(PaperRunnerRun)
    if status is not None:
        query = query.where(PaperRunnerRun.status == status)
    query = query.order_by(PaperRunnerRun.started_at.desc(), PaperRunnerRun.id.desc()).limit(limit)
    return [_read_model(run) for run in db.scalars(query)]


@router.get("/runs/{run_id}", response_model=PaperRunnerRunRead)
def get_paper_runner_run(run_id: int, db: Session = Depends(get_db)) -> PaperRunnerRunRead:
    run = db.get(PaperRunnerRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Paper runner run not found")
    return _read_model(run)
