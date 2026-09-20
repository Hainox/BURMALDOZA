import pytest
from burmaldoza_domain.economy import (
    CURRENCY_CODE,
    EconomyConfig,
    LedgerReason,
    validate_bet,
    validate_wallet_delta,
)


def test_jokergem_config_is_provisional_but_stable() -> None:
    config = EconomyConfig()

    assert CURRENCY_CODE == "JOKERGEM"
    assert config.welcome_grant == 1000
    assert config.daily_bonus == 250
    assert config.relief_grant == 300
    assert config.relief_threshold == 50
    assert config.daily_cooldown_seconds == 86400
    assert config.relief_cooldown_seconds == 259200


def test_wallet_delta_preserves_integer_non_negative_balance() -> None:
    assert validate_wallet_delta(100, -35) == 65
    assert validate_wallet_delta(100, 250) == 350

    with pytest.raises(ValueError, match="negative"):
        validate_wallet_delta(10, -11)


def test_bet_requires_balance_and_configured_limits() -> None:
    assert validate_bet(100, 25, 10, 100) == 25

    with pytest.raises(ValueError, match="between"):
        validate_bet(100, 5, 10, 100)
    with pytest.raises(ValueError, match="between"):
        validate_bet(100, 101, 10, 100)
    with pytest.raises(ValueError, match="insufficient"):
        validate_bet(20, 25, 10, 100)


def test_ledger_reasons_are_explicit() -> None:
    assert {reason.value for reason in LedgerReason} == {
        "welcome",
        "daily_bonus",
        "relief",
        "game_stake",
        "game_payout",
        "admin_adjustment",
    }
