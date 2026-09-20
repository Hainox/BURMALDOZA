import asyncio
from uuid import uuid4

import pytest
from app.db.models import Wallet
from app.services.wallet_service import WalletService
from burmaldoza_domain.core import InsufficientBalanceError
from burmaldoza_domain.economy import LedgerReason
from sqlalchemy import select


@pytest.mark.asyncio
async def test_concurrent_spends_never_make_balance_negative(session_factory) -> None:
    async with session_factory() as session:
        service = WalletService(session)
        await service.apply_delta(202, 100, LedgerReason.WELCOME, uuid4(), uuid4())

    async def spend() -> object:
        async with session_factory() as session:
            try:
                return await WalletService(session).apply_delta(
                    202, -80, LedgerReason.GAME_STAKE, uuid4(), uuid4()
                )
            except InsufficientBalanceError as error:
                return error

    results = await asyncio.gather(spend(), spend())
    assert sum(not isinstance(result, InsufficientBalanceError) for result in results) == 1

    async with session_factory() as session:
        wallet = await session.scalar(select(Wallet).where(Wallet.user_id == 202))
        assert wallet is not None
        assert wallet.balance == 20
        assert wallet.balance >= 0
