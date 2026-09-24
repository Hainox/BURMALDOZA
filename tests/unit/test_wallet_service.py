from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from burmaldoza_domain.core import InsufficientBalanceError
from burmaldoza_domain.economy import LedgerReason

from apps.api.app.services.wallet_service import (
    CooldownError,
    MemoryWalletStore,
    WalletService,
    WalletServiceError,
)


@pytest.mark.asyncio
async def test_starter_daily_and_relief_grants_follow_configured_values() -> None:
    store = MemoryWalletStore()
    service = WalletService(store=store)
    now = datetime(2026, 9, 20, 12, tzinfo=UTC)

    welcome = await service.claim_welcome_grant(1, uuid4())
    daily = await service.claim_daily_bonus(1, now, uuid4())
    relief = await service.claim_relief_grant(2, now, uuid4())

    assert welcome.balance_after == 1000
    assert daily.balance_after == 1250
    assert relief.balance_after == 300
    assert (await service.get_or_create(1)).balance == 1250

    with pytest.raises(CooldownError, match="daily"):
        await service.claim_daily_bonus(1, now + timedelta(hours=23), uuid4())
    await service.apply_delta(2, -300, LedgerReason.GAME_STAKE, uuid4(), uuid4())
    with pytest.raises(CooldownError, match="relief"):
        await service.claim_relief_grant(2, now + timedelta(hours=1), uuid4())


@pytest.mark.asyncio
async def test_positive_and_negative_deltas_preserve_non_negative_balance() -> None:
    store = MemoryWalletStore()
    service = WalletService(store=store)
    user_id = 5

    await service.claim_welcome_grant(user_id, uuid4())
    debit = await service.apply_delta(user_id, -125, LedgerReason.GAME_STAKE, uuid4(), uuid4())
    credit = await service.apply_delta(user_id, 50, LedgerReason.GAME_PAYOUT, uuid4(), uuid4())

    assert debit.balance_after == 875
    assert credit.balance_after == 925
    with pytest.raises(InsufficientBalanceError):
        await service.apply_delta(user_id, -1000, LedgerReason.GAME_STAKE, uuid4(), uuid4())
    assert (await service.get_or_create(user_id)).balance == 925


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_replays_one_operation_and_one_ledger_entry() -> None:
    store = MemoryWalletStore()
    service = WalletService(store=store)
    operation_key = uuid4()
    reference_id = uuid4()

    first = await service.apply_delta(7, 100, LedgerReason.WELCOME, reference_id, operation_key)
    replay = await service.apply_delta(7, 100, LedgerReason.WELCOME, reference_id, operation_key)

    assert replay == first
    assert (await service.get_or_create(7)).balance == 100
    assert store.operation_count == 1
    assert store.ledger_entry_count == 1


@pytest.mark.asyncio
async def test_game_settlement_uses_one_operation_with_stake_and_payout_entries() -> None:
    store = MemoryWalletStore()
    service = WalletService(store=store)
    await service.claim_welcome_grant(9, uuid4())

    result = await service.settle_game_round(9, uuid4(), stake=100, payout=250, idempotency_key=uuid4())

    assert result.stake == 100
    assert result.payout == 250
    assert result.net_delta == 150
    assert result.balance_after == 1150
    assert len(result.entries) == 2
    assert store.operation_count == 2
    assert store.ledger_entry_count == 3


@pytest.mark.asyncio
async def test_idempotency_key_of_another_wallet_is_rejected_not_replayed() -> None:
    store = MemoryWalletStore()
    service = WalletService(store=store)
    now = datetime(2026, 9, 20, 12, tzinfo=UTC)
    shared_key = uuid4()

    await service.claim_daily_bonus(1, now, shared_key)

    with pytest.raises(WalletServiceError, match="another wallet"):
        await service.claim_daily_bonus(2, now, shared_key)
    assert (await service.get_or_create(2)).balance == 0
    assert store.operation_count == 1
