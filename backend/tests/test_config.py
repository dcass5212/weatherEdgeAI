import pytest
from pydantic import ValidationError

from app.config import Settings


def test_default_trading_mode_is_paper() -> None:
    settings = Settings(_env_file=None)

    assert settings.TRADING_MODE == "paper"
    assert settings.LIVE_TRADING_ENABLED is False
    assert settings.PAPER_RUNNER_ALLOW_INTERVAL_CONTRACTS is False
    assert settings.PAPER_RUNNER_ALLOW_STALE_PRICE_FALLBACK is False
    assert settings.live_execution_allowed is False


def test_live_flag_without_live_mode_does_not_allow_live_execution() -> None:
    settings = Settings(_env_file=None, TRADING_MODE="paper", LIVE_TRADING_ENABLED=True)

    assert settings.live_execution_allowed is False


def test_live_mode_requires_explicit_enable_flag() -> None:
    settings = Settings(_env_file=None, TRADING_MODE="live", LIVE_TRADING_ENABLED=False)

    assert settings.live_execution_allowed is False


def test_live_execution_requires_both_live_mode_and_enable_flag() -> None:
    settings = Settings(_env_file=None, TRADING_MODE="live", LIVE_TRADING_ENABLED=True)

    assert settings.live_execution_allowed is True


def test_invalid_trading_mode_fails_closed() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, TRADING_MODE="production")
