from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "paper_market_runner.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("paper_market_runner_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_args_keeps_one_shot_as_default() -> None:
    module = _load_script_module()

    args = module.parse_args([])

    assert args.interval_minutes is None
    assert args.max_hours is None
    assert args.max_runs is None
    assert args.max_trades == 3
    assert args.dry_run is False


def test_parse_args_requires_loop_bound() -> None:
    module = _load_script_module()

    with pytest.raises(SystemExit):
        module.parse_args(["--interval-minutes", "30"])


def test_parse_args_accepts_bounded_loop() -> None:
    module = _load_script_module()

    args = module.parse_args(["--interval-minutes", "30", "--max-hours", "10", "--max-runs", "20", "--dry-run"])

    assert args.interval_minutes == 30
    assert args.max_hours == 10
    assert args.max_runs == 20
    assert args.dry_run is True


def test_within_time_limit() -> None:
    module = _load_script_module()
    started_at = datetime(2026, 5, 9, 12, tzinfo=UTC)

    assert module._within_time_limit(started_at, None, started_at + timedelta(days=365)) is True
    assert module._within_time_limit(started_at, 10, started_at + timedelta(hours=9, minutes=59)) is True
    assert module._within_time_limit(started_at, 10, started_at + timedelta(hours=10)) is False
