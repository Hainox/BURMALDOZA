from uuid import uuid4

import pytest
from app.db.models import LedgerEntry, User, WalletOperation
from app.services.wallet_service import WalletService
from burmaldoza_domain.economy import LedgerReason
from sqlalchemy import func, select


@pytest.mark.asyncio
async def test_duplicate_wallet_mutation_creates_one_operation_and_one_entry(session_factory) -> None:
    key = uuid4()
    async with session_factory() as session:
        session.add(User(id=101, telegram_user_id=101, display_name="Wallet User"))
        await session.commit()
        service = WalletService(session)
        first = await service.apply_delta(101, 100, LedgerReason.WELCOME, uuid4(), key)
        replay = await service.apply_delta(101, 100, LedgerReason.WELCOME, uuid4(), key)

        assert replay == first

        operations = await session.scalar(select(func.count(WalletOperation.id)))
        entries = await session.scalar(select(func.count(LedgerEntry.id)))
        assert operations == 1
        assert entries == 1
