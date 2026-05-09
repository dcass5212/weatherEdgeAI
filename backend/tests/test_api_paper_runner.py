from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import routes_paper_runner
from app.db.models import Market, PaperRunnerRun, utc_now
from app.strategy.paper_market_runner import PaperMarketRunnerConfig


async def _fake_recorded_run(db: Session, config: PaperMarketRunnerConfig) -> PaperRunnerRun:
    run = PaperRunnerRun(
        status="completed",
        source=config.source,
        started_at=utc_now(),
        completed_at=utc_now(),
        config_json={
            "source": config.source,
            "keywords": config.keywords,
            "discovery_limit": config.discovery_limit,
            "process_limit": config.process_limit,
            "max_trades": config.max_trades,
            "quantity": config.quantity,
            "min_liquidity": config.min_liquidity,
            "max_spread": config.max_spread,
            "refresh_prices": config.refresh_prices,
            "create_trades": config.create_trades,
        },
        discovered=2,
        created=1,
        updated=1,
        price_snapshots_created=2,
        processed=2,
        parsed=1,
        forecasts_created=1,
        predictions_created=1,
        recommendations_created=1,
        paper_trades_created=0,
        skipped_json={"trade_creation_disabled": 1},
        errors_json=[],
        report_json={"discovered": 2, "paper_trades_created": 0},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def test_run_paper_runner_once_returns_persisted_run(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(routes_paper_runner, "run_paper_market_once_recorded", _fake_recorded_run)

    response = client.post(
        "/paper-runner/run-once",
        json={
            "keywords": ["rain"],
            "dry_run": True,
            "max_trades": 1,
            "quantity": 1,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "completed"
    assert data["config"]["keywords"] == ["rain"]
    assert data["config"]["create_trades"] is False
    assert data["discovered"] == 2
    assert data["paper_trades_created"] == 0
    assert data["skipped"] == {"trade_creation_disabled": 1}


def test_list_and_get_paper_runner_runs(client: TestClient, db_session: Session) -> None:
    run = PaperRunnerRun(
        status="completed",
        source="polymarket",
        started_at=utc_now(),
        completed_at=utc_now(),
        config_json={"source": "polymarket"},
        discovered=1,
        skipped_json={},
        errors_json=[],
        report_json={"discovered": 1},
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    list_response = client.get("/paper-runner/runs")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == run.id

    get_response = client.get(f"/paper-runner/runs/{run.id}")
    assert get_response.status_code == 200
    assert get_response.json()["report"] == {"discovered": 1}

    missing_response = client.get("/paper-runner/runs/999")
    assert missing_response.status_code == 404


def test_paper_runner_diagnostics_summarizes_runs_and_source_diagnostics(
    client: TestClient,
    db_session: Session,
) -> None:
    first_run = PaperRunnerRun(
        status="completed",
        source="polymarket",
        started_at=utc_now(),
        completed_at=utc_now(),
        config_json={"source": "polymarket"},
        discovered=5,
        processed=4,
        parsed=1,
        forecasts_created=1,
        predictions_created=1,
        recommendations_created=1,
        paper_trades_created=0,
        skipped_json={
            "missing_binary_prices": 2,
            "parse_failed": 1,
            "price_refresh_failed_used_stored_snapshot": 1,
        },
        errors_json=["market_id=7: provider timeout"],
        report_json={"processed": 4},
    )
    second_run = PaperRunnerRun(
        status="completed",
        source="polymarket",
        started_at=utc_now(),
        completed_at=utc_now(),
        config_json={"source": "polymarket"},
        discovered=3,
        processed=2,
        parsed=0,
        forecasts_created=0,
        predictions_created=0,
        recommendations_created=0,
        paper_trades_created=0,
        skipped_json={"missing_coordinates": 2, "spread_above_max": 1},
        errors_json=[],
        report_json={"processed": 2},
    )
    supported_market = Market(
        source="polymarket",
        source_market_id="supported",
        condition_id="condition-supported",
        question="Will New York City get more than 1 inch of rain tomorrow?",
        active=True,
        closed=False,
        source_diagnostics={"price_status": "supported", "unsupported_reasons": []},
    )
    partial_market = Market(
        source="polymarket",
        source_market_id="partial",
        condition_id="condition-partial",
        question="Will Chicago get more than 1 inch of rain tomorrow?",
        active=True,
        closed=False,
        source_diagnostics={
            "price_status": "partial",
            "unsupported_reasons": ["non_binary_outcomes", "missing_binary_yes_no_prices"],
        },
    )
    db_session.add_all([first_run, second_run, supported_market, partial_market])
    db_session.commit()

    response = client.get("/paper-runner/diagnostics")

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "polymarket"
    assert data["run_count"] == 2
    assert data["discovered"] == 8
    assert data["processed"] == 6
    assert data["parsed"] == 1
    assert data["recommendations_created"] == 1
    assert data["price_status_counts"] == {"partial": 1, "supported": 1}
    assert data["unsupported_price_reasons"] == [
        {"reason": "missing_binary_yes_no_prices", "count": 1},
        {"reason": "non_binary_outcomes", "count": 1},
    ]
    assert {"reason": "missing_binary_prices", "count": 2, "category": "price_data", "label": "Missing binary YES/NO prices"} in data[
        "skip_reasons"
    ]
    assert {"reason": "missing_coordinates", "count": 2, "category": "geocoding", "label": "Parsed location has no coordinates"} in data[
        "skip_reasons"
    ]
    assert data["error_count"] == 1
    assert data["recent_errors"] == [{"run_id": first_run.id, "message": "market_id=7: provider timeout"}]
