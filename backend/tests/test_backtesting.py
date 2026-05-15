from datetime import datetime, timezone

import pytest
import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.backtesting.noaa_client import NoaaCdoClient
from app.backtesting.outcome_resolver import (
    build_resolved_outcome_from_observations,
    resolve_weather_outcome_for_parsed_market,
)
from app.backtesting.backtest_runner import BacktestRunner
from app.backtesting.schemas import BacktestRunRequest, WalkForwardBacktestRequest
from app.backtesting.walk_forward import WalkForwardBacktestRunner
from app.db.models import EVRecommendation, Market, ParsedMarket, PaperTrade, Prediction, ResolvedOutcome, utc_now


def test_build_resolved_outcome_from_open_meteo_archive_observations() -> None:
    parsed_market = ParsedMarket(
        id=12,
        market_id=34,
        location_name="New York City",
        latitude=40.7128,
        longitude=-74.006,
        metric="precipitation",
        operator=">",
        threshold_value=1.0,
        threshold_unit="inch",
        parser_version="regex_precip_v1",
        parse_confidence=0.85,
    )
    raw_observations = {
        "daily": {"precipitation_sum": [12.7, "14.0", None, "bad"]},
        "daily_units": {"precipitation_sum": "mm"},
    }

    outcome = build_resolved_outcome_from_observations(parsed_market, raw_observations)

    assert outcome.market_id == 34
    assert outcome.actual_outcome == "YES"
    assert outcome.actual_value == 1.0512
    assert outcome.actual_unit == "inch"
    assert outcome.resolution_source == "open_meteo_archive"
    assert outcome.raw_json["parsed_market_id"] == 12
    assert outcome.raw_json["provider_payload"] == raw_observations


def test_build_resolved_outcome_rejects_missing_observation_units() -> None:
    parsed_market = ParsedMarket(
        id=12,
        market_id=34,
        location_name="New York City",
        latitude=40.7128,
        longitude=-74.006,
        metric="precipitation",
        operator=">",
        threshold_value=1.0,
        threshold_unit="inch",
        parser_version="regex_precip_v1",
        parse_confidence=0.85,
    )

    with pytest.raises(ValueError, match="precipitation units"):
        build_resolved_outcome_from_observations(parsed_market, {"daily": {"precipitation_sum": [1.2]}})


def test_build_resolved_outcome_from_noaa_daily_observations() -> None:
    parsed_market = ParsedMarket(
        id=12,
        market_id=34,
        location_name="New York City",
        latitude=40.7128,
        longitude=-74.006,
        metric="precipitation",
        operator=">=",
        threshold_value=1.0,
        threshold_unit="inch",
        parser_version="regex_precip_v1",
        parse_confidence=0.85,
    )
    raw_observations = {
        "source": "noaa_cdo_daily",
        "results": [
            {"datatype": "TMAX", "value": 71.0, "unit": "F"},
            {"datatype": "PRCP", "date": "2026-05-05T00:00:00", "station": "GHCND:USW00094728", "value": 12.7, "unit": "mm"},
            {"datatype": "PRCP", "date": "2026-05-06T00:00:00", "station": "GHCND:USW00094728", "value": "12.7", "unit": "mm"},
        ],
    }

    outcome = build_resolved_outcome_from_observations(
        parsed_market,
        raw_observations,
        resolution_source="noaa_cdo_daily",
    )

    assert outcome.actual_outcome == "YES"
    assert outcome.actual_value == 1.0
    assert outcome.actual_unit == "inch"
    assert outcome.resolution_source == "noaa_cdo_daily"
    assert outcome.raw_json["source"] == "noaa_cdo_daily"
    assert outcome.raw_json["provider_payload"] == raw_observations


def test_build_resolved_outcome_supports_less_than_operator() -> None:
    parsed_market = ParsedMarket(
        id=12,
        market_id=34,
        location_name="New York City",
        latitude=40.7128,
        longitude=-74.006,
        metric="precipitation",
        operator="<",
        threshold_value=2.0,
        threshold_unit="inch",
        parser_version="regex_precip_v1",
        parse_confidence=0.85,
    )

    outcome = build_resolved_outcome_from_observations(
        parsed_market,
        {"daily": {"precipitation_sum": [1.2]}, "daily_units": {"precipitation_sum": "inch"}},
    )

    assert outcome.actual_outcome == "YES"
    assert outcome.actual_value == 1.2
    assert outcome.actual_unit == "inch"


def test_build_resolved_outcome_supports_between_operator() -> None:
    parsed_market = ParsedMarket(
        id=12,
        market_id=34,
        location_name="Hong Kong",
        latitude=22.3193,
        longitude=114.1694,
        metric="precipitation",
        operator="between",
        threshold_value=190.0,
        threshold_unit="mm",
        parser_version="regex_precip_v1",
        parse_confidence=0.75,
        raw_parse_json={"interval_upper_value": 200.0},
    )

    outcome = build_resolved_outcome_from_observations(
        parsed_market,
        {"daily": {"precipitation_sum": [195.0]}, "daily_units": {"precipitation_sum": "mm"}},
    )

    assert outcome.actual_outcome == "YES"
    assert outcome.actual_value == 195.0
    assert outcome.raw_json["threshold"]["interval_upper_value"] == 200.0


def test_build_resolved_outcome_rejects_noaa_daily_prcp_without_units() -> None:
    parsed_market = ParsedMarket(
        id=12,
        market_id=34,
        location_name="New York City",
        latitude=40.7128,
        longitude=-74.006,
        metric="precipitation",
        operator=">",
        threshold_value=1.0,
        threshold_unit="inch",
        parser_version="regex_precip_v1",
        parse_confidence=0.85,
    )

    with pytest.raises(ValueError, match="NOAA daily PRCP record did not include precipitation units"):
        build_resolved_outcome_from_observations(
            parsed_market,
            {"source": "noaa_cdo_daily", "results": [{"datatype": "PRCP", "value": 25.4}]},
            resolution_source="noaa_cdo_daily",
        )


