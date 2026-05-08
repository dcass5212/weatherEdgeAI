import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.backtesting.schemas import BacktestRunRequest, BacktestRunResponse, CalibrationBucket
from app.db.models import EVRecommendation, Market, PaperTrade, Prediction, ResolvedOutcome, utc_now
from app.modeling.calibration import calibration_summary
from app.modeling.metrics import brier_score


SEED_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "seed_replay.json"


@dataclass(frozen=True)
class ReplayRow:
    probability_yes: float
    outcome_yes: int
    resolved_at: datetime | None


@dataclass(frozen=True)
class PaperTradeReplayRow:
    side: str
    entry_price: float
    quantity: float
    outcome_yes: int
    resolved_at: datetime


@dataclass(frozen=True)
class PaperTradeSummary:
    paper_trade_count: int
    paper_total_pnl: float | None
    paper_roi: float | None
    max_drawdown: float | None


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _date_window(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
    return start, end


def _log_loss(probability: float, outcome: int) -> float:
    clipped = min(max(probability, 1e-15), 1 - 1e-15)
    return -(outcome * math.log(clipped) + (1 - outcome) * math.log(1 - clipped))


def _outcome_to_int(actual_outcome: str) -> int:
    normalized = actual_outcome.upper()
    if normalized == "YES":
        return 1
    if normalized == "NO":
        return 0
    raise ValueError("actual_outcome must be YES or NO")


def _sample_size_note(num_predictions: int) -> str:
    if num_predictions < 30:
        return "Very small sample; use metrics only to verify the replay workflow."
    if num_predictions < 100:
        return "Small sample; calibration and win-rate estimates may be unstable."
    return "Sample size is large enough for directional review, but still requires leakage and coverage checks."


def _win_rate(rows: list[ReplayRow]) -> float:
    wins = 0
    for row in rows:
        predicted_yes = row.probability_yes >= 0.5
        actual_yes = row.outcome_yes == 1
        if predicted_yes == actual_yes:
            wins += 1
    return round(wins / len(rows), 6)


def _settlement_price(side: str, outcome_yes: int) -> float:
    normalized_side = side.upper()
    if normalized_side == "YES":
        return 1.0 if outcome_yes == 1 else 0.0
    if normalized_side == "NO":
        return 1.0 if outcome_yes == 0 else 0.0
    raise ValueError("paper trade side must be YES or NO")


def _paper_trade_summary(rows: list[PaperTradeReplayRow]) -> PaperTradeSummary:
    if not rows:
        return PaperTradeSummary(
            paper_trade_count=0,
            paper_total_pnl=None,
            paper_roi=None,
            max_drawdown=None,
        )

    total_cost = 0.0
    total_pnl = 0.0
    cumulative_pnl = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for row in sorted(rows, key=lambda item: item.resolved_at):
        settlement_price = _settlement_price(row.side, row.outcome_yes)
        cost = row.entry_price * row.quantity
        pnl = (settlement_price - row.entry_price) * row.quantity
        total_cost += cost
        total_pnl += pnl
        cumulative_pnl += pnl
        peak = max(peak, cumulative_pnl)
        max_drawdown = max(max_drawdown, peak - cumulative_pnl)

    return PaperTradeSummary(
        paper_trade_count=len(rows),
        paper_total_pnl=round(total_pnl, 6),
        paper_roi=round(total_pnl / total_cost, 6) if total_cost else None,
        max_drawdown=round(max_drawdown, 6),
    )


class BacktestRunner:
    def __init__(self, db: Session) -> None:
        self.db = db

    def run(self, payload: BacktestRunRequest) -> BacktestRunResponse:
        if payload.end_date < payload.start_date:
            raise ValueError("end_date must be on or after start_date")

        if payload.seed_fixtures:
            self._seed_fixture_records()

        rows = self._load_replay_rows(payload)
        ev_recommendation_count = self._count_ev_recommendations(payload)
        paper_summary = _paper_trade_summary(self._load_paper_trade_rows(payload))
        if not rows:
            return BacktestRunResponse(
                model_version=payload.model_version,
                num_predictions=0,
                num_resolved_outcomes=0,
                ev_recommendation_count=ev_recommendation_count,
                paper_trade_count=paper_summary.paper_trade_count,
                paper_total_pnl=paper_summary.paper_total_pnl,
                paper_roi=paper_summary.paper_roi,
                max_drawdown=paper_summary.max_drawdown,
                status="no_resolved_predictions",
                source="seed_fixture" if payload.seed_fixtures else "persisted_records",
            )

        brier_values = [brier_score(row.probability_yes, row.outcome_yes) for row in rows]
        log_loss_values = [_log_loss(row.probability_yes, row.outcome_yes) for row in rows]
        buckets = calibration_summary([(row.probability_yes, row.outcome_yes) for row in rows])
        return BacktestRunResponse(
            model_version=payload.model_version,
            num_predictions=len(rows),
            num_resolved_outcomes=len(rows),
            ev_recommendation_count=ev_recommendation_count,
            paper_trade_count=paper_summary.paper_trade_count,
            win_rate=_win_rate(rows),
            brier_score=round(sum(brier_values) / len(brier_values), 6),
            log_loss=round(sum(log_loss_values) / len(log_loss_values), 6),
            calibration_buckets=[CalibrationBucket.model_validate(bucket.__dict__) for bucket in buckets],
            sample_size_note=_sample_size_note(len(rows)),
            paper_total_pnl=paper_summary.paper_total_pnl,
            paper_roi=paper_summary.paper_roi,
            max_drawdown=paper_summary.max_drawdown,
            status="completed",
            source="seed_fixture" if payload.seed_fixtures else "persisted_records",
        )

    def _load_replay_rows(self, payload: BacktestRunRequest) -> list[ReplayRow]:
        start, end = _date_window(payload.start_date, payload.end_date)
        statement: Select[tuple[Prediction, ResolvedOutcome]] = (
            select(Prediction, ResolvedOutcome)
            .join(ResolvedOutcome, ResolvedOutcome.market_id == Prediction.market_id)
            .where(Prediction.model_version == payload.model_version)
            .where(ResolvedOutcome.resolved_at.is_not(None))
            .where(ResolvedOutcome.resolved_at >= start)
            .where(ResolvedOutcome.resolved_at <= end)
            .order_by(ResolvedOutcome.resolved_at.asc(), Prediction.created_at.asc())
        )
        return [
            ReplayRow(
                probability_yes=prediction.p_yes,
                outcome_yes=_outcome_to_int(outcome.actual_outcome),
                resolved_at=outcome.resolved_at,
            )
            for prediction, outcome in self.db.execute(statement).all()
        ]

    def _count_ev_recommendations(self, payload: BacktestRunRequest) -> int:
        start, end = _date_window(payload.start_date, payload.end_date)
        statement = (
            select(EVRecommendation.id)
            .join(Prediction, EVRecommendation.prediction_id == Prediction.id)
            .join(ResolvedOutcome, ResolvedOutcome.market_id == Prediction.market_id)
            .where(Prediction.model_version == payload.model_version)
            .where(ResolvedOutcome.resolved_at.is_not(None))
            .where(ResolvedOutcome.resolved_at >= start)
            .where(ResolvedOutcome.resolved_at <= end)
        )
        return len(self.db.execute(statement).all())

    def _load_paper_trade_rows(self, payload: BacktestRunRequest) -> list[PaperTradeReplayRow]:
        start, end = _date_window(payload.start_date, payload.end_date)
        statement: Select[tuple[PaperTrade, ResolvedOutcome]] = (
            select(PaperTrade, ResolvedOutcome)
            .join(EVRecommendation, PaperTrade.recommendation_id == EVRecommendation.id)
            .join(Prediction, EVRecommendation.prediction_id == Prediction.id)
            .join(ResolvedOutcome, ResolvedOutcome.market_id == PaperTrade.market_id)
            .where(Prediction.model_version == payload.model_version)
            .where(ResolvedOutcome.resolved_at.is_not(None))
            .where(ResolvedOutcome.resolved_at >= start)
            .where(ResolvedOutcome.resolved_at <= end)
            .order_by(ResolvedOutcome.resolved_at.asc(), PaperTrade.entry_time.asc())
        )
        return [
            PaperTradeReplayRow(
                side=trade.side,
                entry_price=trade.entry_price,
                quantity=trade.quantity,
                outcome_yes=_outcome_to_int(outcome.actual_outcome),
                resolved_at=outcome.resolved_at,
            )
            for trade, outcome in self.db.execute(statement).all()
            if outcome.resolved_at is not None
        ]

    def _seed_fixture_records(self) -> None:
        data = json.loads(SEED_FIXTURE_PATH.read_text())
        for row in data["resolved_predictions"]:
            source_market_id = row["source_market_id"]
            market = self.db.scalars(
                select(Market)
                .where(Market.source == "seed_fixture")
                .where(Market.source_market_id == source_market_id)
                .limit(1)
            ).first()
            if market is None:
                market = Market(
                    source="seed_fixture",
                    source_market_id=source_market_id,
                    question=row["question"],
                    category="weather",
                    active=False,
                    closed=True,
                    end_time=_parse_datetime(row.get("resolved_at")),
                    raw_json={"seed_fixture": True},
                )
                self.db.add(market)
                self.db.flush()

            prediction = self.db.scalars(
                select(Prediction)
                .where(Prediction.market_id == market.id)
                .where(Prediction.model_version == row["model_version"])
                .limit(1)
            ).first()
            if prediction is None:
                prediction = Prediction(
                    market_id=market.id,
                    model_version=row["model_version"],
                    p_yes=row["p_yes"],
                    p_no=round(1 - row["p_yes"], 10),
                    confidence=row.get("confidence", "seed"),
                    features_json=row.get("features_json", {}),
                    created_at=_parse_datetime(row.get("prediction_created_at")) or utc_now(),
                )
                self.db.add(prediction)
                self.db.flush()

            recommendation_data = row.get("ev_recommendation")
            if recommendation_data is not None:
                recommendation = self.db.scalars(
                    select(EVRecommendation).where(EVRecommendation.prediction_id == prediction.id).limit(1)
                ).first()
                if recommendation is None:
                    recommendation = EVRecommendation(
                        prediction_id=prediction.id,
                        market_price_yes=recommendation_data.get("market_price_yes"),
                        market_price_no=recommendation_data.get("market_price_no"),
                        edge_yes=recommendation_data.get("edge_yes"),
                        edge_no=recommendation_data.get("edge_no"),
                        ev_yes=recommendation_data.get("ev_yes"),
                        ev_no=recommendation_data.get("ev_no"),
                        recommendation=recommendation_data["recommendation"],
                        paper_position_size=recommendation_data.get("paper_position_size"),
                        reason=recommendation_data.get("reason"),
                    )
                    self.db.add(recommendation)
                    self.db.flush()

                paper_trade_data = row.get("paper_trade")
                if paper_trade_data is not None:
                    trade_exists = self.db.scalars(
                        select(PaperTrade).where(PaperTrade.recommendation_id == recommendation.id).limit(1)
                    ).first()
                    if trade_exists is None:
                        self.db.add(
                            PaperTrade(
                                market_id=market.id,
                                recommendation_id=recommendation.id,
                                side=paper_trade_data["side"],
                                entry_price=paper_trade_data["entry_price"],
                                quantity=paper_trade_data["quantity"],
                                entry_time=_parse_datetime(paper_trade_data.get("entry_time")) or utc_now(),
                                status=paper_trade_data.get("status", "OPEN"),
                            )
                        )

            outcome_exists = self.db.scalars(
                select(ResolvedOutcome)
                .where(ResolvedOutcome.market_id == market.id)
                .where(ResolvedOutcome.resolution_source == "seed_fixture")
                .limit(1)
            ).first()
            if outcome_exists is None:
                self.db.add(
                    ResolvedOutcome(
                        market_id=market.id,
                        actual_outcome=row["actual_outcome"],
                        actual_value=row.get("actual_value"),
                        actual_unit=row.get("actual_unit"),
                        resolution_source="seed_fixture",
                        resolved_at=_parse_datetime(row.get("resolved_at")),
                        raw_json=row,
                    )
                )

        self.db.commit()
