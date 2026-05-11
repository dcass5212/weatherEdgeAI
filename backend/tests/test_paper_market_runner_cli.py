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
    assert args.rehearsal is False
    assert args.allow_interval_contracts is None
    assert args.max_price_age_minutes is None
    assert args.max_forecast_age_hours is None
    assert args.max_open_trades is None
    assert args.max_total_exposure is None
    assert args.max_market_exposure is None
    assert args.max_location_exposure is None
    assert args.entry_slippage_rate is None
    assert args.allow_stale_price_fallback is False
    assert args.require_fresh_prices is False


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


def test_parse_args_rehearsal_enables_dry_run() -> None:
    module = _load_script_module()

    args = module.parse_args(["--rehearsal"])

    assert args.rehearsal is True
    assert args.dry_run is True


def test_parse_args_accepts_interval_contract_opt_in() -> None:
    module = _load_script_module()

    args = module.parse_args(["--allow-interval-contracts"])

    assert args.allow_interval_contracts is True


def test_parse_args_accepts_interval_contract_opt_out() -> None:
    module = _load_script_module()

    args = module.parse_args(["--disable-interval-contracts"])

    assert args.allow_interval_contracts is False


def test_parse_args_accepts_freshness_overrides() -> None:
    module = _load_script_module()

    args = module.parse_args(["--max-price-age-minutes", "45", "--max-forecast-age-hours", "6"])
    config = module._config_from_args(args)

    assert args.max_price_age_minutes == 45
    assert args.max_forecast_age_hours == 6
    assert config.max_price_age_minutes == 45
    assert config.max_forecast_age_hours == 6


def test_parse_args_accepts_portfolio_limit_overrides() -> None:
    module = _load_script_module()

    args = module.parse_args(
        [
            "--max-open-trades",
            "2",
            "--max-total-exposure",
            "10",
            "--max-market-exposure",
            "3",
            "--max-location-exposure",
            "6",
        ]
    )
    config = module._config_from_args(args)

    assert config.max_open_trades == 2
    assert config.max_total_exposure == 10
    assert config.max_market_exposure == 3
    assert config.max_location_exposure == 6


def test_parse_args_accepts_entry_slippage_override() -> None:
    module = _load_script_module()

    args = module.parse_args(["--entry-slippage-rate", "0.02"])
    config = module._config_from_args(args)

    assert config.entry_slippage_rate == 0.02


def test_parse_args_accepts_stale_price_fallback_override() -> None:
    module = _load_script_module()

    args = module.parse_args(["--allow-stale-price-fallback"])
    config = module._config_from_args(args)

    assert args.allow_stale_price_fallback is True
    assert config.allow_stale_price_fallback is True


def test_parse_args_rejects_conflicting_stale_price_fallback_flags() -> None:
    module = _load_script_module()

    with pytest.raises(SystemExit):
        module.parse_args(["--allow-stale-price-fallback", "--require-fresh-prices"])


def test_parse_args_rejects_negative_freshness_overrides() -> None:
    module = _load_script_module()

    with pytest.raises(SystemExit):
        module.parse_args(["--max-price-age-minutes", "-1"])
    with pytest.raises(SystemExit):
        module.parse_args(["--max-forecast-age-hours", "-1"])


def test_parse_args_rejects_negative_portfolio_limit_overrides() -> None:
    module = _load_script_module()

    for option in (
        "--max-open-trades",
        "--max-total-exposure",
        "--max-market-exposure",
        "--max-location-exposure",
    ):
        with pytest.raises(SystemExit):
            module.parse_args([option, "-1"])


def test_parse_args_rejects_invalid_entry_slippage() -> None:
    module = _load_script_module()

    with pytest.raises(SystemExit):
        module.parse_args(["--entry-slippage-rate", "-0.01"])
    with pytest.raises(SystemExit):
        module.parse_args(["--entry-slippage-rate", "1.01"])


def test_within_time_limit() -> None:
    module = _load_script_module()
    started_at = datetime(2026, 5, 9, 12, tzinfo=UTC)

    assert module._within_time_limit(started_at, None, started_at + timedelta(days=365)) is True
    assert module._within_time_limit(started_at, 10, started_at + timedelta(hours=9, minutes=59)) is True
    assert module._within_time_limit(started_at, 10, started_at + timedelta(hours=10)) is False