def test_build_resolved_outcome_rejects_noaa_daily_mixed_prcp_units() -> None:
    parsed_market = ParsedMarket(
        id=12,
        market_id=34,
        location_name="New York City",
        latitude=40.7128,
        longitude=-74.006,
        metric="precipitation",
        operator=">",
        threshold_value=1.0,
        threshold_unit="inch",
        parser_version="regex_precip_v1",
        parse_confidence=0.85,
    )

    with pytest.raises(ValueError, match="mixed precipitation units"):
        build_resolved_outcome_from_observations(
            parsed_market,
            {
                "source": "noaa_cdo_daily",
                "results": [
                    {"datatype": "PRCP", "value": 0.5, "unit": "inch"},
                    {"datatype": "PRCP", "value": 12.7, "unit": "mm"},
                ],
            },
            resolution_source="noaa_cdo_daily",
        )


@pytest.mark.anyio
async def test_noaa_cdo_client_requires_token() -> None:
    client = NoaaCdoClient(base_url="https://noaa.test", token=None)

    with pytest.raises(ValueError, match="NOAA_CDO_TOKEN is required"):
        await client.fetch_daily_precipitation(
            latitude=40.7128,
            longitude=-74.006,
            start_date="2026-05-05",
            end_date="2026-05-05",
        )


@pytest.mark.anyio
async def test_resolve_weather_outcome_from_mocked_noaa_cdo_daily_client() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/data"
        assert request.headers["token"] == "test-token"
        assert request.url.params["datasetid"] == "GHCND"
        assert request.url.params["datatypeid"] == "PRCP"
        assert request.url.params["units"] == "metric"
        return httpx.Response(
            200,
            json={
                "results": [
                    {"datatype": "PRCP", "date": "2026-05-05T00:00:00", "station": "GHCND:TEST", "value": 25.4}
                ]
            },
        )

    parsed_market = ParsedMarket(
        id=12,
        market_id=34,
        location_name="New York City",
        latitude=40.7128,
        longitude=-74.006,
        metric="precipitation",
        operator=">=",
        threshold_value=1.0,
        threshold_unit="inch",
        target_start=datetime(2026, 5, 5, tzinfo=timezone.utc),
        target_end=datetime(2026, 5, 5, tzinfo=timezone.utc),
        parser_version="regex_precip_v1",
        parse_confidence=0.85,
    )

    outcome = await resolve_weather_outcome_for_parsed_market(
        parsed_market,
        provider="noaa_cdo_daily",
        noaa_client=NoaaCdoClient(
            base_url="https://noaa.test",
            token="test-token",
            transport=httpx.MockTransport(handler),
        ),
    )

    assert outcome.actual_outcome == "YES"
    assert outcome.actual_value == 1.0
    assert outcome.actual_unit == "inch"
    assert outcome.resolution_source == "noaa_cdo_daily"
    assert outcome.raw_json["provider_payload"]["source"] == "noaa_cdo_daily"


