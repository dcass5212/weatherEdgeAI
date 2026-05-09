from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, create_engine

from app.config import settings


def test_alembic_upgrade_head_creates_current_schema(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "migration.db"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)

    backend_dir = Path(__file__).resolve().parents[1]
    alembic_config = Config(str(backend_dir / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(backend_dir / "migrations"))

    command.upgrade(alembic_config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)

    assert {
        "markets",
        "parsed_markets",
        "market_price_snapshots",
        "weather_forecast_snapshots",
        "predictions",
        "ev_recommendations",
        "paper_trades",
        "paper_runner_runs",
        "resolved_outcomes",
        "alembic_version",
    }.issubset(set(inspector.get_table_names()))
    market_columns = {column["name"] for column in inspector.get_columns("markets")}
    assert "source_diagnostics" in market_columns
