import asyncio
from uuid import uuid4

import pytest
from app.db.models import AdminAuditLog, LedgerEntry, User, Wallet
from app.services.admin_service import MAX_ADMIN_ADJUSTMENT, AdminError, AdminService
from sqlalchemy import func, select

ADMIN = 1001
PLAYER = 2002


async def seed(session_factory):
    async with session_factory() as session, session.begin():
        session.add(User(id=1, telegram_user_id=ADMIN, display_name="Admin", username="Boss"))
        session.add(
            User(id=2, telegram_user_id=PLAYER, display_name="Player", username="Lucky_One")
        )


def service(session):
    return AdminService(session, frozenset({ADMIN}))


@pytest.mark.asyncio
async def test_only_configured_admin_may_look_up_or_adjust(session_factory):
    await seed(session_factory)
    async with session_factory() as session:
        for call in (
            service(session).lookup(PLAYER, "@lucky_one"),
            service(session).adjust(PLAYER, PLAYER, 500, "", uuid4()),
        ):
            with pytest.raises(AdminError) as error:
                await call
            assert error.value.status == 403
    async with session_factory() as session:
        assert (await session.scalar(select(func.count()).select_from(LedgerEntry))) == 0


@pytest.mark.asyncio
async def test_lookup_by_case_insensitive_username_or_telegram_id(session_factory):
    await seed(session_factory)
    async with session_factory() as session:
        by_name = await service(session).lookup(ADMIN, "@LUCKY_one")
    async with session_factory() as session:
        by_id = await service(session).lookup(ADMIN, str(PLAYER))
        with pytest.raises(AdminError) as missing:
            await service(session).lookup(ADMIN, "@nobody")
    assert by_name.telegram_user_id == by_id.telegram_user_id == PLAYER
    assert by_name.balance == 0
    assert missing.value.status == 404


@pytest.mark.asyncio
async def test_grant_writes_ledger_and_audit_once_even_when_replayed(session_factory):
    await seed(session_factory)
    key = uuid4()
    async with session_factory() as session:
        first = await service(session).adjust(ADMIN, PLAYER, 5_000, "приз турнира", key)
    async with session_factory() as session:
        replay = await service(session).adjust(ADMIN, PLAYER, 5_000, "приз турнира", key)
    assert (first.balance_before, first.balance_after, first.replayed) == (0, 5_000, False)
    assert (replay.balance_after, replay.replayed) == (5_000, True)
    async with session_factory() as session:
        wallet = await session.get(Wallet, 2)
        entries = (
            (await session.execute(select(LedgerEntry).where(LedgerEntry.wallet_id == 2)))
            .scalars()
            .all()
        )
        audits = (await session.execute(select(AdminAuditLog))).scalars().all()
    assert wallet.balance == 5_000
    assert [(e.reason, e.amount_delta, e.balance_after) for e in entries] == [
        ("admin_adjustment", 5_000, 5_000)
    ]
    assert len(audits) == 1
    audit = audits[0]
    assert (audit.actor_id, audit.action, audit.target) == (1, "wallet.admin_adjustment", "user:2")
    assert audit.before_json == {"balance": 0}
    assert audit.after_json["balance"] == 5_000 and audit.after_json["comment"] == "приз турнира"


@pytest.mark.asyncio
async def test_take_cannot_go_below_zero_and_amount_is_capped(session_factory):
    await seed(session_factory)
    async with session_factory() as session:
        await service(session).adjust(ADMIN, PLAYER, 300, "", uuid4())
    async with session_factory() as session:
        with pytest.raises(AdminError) as insufficient:
            await service(session).adjust(ADMIN, PLAYER, -301, "", uuid4())
    async with session_factory() as session:
        taken = await service(session).adjust(ADMIN, PLAYER, -300, "", uuid4())
    for bad in (0, MAX_ADMIN_ADJUSTMENT + 1, -(MAX_ADMIN_ADJUSTMENT + 1)):
        async with session_factory() as session:
            with pytest.raises(AdminError) as invalid:
                await service(session).adjust(ADMIN, PLAYER, bad, "", uuid4())
            assert invalid.value.status == 422
    assert insufficient.value.status == 409
    assert taken.balance_after == 0
    async with session_factory() as session:
        assert (await session.get(Wallet, 2)).balance == 0
        assert (await session.scalar(select(func.count()).select_from(AdminAuditLog))) == 2


@pytest.mark.asyncio
async def test_ambiguous_username_is_refused(session_factory):
    await seed(session_factory)
    async with session_factory() as session, session.begin():
        # Прежний владелец ника не заходил после смены — в базе два игрока с одним username.
        session.add(User(id=3, telegram_user_id=3003, display_name="Old", username="lucky_one"))
    async with session_factory() as session:
        with pytest.raises(AdminError) as ambiguous:
            await service(session).lookup(ADMIN, "@Lucky_One")
    assert ambiguous.value.status == 409


@pytest.mark.asyncio
async def test_concurrent_confirmations_write_one_entry_and_one_audit(session_factory):
    await seed(session_factory)
    key = uuid4()

    async def confirm():
        async with session_factory() as session:
            return await service(session).adjust(ADMIN, PLAYER, 700, "", key)

    first, second = await asyncio.gather(confirm(), confirm())
    assert sorted([first.replayed, second.replayed]) == [False, True]
    async with session_factory() as session:
        assert (await session.get(Wallet, 2)).balance == 700
        assert (await session.scalar(select(func.count()).select_from(LedgerEntry))) == 1
        assert (await session.scalar(select(func.count()).select_from(AdminAuditLog))) == 1