def test_create_resolved_outcome_route(client: TestClient) -> None:
    create_response = client.post(
        "/markets",
        json={
            "source": "mock",
            "source_market_id": "resolved-outcome-route-1",
            "question": "Will New York City get more than 1 inch of rain on May 5?",
            "category": "weather",
        },
    )
    create_response.raise_for_status()
    market_id = create_response.json()["id"]

    response = client.post(
        "/backtests/resolved-outcomes",
        json={
            "market_id": market_id,
            "actual_outcome": "YES",
            "actual_value": 1.2,
            "actual_unit": "inch",
            "resolution_source": "test_fixture",
            "resolved_at": "2026-05-06T02:00:00Z",
            "raw_json": {"source": "test"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["market_id"] == market_id
    assert body["actual_outcome"] == "YES"
    assert body["actual_value"] == 1.2


def test_create_resolved_outcome_settles_open_paper_trade(client: TestClient, db_session: Session) -> None:
    market = Market(
        source="test",
        source_market_id="settle-route-1",
        question="Will New York City get more than 1 inch of rain on May 5?",
        category="weather",
    )
    db_session.add(market)
    db_session.flush()
    prediction = Prediction(market_id=market.id, model_version="baseline_precip_v1", p_yes=0.7, p_no=0.3)
    db_session.add(prediction)
    db_session.flush()
    recommendation = EVRecommendation(
        prediction_id=prediction.id,
        market_price_yes=0.4,
        market_price_no=0.6,
        edge_yes=0.3,
        edge_no=-0.3,
        ev_yes=0.3,
        ev_no=-0.3,
        recommendation="PAPER_BUY_YES",
    )
    db_session.add(recommendation)
    db_session.flush()
    trade = PaperTrade(
        market_id=market.id,
        recommendation_id=recommendation.id,
        side="YES",
        entry_price=0.4,
        quantity=10.0,
        status="OPEN",
    )
    db_session.add(trade)
    db_session.commit()

    response = client.post(
        "/backtests/resolved-outcomes",
        json={
            "market_id": market.id,
            "actual_outcome": "YES",
            "actual_value": 1.2,
            "actual_unit": "inch",
            "resolution_source": "test_fixture",
            "resolved_at": "2026-05-06T02:00:00Z",
        },
    )

    assert response.status_code == 201
    db_session.refresh(trade)
    assert trade.status == "RESOLVED"
    assert trade.exit_price == 1.0
    assert trade.pnl == 6.0


def test_resolve_weather_outcome_route_persists_provider_result(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_resolve_weather_outcome(parsed_market: ParsedMarket, provider: str = "open_meteo_archive") -> ResolvedOutcome:
        return ResolvedOutcome(
            market_id=parsed_market.market_id,
            actual_outcome="NO",
            actual_value=0.2,
            actual_unit="inch",
            resolution_source="open_meteo_archive",
            resolved_at=utc_now(),
            raw_json={"source": "test_archive", "parsed_market_id": parsed_market.id},
        )

    monkeypatch.setattr(
        "app.api.routes_backtests.resolve_weather_outcome_for_parsed_market",
        fake_resolve_weather_outcome,
    )
    create_response = client.post(
        "/markets",
        json={
            "source": "mock",
            "source_market_id": "weather-resolve-route-1",
            "question": "Will New York City get more than 1 inch of rain on May 5?",
            "category": "weather",
        },
    )
    create_response.raise_for_status()
    market_id = create_response.json()["id"]
    parse_response = client.post(f"/markets/{market_id}/parse")
    parse_response.raise_for_status()

    response = client.post("/backtests/resolved-outcomes/resolve-weather", json={"market_id": market_id})

    assert response.status_code == 201
    body = response.json()
    assert body["market_id"] == market_id
    assert body["actual_outcome"] == "NO"
    assert body["actual_value"] == 0.2
    assert body["resolution_source"] == "open_meteo_archive"

    list_response = client.get(f"/backtests/resolved-outcomes?market_id={market_id}")
    list_response.raise_for_status()
    assert len(list_response.json()) == 1


def test_resolve_weather_outcomes_batch_skips_existing_and_settles(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_resolve_weather_outcome(parsed_market: ParsedMarket, provider: str = "open_meteo_archive") -> ResolvedOutcome:
        return ResolvedOutcome(
            market_id=parsed_market.market_id,
            actual_outcome="NO",
            actual_value=0.2,
            actual_unit="inch",
            resolution_source=provider,
            resolved_at=datetime(2026, 5, 6, 2, tzinfo=timezone.utc),
            raw_json={"source": "test_archive", "parsed_market_id": parsed_market.id},
        )

    monkeypatch.setattr(
        "app.api.routes_backtests.resolve_weather_outcome_for_parsed_market",
        fake_resolve_weather_outcome,
    )
    market = Market(
        source="test",
        source_market_id="batch-resolve-1",
        question="Will Chicago receive less than 1 inch of rain on May 5?",
        category="weather",
    )
    db_session.add(market)
    db_session.flush()
    parsed = ParsedMarket(
        market_id=market.id,
        location_name="Chicago",
        latitude=41.8781,
        longitude=-87.6298,
        metric="precipitation",
        operator="<",
        threshold_value=1.0,
        threshold_unit="inch",
        target_start=datetime(2026, 5, 5, tzinfo=timezone.utc),
        target_end=datetime(2026, 5, 5, tzinfo=timezone.utc),
        parser_version="regex_precip_v1",
        parse_confidence=0.8,
    )
    db_session.add(parsed)
    db_session.flush()
    prediction = Prediction(market_id=market.id, parsed_market_id=parsed.id, model_version="baseline_precip_v1", p_yes=0.65, p_no=0.35)
    db_session.add(prediction)
    db_session.flush()
    recommendation = EVRecommendation(
        prediction_id=prediction.id,
        market_price_yes=0.5,
        market_price_no=0.5,
        recommendation="PAPER_BUY_NO",
    )
    db_session.add(recommendation)
    db_session.flush()
    trade = PaperTrade(
        market_id=market.id,
        recommendation_id=recommendation.id,
        side="NO",
        entry_price=0.5,
        quantity=4.0,
        status="OPEN",
    )
    db_session.add(trade)
    db_session.commit()

    response = client.post("/backtests/resolved-outcomes/resolve-weather-batch", json={"limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert body["resolved"] == 1
    assert body["settled_trades"] == 1
    assert body["results"][0]["status"] == "resolved"
    db_session.refresh(trade)
    assert trade.status == "RESOLVED"
    assert trade.exit_price == 1.0
    assert trade.pnl == 2.0

    second_response = client.post("/backtests/resolved-outcomes/resolve-weather-batch", json={"limit": 10})
    second_response.raise_for_status()
    assert second_response.json()["resolved"] == 0
    assert second_response.json()["skipped"] >= 1


def test_outcome_eligibility_preview_reports_resolution_readiness(
    client: TestClient,
    db_session: Session,
) -> None:
    def add_market_with_parse(
        source_market_id: str,
        *,
        latitude: float | None = 40.7128,
        longitude: float | None = -74.006,
        target_start: datetime | None = datetime(2026, 5, 5, tzinfo=timezone.utc),
        target_end: datetime | None = datetime(2026, 5, 5, tzinfo=timezone.utc),
        location_name: str = "New York City",
    ) -> tuple[Market, ParsedMarket]:
        market = Market(
            source="test",
            source_market_id=source_market_id,
            question=f"Will {location_name} get more than 1 inch of rain?",
            category="weather",
        )
        db_session.add(market)
        db_session.flush()
        parsed = ParsedMarket(
            market_id=market.id,
            location_name=location_name,
            latitude=latitude,
            longitude=longitude,
            metric="precipitation",
            operator=">",
            threshold_value=1.0,
            threshold_unit="inch",
            target_start=target_start,
            target_end=target_end,
            parser_version="regex_precip_v1",
            parse_confidence=0.8,
        )
        db_session.add(parsed)
        db_session.flush()
        return market, parsed

    ready_market, _ = add_market_with_parse("preview-ready")
    future_market, _ = add_market_with_parse(
        "preview-not-ready",
        target_start=datetime(2026, 5, 20, tzinfo=timezone.utc),
        target_end=datetime(2026, 5, 20, tzinfo=timezone.utc),
    )
    missing_coordinates_market, _ = add_market_with_parse("preview-missing-coords", latitude=None, longitude=None)
    missing_target_market, _ = add_market_with_parse("preview-missing-target", target_start=None, target_end=None)
    resolved_market, _ = add_market_with_parse("preview-resolved")
    duplicate_market, latest_duplicate_parse = add_market_with_parse("preview-duplicate")
    db_session.add(
        ParsedMarket(
            market_id=duplicate_market.id,
            location_name="New York City",
            latitude=40.7128,
            longitude=-74.006,
            metric="precipitation",
            operator=">",
            threshold_value=1.0,
            threshold_unit="inch",
            target_start=datetime(2026, 5, 5, tzinfo=timezone.utc),
            target_end=datetime(2026, 5, 5, tzinfo=timezone.utc),
            parser_version="regex_precip_v1",
            parse_confidence=0.7,
        )
    )
    db_session.add(
        ResolvedOutcome(
            market_id=resolved_market.id,
            actual_outcome="YES",
            actual_value=1.4,
            actual_unit="inch",
            resolution_source="open_meteo_archive",
            resolved_at=datetime(2026, 5, 6, 2, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    response = client.get("/backtests/resolved-outcomes/eligibility-preview?limit=20")

    assert response.status_code == 200
    body = response.json()
    assert body["resolution_provider"] == "open_meteo_archive"
    assert body["counts"]["ready"] == 2
    assert body["counts"]["not_ready"] == 1
    assert body["counts"]["missing_coordinates"] == 1
    assert body["counts"]["missing_target_window"] == 1
    assert body["counts"]["already_resolved"] == 1
    assert body["counts"]["skipped"] == 1

    by_market = {item["market_id"]: item for item in body["results"] if item["status"] != "skipped"}
    assert by_market[ready_market.id]["status"] == "ready"
    assert by_market[future_market.id]["reason"] == "target weather window has not completed"
    assert by_market[missing_coordinates_market.id]["status"] == "missing_coordinates"
    assert by_market[missing_target_market.id]["status"] == "missing_target_window"
    assert by_market[resolved_market.id]["latest_outcome_source"] == "open_meteo_archive"
    skipped = [item for item in body["results"] if item["status"] == "skipped"]
    assert skipped[0]["market_id"] == duplicate_market.id
    assert skipped[0]["parsed_market_id"] == latest_duplicate_parse.id


def test_resolve_weather_outcome_route_reports_provider_http_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_resolve_weather_outcome(
        parsed_market: ParsedMarket,
        provider: str = "open_meteo_archive",
    ) -> ResolvedOutcome:
        raise httpx.ConnectError("provider unavailable")

    monkeypatch.setattr(
        "app.api.routes_backtests.resolve_weather_outcome_for_parsed_market",
        fake_resolve_weather_outcome,
    )
    create_response = client.post(
        "/markets",
        json={
            "source": "mock",
            "source_market_id": "weather-resolve-route-provider-failure",
            "question": "Will New York City get more than 1 inch of rain on May 5?",
            "category": "weather",
        },
    )
    create_response.raise_for_status()
    market_id = create_response.json()["id"]
    parse_response = client.post(f"/markets/{market_id}/parse")
    parse_response.raise_for_status()

    response = client.post(
        "/backtests/resolved-outcomes/resolve-weather",
        json={"market_id": market_id, "resolution_provider": "noaa_cdo_daily"},
    )

    assert response.status_code == 502
    assert "noaa_cdo_daily observed-weather request failed" in response.json()["detail"]


def test_backtest_runner_replays_persisted_resolved_predictions(db_session: Session) -> None:
    market = Market(
        source="test",
        source_market_id="resolved-prediction-1",
        question="Will New York City get more than 1 inch of rain on May 5?",
        category="weather",
        active=False,
        closed=True,
    )
    db_session.add(market)
    db_session.flush()
    prediction = Prediction(
        market_id=market.id,
        model_version="baseline_precip_v1",
        p_yes=0.75,
        p_no=0.25,
        confidence="medium",
    )
    db_session.add(prediction)
    db_session.flush()
    recommendation = EVRecommendation(
        prediction_id=prediction.id,
        market_price_yes=0.5,
        market_price_no=0.5,
        edge_yes=0.25,
        edge_no=-0.25,
        ev_yes=0.25,
        ev_no=-0.25,
        recommendation="PAPER_BUY_YES",
        paper_position_size=10.0,
    )
    db_session.add(recommendation)
    db_session.flush()
    db_session.add_all(
        [
            PaperTrade(
                market_id=market.id,
                recommendation_id=recommendation.id,
                side="YES",
                entry_price=0.5,
                quantity=10.0,
                entry_time=datetime(2026, 5, 5, 12, tzinfo=timezone.utc),
                status="OPEN",
            ),
            ResolvedOutcome(
                market_id=market.id,
                actual_outcome="YES",
                actual_value=1.1,
                actual_unit="inch",
                resolution_source="test_fixture",
                resolved_at=datetime(2026, 5, 6, 2, tzinfo=timezone.utc),
            ),
        ]
    )
    db_session.commit()

    result = BacktestRunner(db_session).run(
        BacktestRunRequest(start_date="2026-05-01", end_date="2026-05-10")
    )

    assert result.status == "completed"
    assert result.source == "persisted_records"
    assert result.num_predictions == 1
    assert result.num_resolved_outcomes == 1
    assert result.ev_recommendation_count == 1
    assert result.paper_trade_count == 1
    assert result.win_rate == 1.0
    assert result.brier_score == 0.0625
    assert result.log_loss is not None
    assert result.paper_gross_pnl == 5.0
    assert result.paper_fee_cost == 0.0
    assert result.paper_slippage_cost == 0.0
    assert result.paper_total_pnl == 5.0
    assert result.paper_roi == 1.0
    assert result.max_drawdown == 0.0
    assert "0.0000 fee rate" in result.paper_settlement_note
    assert result.sample_size_note == "Very small sample; use metrics only to verify the replay workflow."
    assert result.calibration_buckets[3].count == 1
    assert result.calibration_buckets[3].average_predicted_probability == 0.75
    assert result.calibration_buckets[3].observed_yes_rate == 1.0
    assert result.sample_size_gate == "insufficient_sample"
    assert [item.name for item in result.baseline_comparisons] == [
        "model_probability",
        "always_50_percent",
        "market_implied_probability",
    ]
    assert result.baseline_comparisons[0].brier_score == result.brier_score
    assert result.baseline_comparisons[1].brier_score == 0.25
    assert result.baseline_comparisons[2].prediction_count == 1


def test_backtest_runner_reports_coverage_diagnostics(db_session: Session) -> None:
    evaluated_market = Market(
        source="test",
        source_market_id="coverage-evaluated",
        question="Will New York City get more than 1 inch of rain on May 5?",
        category="weather",
        active=False,
        closed=True,
    )
    missing_outcome_market = Market(
        source="test",
        source_market_id="coverage-missing-outcome",
        question="Will Chicago receive at least 0.5 inches of rain tomorrow?",
        category="weather",
        active=False,
        closed=True,
    )
    unmatched_outcome_market = Market(
        source="test",
        source_market_id="coverage-unmatched-outcome",
        question="Will Boston get more than 1 inch of rain on May 5?",
        category="weather",
        active=False,
        closed=True,
    )
    wrong_model_market = Market(
        source="test",
        source_market_id="coverage-wrong-model",
        question="Will Philadelphia get more than 1 inch of rain on May 5?",
        category="weather",
        active=False,
        closed=True,
    )
    db_session.add_all([evaluated_market, missing_outcome_market, unmatched_outcome_market, wrong_model_market])
    db_session.flush()

    db_session.add_all(
        [
            Prediction(
                market_id=evaluated_market.id,
                model_version="baseline_precip_v1",
                p_yes=0.7,
                p_no=0.3,
                confidence="medium",
            ),
            Prediction(
                market_id=missing_outcome_market.id,
                model_version="baseline_precip_v1",
                p_yes=0.4,
                p_no=0.6,
                confidence="medium",
            ),
            Prediction(
                market_id=wrong_model_market.id,
                model_version="experimental_precip_v2",
                p_yes=0.8,
                p_no=0.2,
                confidence="medium",
            ),
            ResolvedOutcome(
                market_id=evaluated_market.id,
                actual_outcome="YES",
                actual_value=1.2,
                actual_unit="inch",
                resolution_source="test_fixture",
                resolved_at=datetime(2026, 5, 6, 2, tzinfo=timezone.utc),
            ),
            ResolvedOutcome(
                market_id=unmatched_outcome_market.id,
                actual_outcome="NO",
                actual_value=0.2,
                actual_unit="inch",
                resolution_source="test_fixture",
                resolved_at=datetime(2026, 5, 6, 3, tzinfo=timezone.utc),
            ),
            ResolvedOutcome(
                market_id=wrong_model_market.id,
                actual_outcome="YES",
                actual_value=1.3,
                actual_unit="inch",
                resolution_source="test_fixture",
                resolved_at=datetime(2026, 5, 6, 4, tzinfo=timezone.utc),
            ),
        ]
    )
    db_session.commit()

    result = BacktestRunner(db_session).run(
        BacktestRunRequest(start_date="2026-05-01", end_date="2026-05-10", model_version="baseline_precip_v1")
    )

    assert result.num_predictions == 1
    assert result.coverage_diagnostics.candidate_prediction_count == 2
    assert result.coverage_diagnostics.evaluated_prediction_count == 1
    assert result.coverage_diagnostics.missing_outcome_count == 1
    assert result.coverage_diagnostics.resolved_outcome_count_in_window == 3
    assert result.coverage_diagnostics.unmatched_resolved_outcome_count == 2
    assert result.coverage_diagnostics.excluded_prediction_model_version_count == 1


def test_backtest_runner_uses_one_latest_outcome_per_market(db_session: Session) -> None:
    market = Market(
        source="test",
        source_market_id="multiple-outcomes",
        question="Will New York City get more than 1 inch of rain on May 5?",
        category="weather",
        active=False,
        closed=True,
    )
    db_session.add(market)
    db_session.flush()
    prediction = Prediction(
        market_id=market.id,
        model_version="baseline_precip_v1",
        p_yes=0.8,
        p_no=0.2,
        confidence="medium",
    )
    db_session.add(prediction)
    db_session.flush()
    recommendation = EVRecommendation(
        prediction_id=prediction.id,
        market_price_yes=0.5,
        market_price_no=0.5,
        edge_yes=0.3,
        edge_no=-0.3,
        ev_yes=0.3,
        ev_no=-0.3,
        recommendation="PAPER_BUY_YES",
        paper_position_size=10.0,
    )
    db_session.add(recommendation)
    db_session.flush()
    db_session.add_all(
        [
            PaperTrade(
                market_id=market.id,
                recommendation_id=recommendation.id,
                side="YES",
                entry_price=0.5,
                quantity=10.0,
                entry_time=datetime(2026, 5, 5, 12, tzinfo=timezone.utc),
                status="OPEN",
            ),
            ResolvedOutcome(
                market_id=market.id,
                actual_outcome="NO",
                actual_value=0.3,
                actual_unit="inch",
                resolution_source="initial_review",
                resolved_at=datetime(2026, 5, 6, 2, tzinfo=timezone.utc),
            ),
            ResolvedOutcome(
                market_id=market.id,
                actual_outcome="YES",
                actual_value=1.2,
                actual_unit="inch",
                resolution_source="corrected_review",
                resolved_at=datetime(2026, 5, 6, 3, tzinfo=timezone.utc),
            ),
        ]
    )
    db_session.commit()

    result = BacktestRunner(db_session).run(
        BacktestRunRequest(start_date="2026-05-01", end_date="2026-05-10", model_version="baseline_precip_v1")
    )

    assert result.num_predictions == 1
    assert result.num_resolved_outcomes == 1
    assert result.ev_recommendation_count == 1
    assert result.paper_trade_count == 1
    assert result.win_rate == 1.0
    assert result.paper_total_pnl == 5.0
    assert result.coverage_diagnostics.evaluated_prediction_count == 1
    assert result.coverage_diagnostics.resolved_outcome_count_in_window == 2


def test_backtest_runner_applies_paper_fee_and_slippage_assumptions(db_session: Session) -> None:
    market = Market(
        source="test",
        source_market_id="paper-costs",
        question="Will New York City get more than 1 inch of rain on May 5?",
        category="weather",
        active=False,
        closed=True,
    )
    db_session.add(market)
    db_session.flush()
    prediction = Prediction(
        market_id=market.id,
        model_version="baseline_precip_v1",
        p_yes=0.75,
        p_no=0.25,
        confidence="medium",
    )
    db_session.add(prediction)
    db_session.flush()
    recommendation = EVRecommendation(
        prediction_id=prediction.id,
        market_price_yes=0.5,
        market_price_no=0.5,
        edge_yes=0.25,
        edge_no=-0.25,
        ev_yes=0.25,
        ev_no=-0.25,
        recommendation="PAPER_BUY_YES",
        paper_position_size=10.0,
    )
    db_session.add(recommendation)
    db_session.flush()
    db_session.add_all(
        [
            PaperTrade(
                market_id=market.id,
                recommendation_id=recommendation.id,
                side="YES",
                entry_price=0.5,
                quantity=10.0,
                entry_time=datetime(2026, 5, 5, 12, tzinfo=timezone.utc),
                status="OPEN",
            ),
            ResolvedOutcome(
                market_id=market.id,
                actual_outcome="YES",
                actual_value=1.1,
                actual_unit="inch",
                resolution_source="test_fixture",
                resolved_at=datetime(2026, 5, 6, 2, tzinfo=timezone.utc),
            ),
        ]
    )
    db_session.commit()

    result = BacktestRunner(db_session).run(
        BacktestRunRequest(
            start_date="2026-05-01",
            end_date="2026-05-10",
            paper_fee_rate=0.1,
            paper_slippage_rate=0.02,
        )
    )

    assert result.paper_gross_pnl == 5.0
    assert result.paper_slippage_cost == 0.2
    assert result.paper_fee_cost == 0.52
    assert result.paper_total_pnl == 4.28
    assert result.paper_roi == 0.748252
    assert "0.1000 fee rate" in result.paper_settlement_note
    assert "0.0200 entry slippage rate" in result.paper_settlement_note


def test_backtest_route_can_seed_fixture_replay(client: TestClient) -> None:
    response = client.post(
        "/backtests/run",
        json={
            "start_date": "2026-05-01",
            "end_date": "2026-05-10",
            "model_version": "baseline_precip_v1",
            "seed_fixtures": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["source"] == "seed_fixture"
    assert body["num_predictions"] == 3
    assert body["num_resolved_outcomes"] == 3
    assert body["ev_recommendation_count"] == 3
    assert body["paper_trade_count"] == 3
    assert body["win_rate"] == 0.666667
    assert body["brier_score"] == 0.194167
    assert body["paper_total_pnl"] == 5.8
    assert body["paper_roi"] == 0.408451
    assert body["max_drawdown"] == 4.5
    assert body["sample_size_note"] == "Very small sample; use metrics only to verify the replay workflow."
    assert body["sample_size_gate"] == "insufficient_sample"
    assert body["baseline_comparisons"][0]["name"] == "model_probability"
    assert body["coverage_diagnostics"]["candidate_prediction_count"] == 3
    assert body["coverage_diagnostics"]["evaluated_prediction_count"] == 3
    assert body["coverage_diagnostics"]["missing_outcome_count"] == 0
    assert body["coverage_diagnostics"]["resolved_outcome_count_in_window"] == 3
    assert body["coverage_diagnostics"]["unmatched_resolved_outcome_count"] == 0
    assert body["coverage_diagnostics"]["excluded_prediction_model_version_count"] == 0
    assert len(body["calibration_buckets"]) == 5
    assert body["calibration_buckets"][2]["count"] == 1
    assert body["calibration_buckets"][2]["average_predicted_probability"] == 0.4
    assert body["calibration_buckets"][2]["observed_yes_rate"] == 0.0
    assert body["calibration_buckets"][3]["count"] == 2
    assert body["calibration_buckets"][3]["average_predicted_probability"] == 0.675
    assert body["calibration_buckets"][3]["observed_yes_rate"] == 0.5


def test_walk_forward_backtest_slices_windows_and_aggregates_metrics(db_session: Session) -> None:
    first_market = Market(
        source="test",
        source_market_id="walk-forward-1",
        question="Will New York City get more than 1 inch of rain on May 1?",
        category="weather",
        active=False,
        closed=True,
    )
    second_market = Market(
        source="test",
        source_market_id="walk-forward-2",
        question="Will Chicago get less than 1 inch of rain on May 8?",
        category="weather",
        active=False,
        closed=True,
    )
    db_session.add_all([first_market, second_market])
    db_session.flush()
    first_prediction = Prediction(
        market_id=first_market.id,
        model_version="baseline_precip_v1",
        p_yes=0.75,
        p_no=0.25,
        confidence="medium",
    )
    second_prediction = Prediction(
        market_id=second_market.id,
        model_version="baseline_precip_v1",
        p_yes=0.25,
        p_no=0.75,
        confidence="medium",
    )
    db_session.add_all([first_prediction, second_prediction])
    db_session.flush()
    db_session.add_all(
        [
            EVRecommendation(
                prediction_id=first_prediction.id,
                market_price_yes=0.5,
                market_price_no=0.5,
                recommendation="PAPER_BUY_YES",
            ),
            EVRecommendation(
                prediction_id=second_prediction.id,
                market_price_yes=0.5,
                market_price_no=0.5,
                recommendation="WATCH",
            ),
            ResolvedOutcome(
                market_id=first_market.id,
                actual_outcome="YES",
                actual_value=1.3,
                actual_unit="inch",
                resolution_source="test_fixture",
                resolved_at=datetime(2026, 5, 2, 12, tzinfo=timezone.utc),
            ),
            ResolvedOutcome(
                market_id=second_market.id,
                actual_outcome="NO",
                actual_value=0.2,
                actual_unit="inch",
                resolution_source="test_fixture",
                resolved_at=datetime(2026, 5, 8, 12, tzinfo=timezone.utc),
            ),
        ]
    )
    db_session.commit()

    result = WalkForwardBacktestRunner(db_session).run(
        WalkForwardBacktestRequest(
            start_date="2026-05-01",
            end_date="2026-05-10",
            model_version="baseline_precip_v1",
            window_days=5,
            step_days=5,
        )
    )

    assert result.status == "completed"
    assert len(result.windows) == 2
    assert result.windows[0].start_date.isoformat() == "2026-05-01"
    assert result.windows[0].end_date.isoformat() == "2026-05-05"
    assert result.windows[0].backtest.num_predictions == 1
    assert result.windows[1].start_date.isoformat() == "2026-05-06"
    assert result.windows[1].end_date.isoformat() == "2026-05-10"
    assert result.windows[1].backtest.num_predictions == 1
    assert result.aggregate.window_count == 2
    assert result.aggregate.completed_window_count == 2
    assert result.aggregate.no_resolved_window_count == 0
    assert result.aggregate.total_evaluated_predictions == 2
    assert result.aggregate.total_resolved_outcomes == 2
    assert result.aggregate.total_ev_recommendations == 2
    assert result.aggregate.average_brier_score == 0.0625
    assert result.aggregate.average_win_rate == 1.0


def test_walk_forward_backtest_route_reports_empty_windows(client: TestClient, db_session: Session) -> None:
    market = Market(
        source="test",
        source_market_id="walk-forward-route-1",
        question="Will New York City get more than 1 inch of rain on May 5?",
        category="weather",
        active=False,
        closed=True,
    )
    db_session.add(market)
    db_session.flush()
    db_session.add_all(
        [
            Prediction(
                market_id=market.id,
                model_version="baseline_precip_v1",
                p_yes=0.8,
                p_no=0.2,
                confidence="medium",
            ),
            ResolvedOutcome(
                market_id=market.id,
                actual_outcome="YES",
                actual_value=1.4,
                actual_unit="inch",
                resolution_source="test_fixture",
                resolved_at=datetime(2026, 5, 8, 12, tzinfo=timezone.utc),
            ),
        ]
    )
    db_session.commit()

    response = client.post(
        "/backtests/walk-forward",
        json={
            "start_date": "2026-05-01",
            "end_date": "2026-05-10",
            "model_version": "baseline_precip_v1",
            "window_days": 5,
            "step_days": 5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["aggregate"]["window_count"] == 2
    assert body["aggregate"]["completed_window_count"] == 1
    assert body["aggregate"]["no_resolved_window_count"] == 1
    assert body["aggregate"]["total_evaluated_predictions"] == 1
    assert body["windows"][0]["backtest"]["status"] == "no_resolved_predictions"
    assert body["windows"][1]["backtest"]["status"] == "completed"
    assert "Some windows had no resolved predictions" in body["interpretation_limits"][-1]


def test_evidence_report_summarizes_backtest_and_limits(client: TestClient, db_session: Session) -> None:
    market = Market(
        source="test",
        source_market_id="evidence-report-1",
        question="Will New York City get more than 1 inch of rain on May 5?",
        category="weather",
    )
    db_session.add(market)
    db_session.flush()
    prediction = Prediction(market_id=market.id, model_version="baseline_precip_v1", p_yes=0.75, p_no=0.25)
    db_session.add(prediction)
    db_session.flush()
    recommendation = EVRecommendation(
        prediction_id=prediction.id,
        market_price_yes=0.5,
        market_price_no=0.5,
        recommendation="PAPER_BUY_YES",
    )
    db_session.add(recommendation)
    db_session.flush()
    db_session.add_all(
        [
            PaperTrade(
                market_id=market.id,
                recommendation_id=recommendation.id,
                side="YES",
                entry_price=0.5,
                quantity=2.0,
                status="OPEN",
            ),
            ResolvedOutcome(
                market_id=market.id,
                actual_outcome="YES",
                actual_value=1.1,
                actual_unit="inch",
                resolution_source="test_fixture",
                resolved_at=datetime(2026, 5, 6, 2, tzinfo=timezone.utc),
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/evaluation/evidence-report",
        params={"start_date": "2026-05-01", "end_date": "2026-05-10"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["sample_size_gate"] == "insufficient_sample"
    assert body["counts"]["predictions"] == 1
    assert body["counts"]["unresolved_paper_trades"] == 0
    assert body["paper_trade_lifecycle"]["recommended_buy_signals"] == 1
    assert body["paper_trade_lifecycle"]["recommended_but_not_traded"] == 0
    assert body["paper_trade_lifecycle"]["open"] == 1
    assert body["paper_trade_lifecycle"]["unresolved"] == 0
    assert body["market_implied_coverage"]["evaluated_prediction_count"] == 1
    assert body["market_implied_coverage"]["with_market_implied_count"] == 1
    assert body["market_implied_coverage"]["missing_market_implied_count"] == 0
    assert body["market_implied_coverage"]["coverage_ratio"] == 1.0
    assert body["backtest"]["baseline_comparisons"][1]["name"] == "always_50_percent"
    assert body["interpretation_limits"]


def test_evidence_report_includes_paper_trade_lifecycle_counts(client: TestClient, db_session: Session) -> None:
    markets: list[Market] = []
    recommendations: list[EVRecommendation] = []
    for index in range(4):
        market = Market(
            source="test",
            source_market_id=f"lifecycle-{index}",
            question="Will New York City get more than 1 inch of rain on May 5?",
            category="weather",
        )
        db_session.add(market)
        db_session.flush()
        prediction = Prediction(market_id=market.id, model_version="baseline_precip_v1", p_yes=0.7, p_no=0.3)
        db_session.add(prediction)
        db_session.flush()
        recommendation = EVRecommendation(
            prediction_id=prediction.id,
            market_price_yes=0.5,
            market_price_no=0.5,
            recommendation="PAPER_BUY_YES",
        )
        db_session.add(recommendation)
        db_session.flush()
        markets.append(market)
        recommendations.append(recommendation)

    expired_target_snapshot = {
        "parsed_target": {
            "target_start": "2026-05-05T00:00:00+00:00",
            "target_end": "2026-05-05T00:00:00+00:00",
        }
    }
    db_session.add_all(
        [
            PaperTrade(
                market_id=markets[0].id,
                recommendation_id=recommendations[0].id,
                side="YES",
                entry_price=0.5,
                quantity=2.0,
                status="OPEN",
                signal_snapshot_json=expired_target_snapshot,
            ),
            PaperTrade(
                market_id=markets[1].id,
                recommendation_id=recommendations[1].id,
                side="YES",
                entry_price=0.5,
                quantity=2.0,
                status="RESOLVED",
            ),
            PaperTrade(
                market_id=markets[2].id,
                recommendation_id=recommendations[2].id,
                side="YES",
                entry_price=0.5,
                quantity=2.0,
                status="CLOSED",
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/evaluation/evidence-report",
        params={"start_date": "2026-05-01", "end_date": "2026-05-10"},
    )

    assert response.status_code == 200
    lifecycle = response.json()["paper_trade_lifecycle"]
    assert lifecycle["recommended_buy_signals"] == 4
    assert lifecycle["recommended_but_not_traded"] == 1
    assert lifecycle["open"] == 1
    assert lifecycle["resolved"] == 1
    assert lifecycle["manually_closed"] == 1
    assert lifecycle["unresolved"] == 1
    assert lifecycle["unresolved_past_target_window"] == 1


def test_evidence_report_market_implied_coverage_reports_partial_sample(
    client: TestClient,
    db_session: Session,
) -> None:
    markets: list[Market] = []
    predictions: list[Prediction] = []
    for index in range(2):
        market = Market(
            source="test",
            source_market_id=f"market-implied-coverage-{index}",
            question="Will New York City get more than 1 inch of rain on May 5?",
            category="weather",
        )
        db_session.add(market)
        db_session.flush()
        prediction = Prediction(market_id=market.id, model_version="baseline_precip_v1", p_yes=0.7, p_no=0.3)
        db_session.add(prediction)
        db_session.flush()
        db_session.add(
            ResolvedOutcome(
                market_id=market.id,
                actual_outcome="YES",
                actual_value=1.2,
                actual_unit="inch",
                resolution_source="test_fixture",
                resolved_at=datetime(2026, 5, 6, 2, tzinfo=timezone.utc),
            )
        )
        markets.append(market)
        predictions.append(prediction)

    db_session.add(
        EVRecommendation(
            prediction_id=predictions[0].id,
            market_price_yes=0.5,
            market_price_no=0.5,
            recommendation="PAPER_BUY_YES",
        )
    )
    db_session.commit()

    response = client.get(
        "/evaluation/evidence-report",
        params={"start_date": "2026-05-01", "end_date": "2026-05-10"},
    )

    assert response.status_code == 200
    coverage = response.json()["market_implied_coverage"]
    assert coverage["evaluated_prediction_count"] == 2
    assert coverage["with_market_implied_count"] == 1
    assert coverage["missing_market_implied_count"] == 1
    assert coverage["coverage_ratio"] == 0.5
    assert coverage["missing_reason"] == "evaluated predictions lacked linked market YES prices"
    assert "Market-implied comparison covers only part of the evaluated prediction sample." in response.json()[
        "interpretation_limits"
    ]


def test_evidence_report_market_implied_coverage_reports_no_coverage(
    client: TestClient,
    db_session: Session,
) -> None:
    market = Market(
        source="test",
        source_market_id="market-implied-no-coverage",
        question="Will New York City get more than 1 inch of rain on May 5?",
        category="weather",
    )
    db_session.add(market)
    db_session.flush()
    db_session.add_all(
        [
            Prediction(market_id=market.id, model_version="baseline_precip_v1", p_yes=0.7, p_no=0.3),
            ResolvedOutcome(
                market_id=market.id,
                actual_outcome="YES",
                actual_value=1.2,
                actual_unit="inch",
                resolution_source="test_fixture",
                resolved_at=datetime(2026, 5, 6, 2, tzinfo=timezone.utc),
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/evaluation/evidence-report",
        params={"start_date": "2026-05-01", "end_date": "2026-05-10"},
    )

    assert response.status_code == 200
    coverage = response.json()["market_implied_coverage"]
    assert coverage["evaluated_prediction_count"] == 1
    assert coverage["with_market_implied_count"] == 0
    assert coverage["missing_market_implied_count"] == 1
    assert coverage["coverage_ratio"] == 0.0
    assert "No market-implied comparison was available" in response.json()["interpretation_limits"][-1]
