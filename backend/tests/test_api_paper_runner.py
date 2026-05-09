from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import routes_paper_runner
from app.db.models import PaperRunnerRun, utc_now
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
