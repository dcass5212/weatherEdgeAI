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
from app.backtesting.schemas import BacktestRunRequest
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
    assert result.paper_total_pnl == 5.0
    assert result.paper_roi == 1.0
    assert result.max_drawdown == 0.0
    assert result.sample_size_note == "Very small sample; use metrics only to verify the replay workflow."
    assert result.calibration_buckets[3].count == 1
    assert result.calibration_buckets[3].average_predicted_probability == 0.75
    assert result.calibration_buckets[3].observed_yes_rate == 1.0


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
