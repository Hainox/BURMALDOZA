from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from burmaldoza_contracts.wallet import WalletSnapshot
from burmaldoza_domain.economy import (
    CURRENCY_CODE,
    EconomyConfig,
    LedgerReason,
    validate_wallet_delta,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LedgerEntry, User, Wallet, WalletOperation


class WalletServiceError(ValueError):
    """Base application error for wallet operations."""


class CooldownError(WalletServiceError):
    """Raised when a faucet grant is still cooling down."""


class GrantAlreadyClaimedError(WalletServiceError):
    """Raised when a one-time welcome grant was already claimed."""


class ReliefUnavailableError(WalletServiceError):
    """Raised when relief is not available at the current balance."""


@dataclass(frozen=True, slots=True)
class LedgerEntryResult:
    id: UUID
    operation_id: UUID
    amount_delta: int
    balance_after: int
    reason: LedgerReason
    reference_id: UUID | None


@dataclass(frozen=True, slots=True)
class LedgerResult:
    operation_id: UUID
    idempotency_key: UUID
    user_id: int
    delta: int
    balance_after: int
    reason: LedgerReason
    reference_id: UUID | None
    entries: tuple[LedgerEntryResult, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SettlementResult:
    operation_id: UUID
    idempotency_key: UUID
    user_id: int
    stake: int
    payout: int
    net_delta: int
    balance_after: int
    entries: tuple[LedgerEntryResult, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class _MemoryWallet:
    user_id: int
    balance: int = 0
    version: int = 0
    welcome_granted_at: datetime | None = None
    daily_bonus_at: datetime | None = None
    relief_grant_at: datetime | None = None


class MemoryWalletStore:
    """Small deterministic store used by unit tests, not by production requests."""

    def __init__(self) -> None:
        self.wallets: dict[int, _MemoryWallet] = {}
        self.operations: dict[UUID, LedgerResult | SettlementResult] = {}
        self.ledger_entry_count = 0
        self.lock = asyncio.Lock()

    @property
    def operation_count(self) -> int:
        return len(self.operations)

    def get_wallet(self, user_id: int) -> _MemoryWallet:
        return self.wallets.setdefault(user_id, _MemoryWallet(user_id=user_id))


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class WalletService:
    def __init__(
        self,
        session: AsyncSession | None = None,
        *,
        store: MemoryWalletStore | None = None,
        economy: EconomyConfig | None = None,
    ) -> None:
        if (session is None) == (store is None):
            raise ValueError("provide exactly one of session or store")
        self.session = session
        self.store = store
        self.economy = economy or EconomyConfig()

    def _snapshot(self, wallet: _MemoryWallet) -> WalletSnapshot:
        return WalletSnapshot(
            user_id=wallet.user_id,
            balance=wallet.balance,
            currency_code=CURRENCY_CODE,
            version=wallet.version,
        )

    async def get_or_create(self, user_id: int) -> WalletSnapshot:
        if self.store is not None:
            async with self.store.lock:
                return self._snapshot(self.store.get_wallet(user_id))
        assert self.session is not None
        async with self.session.begin():
            wallet = await self._db_get_or_create_wallet(user_id, lock=True)
            return self._db_snapshot(wallet)

    async def apply_delta(
        self,
        user_id: int,
        delta: int,
        reason: LedgerReason,
        reference_id: UUID,
        idempotency_key: UUID,
    ) -> LedgerResult:
        if self.store is not None:
            async with self.store.lock:
                return self._memory_apply_delta(user_id, delta, reason, reference_id, idempotency_key)
        assert self.session is not None
        async with self.session.begin():
            wallet = await self._db_get_or_create_wallet(user_id, lock=True)
            existing = await self._db_replay(idempotency_key)
            if existing is not None:
                if not isinstance(existing, LedgerResult):
                    raise WalletServiceError("idempotency key belongs to another operation")
                return existing
            return await self._db_apply_delta(wallet, delta, reason, reference_id, idempotency_key)

    async def claim_welcome_grant(self, user_id: int, idempotency_key: UUID) -> LedgerResult:
        if self.store is not None:
            async with self.store.lock:
                wallet = self.store.get_wallet(user_id)
                replay = self.store.operations.get(idempotency_key)
                if replay is not None:
                    return self._as_ledger_result(replay)
                if wallet.welcome_granted_at is not None:
                    raise GrantAlreadyClaimedError("welcome grant already claimed")
                result = self._memory_apply_delta_locked(
                    wallet, self.economy.welcome_grant, LedgerReason.WELCOME, None, idempotency_key
                )
                wallet.welcome_granted_at = datetime.now(UTC)
                return result
        assert self.session is not None
        async with self.session.begin():
            wallet = await self._db_get_or_create_wallet(user_id, lock=True)
            existing = await self._db_replay(idempotency_key)
            if existing is not None:
                return self._as_ledger_result(existing)
            if wallet.welcome_granted_at is not None:
                raise GrantAlreadyClaimedError("welcome grant already claimed")
            result = await self._db_apply_delta(
                wallet, self.economy.welcome_grant, LedgerReason.WELCOME, None, idempotency_key
            )
            wallet.welcome_granted_at = datetime.now(UTC)
            return result

    async def claim_daily_bonus(
        self, user_id: int, now: datetime, idempotency_key: UUID
    ) -> LedgerResult:
        now = _utc(now)
        if self.store is not None:
            async with self.store.lock:
                wallet = self.store.get_wallet(user_id)
                replay = self.store.operations.get(idempotency_key)
                if replay is not None:
                    return self._as_ledger_result(replay)
                self._check_cooldown(wallet.daily_bonus_at, now, self.economy.daily_cooldown_seconds, "daily")
                result = self._memory_apply_delta_locked(
                    wallet, self.economy.daily_bonus, LedgerReason.DAILY_BONUS, None, idempotency_key
                )
                wallet.daily_bonus_at = now
                return result
        assert self.session is not None
        async with self.session.begin():
            wallet = await self._db_get_or_create_wallet(user_id, lock=True)
            existing = await self._db_replay(idempotency_key)
            if existing is not None:
                return self._as_ledger_result(existing)
            self._check_cooldown(wallet.daily_bonus_at, now, self.economy.daily_cooldown_seconds, "daily")
            result = await self._db_apply_delta(
                wallet, self.economy.daily_bonus, LedgerReason.DAILY_BONUS, None, idempotency_key
            )
            wallet.daily_bonus_at = now
            return result

    async def claim_relief_grant(
        self, user_id: int, now: datetime, idempotency_key: UUID
    ) -> LedgerResult:
        now = _utc(now)
        if self.store is not None:
            async with self.store.lock:
                wallet = self.store.get_wallet(user_id)
                replay = self.store.operations.get(idempotency_key)
                if replay is not None:
                    return self._as_ledger_result(replay)
                if wallet.balance >= self.economy.relief_threshold:
                    raise ReliefUnavailableError("relief is available only below the balance threshold")
                self._check_cooldown(wallet.relief_grant_at, now, self.economy.relief_cooldown_seconds, "relief")
                result = self._memory_apply_delta_locked(
                    wallet, self.economy.relief_grant, LedgerReason.RELIEF, None, idempotency_key
                )
                wallet.relief_grant_at = now
                return result
        assert self.session is not None
        async with self.session.begin():
            wallet = await self._db_get_or_create_wallet(user_id, lock=True)
            existing = await self._db_replay(idempotency_key)
            if existing is not None:
                return self._as_ledger_result(existing)
            if wallet.balance >= self.economy.relief_threshold:
                raise ReliefUnavailableError("relief is available only below the balance threshold")
            self._check_cooldown(wallet.relief_grant_at, now, self.economy.relief_cooldown_seconds, "relief")
            result = await self._db_apply_delta(
                wallet, self.economy.relief_grant, LedgerReason.RELIEF, None, idempotency_key
            )
            wallet.relief_grant_at = now
            return result

    async def settle_game_round(
        self,
        user_id: int,
        round_id: UUID,
        stake: int,
        payout: int,
        idempotency_key: UUID,
    ) -> SettlementResult:
        if stake < 0 or payout < 0:
            raise ValueError("stake and payout must be non-negative")
        if self.store is not None:
            async with self.store.lock:
                existing = self.store.operations.get(idempotency_key)
                if existing is not None:
                    return self._as_settlement_result(existing)
                wallet = self.store.get_wallet(user_id)
                result = self._memory_settle_locked(wallet, round_id, stake, payout, idempotency_key)
                self.store.operations[idempotency_key] = result
                self.store.ledger_entry_count += len(result.entries)
                return result
        assert self.session is not None
        async with self.session.begin():
            wallet = await self._db_get_or_create_wallet(user_id, lock=True)
            existing = await self._db_replay(idempotency_key)
            if existing is not None:
                return self._as_settlement_result(existing)
            return await self._db_settle(wallet, round_id, stake, payout, idempotency_key)

    @staticmethod
    def _check_cooldown(
        last_claim: datetime | None, now: datetime, cooldown_seconds: int, label: str
    ) -> None:
        if last_claim is not None and now - _utc(last_claim) < timedelta(seconds=cooldown_seconds):
            raise CooldownError(f"{label} bonus is on cooldown")

    def _memory_apply_delta(
        self, user_id: int, delta: int, reason: LedgerReason, reference_id: UUID | None, key: UUID
    ) -> LedgerResult:
        wallet = self.store.get_wallet(user_id)  # type: ignore[union-attr]
        existing = self.store.operations.get(key)  # type: ignore[union-attr]
        if existing is not None:
            return self._as_ledger_result(existing)
        return self._memory_apply_delta_locked(wallet, delta, reason, reference_id, key)

    def _memory_apply_delta_locked(
        self, wallet: _MemoryWallet, delta: int, reason: LedgerReason, reference_id: UUID | None, key: UUID
    ) -> LedgerResult:
        new_balance = validate_wallet_delta(wallet.balance, delta)
        operation_id = uuid4()
        entry = LedgerEntryResult(uuid4(), operation_id, delta, new_balance, reason, reference_id)
        result = LedgerResult(operation_id, key, wallet.user_id, delta, new_balance, reason, reference_id, (entry,))
        wallet.balance = new_balance
        wallet.version += 1
        self.store.operations[key] = result  # type: ignore[union-attr]
        self.store.ledger_entry_count += 1  # type: ignore[union-attr]
        return result

    def _memory_settle_locked(
        self, wallet: _MemoryWallet, round_id: UUID, stake: int, payout: int, key: UUID
    ) -> SettlementResult:
        balance = validate_wallet_delta(wallet.balance, -stake)
        entries: list[LedgerEntryResult] = []
        operation_id = uuid4()
        if stake:
            entries.append(LedgerEntryResult(uuid4(), operation_id, -stake, balance, LedgerReason.GAME_STAKE, round_id))
        if payout:
            balance = validate_wallet_delta(balance, payout)
            entries.append(LedgerEntryResult(uuid4(), operation_id, payout, balance, LedgerReason.GAME_PAYOUT, round_id))
        wallet.balance = balance
        wallet.version += 1
        return SettlementResult(operation_id, key, wallet.user_id, stake, payout, payout - stake, balance, tuple(entries))

    @staticmethod
    def _as_ledger_result(result: LedgerResult | SettlementResult) -> LedgerResult:
        if isinstance(result, LedgerResult):
            return result
        raise WalletServiceError("idempotency key belongs to a game settlement")

    @staticmethod
    def _as_settlement_result(result: LedgerResult | SettlementResult) -> SettlementResult:
        if isinstance(result, SettlementResult):
            return result
        raise WalletServiceError("idempotency key belongs to another wallet operation")

    @staticmethod
    def _db_snapshot(wallet: Wallet) -> WalletSnapshot:
        return WalletSnapshot(
            user_id=wallet.user_id,
            balance=wallet.balance,
            currency_code=CURRENCY_CODE,
            version=wallet.version,
        )

    async def _db_get_or_create_wallet(self, user_id: int, *, lock: bool) -> Wallet:
        assert self.session is not None
        query = select(Wallet).where(Wallet.user_id == user_id)
        if lock:
            query = query.with_for_update()
        wallet = (await self.session.execute(query)).scalar_one_or_none()
        if wallet is None:
            user = await self.session.get(User, user_id)
            if user is None:
                self.session.add(User(id=user_id, telegram_user_id=user_id, display_name=str(user_id)))
                await self.session.flush()
            wallet = Wallet(user_id=user_id, balance=0, version=0)
            self.session.add(wallet)
            await self.session.flush()
        return wallet

    async def _db_replay(self, key: UUID) -> LedgerResult | SettlementResult | None:
        assert self.session is not None
        operation = (
            await self.session.execute(select(WalletOperation).where(WalletOperation.idempotency_key == key))
        ).scalar_one_or_none()
        if operation is None:
            return None
        entries = tuple(
            
                LedgerEntryResult(
                    id=entry.id,
                    operation_id=entry.operation_id,
                    amount_delta=entry.amount_delta,
                    balance_after=entry.balance_after,
                    reason=LedgerReason(entry.reason),
                    reference_id=entry.reference_id,
                )
                for entry in (
                    await self.session.execute(
                        select(LedgerEntry)
                        .where(LedgerEntry.operation_id == operation.id)
                        .order_by(LedgerEntry.created_at, LedgerEntry.id)
                    )
                ).scalars()
            
        )
        balance_after = entries[-1].balance_after if entries else 0
        if operation.operation_type == "game_settlement":
            stake = abs(next((entry.amount_delta for entry in entries if entry.reason is LedgerReason.GAME_STAKE), 0))
            payout = next((entry.amount_delta for entry in entries if entry.reason is LedgerReason.GAME_PAYOUT), 0)
            return SettlementResult(
                operation_id=operation.id,
                idempotency_key=operation.idempotency_key,
                user_id=operation.wallet_id,
                stake=stake,
                payout=payout,
                net_delta=payout - stake,
                balance_after=balance_after,
                entries=entries,
            )
        first = entries[0] if entries else None
        return LedgerResult(
            operation_id=operation.id,
            idempotency_key=operation.idempotency_key,
            user_id=operation.wallet_id,
            delta=sum(entry.amount_delta for entry in entries),
            balance_after=balance_after,
            reason=first.reason if first else LedgerReason.ADMIN_ADJUSTMENT,
            reference_id=first.reference_id if first else operation.reference_id,
            entries=entries,
        )

    async def _db_apply_delta(
        self, wallet: Wallet, delta: int, reason: LedgerReason, reference_id: UUID | None, key: UUID
    ) -> LedgerResult:
        assert self.session is not None
        new_balance = validate_wallet_delta(wallet.balance, delta)
        operation = WalletOperation(
            wallet_id=wallet.user_id,
            operation_type="delta",
            idempotency_key=key,
            reference_type=reason.value,
            reference_id=reference_id,
        )
        self.session.add(operation)
        await self.session.flush()
        entry = LedgerEntry(
            operation_id=operation.id,
            wallet_id=wallet.user_id,
            amount_delta=delta,
            balance_after=new_balance,
            reason=reason.value,
            reference_type=reason.value,
            reference_id=reference_id,
        )
        self.session.add(entry)
        wallet.balance = new_balance
        wallet.version += 1
        await self.session.flush()
        return LedgerResult(
            operation.id,
            key,
            wallet.user_id,
            delta,
            new_balance,
            reason,
            reference_id,
            (LedgerEntryResult(entry.id, operation.id, delta, new_balance, reason, reference_id),),
        )

    async def _db_settle(
        self, wallet: Wallet, round_id: UUID, stake: int, payout: int, key: UUID
    ) -> SettlementResult:
        assert self.session is not None
        balance = validate_wallet_delta(wallet.balance, -stake)
        operation = WalletOperation(
            wallet_id=wallet.user_id,
            operation_type="game_settlement",
            idempotency_key=key,
            reference_type="game_round",
            reference_id=round_id,
        )
        self.session.add(operation)
        await self.session.flush()
        entries: list[LedgerEntryResult] = []
        if stake:
            debit = LedgerEntry(
                operation_id=operation.id,
                wallet_id=wallet.user_id,
                amount_delta=-stake,
                balance_after=balance,
                reason=LedgerReason.GAME_STAKE.value,
                reference_type="game_round",
                reference_id=round_id,
            )
            self.session.add(debit)
            await self.session.flush()
            entries.append(LedgerEntryResult(debit.id, operation.id, -stake, balance, LedgerReason.GAME_STAKE, round_id))
        if payout:
            balance = validate_wallet_delta(balance, payout)
            credit = LedgerEntry(
                operation_id=operation.id,
                wallet_id=wallet.user_id,
                amount_delta=payout,
                balance_after=balance,
                reason=LedgerReason.GAME_PAYOUT.value,
                reference_type="game_round",
                reference_id=round_id,
            )
            self.session.add(credit)
            await self.session.flush()
            entries.append(LedgerEntryResult(credit.id, operation.id, payout, balance, LedgerReason.GAME_PAYOUT, round_id))
        wallet.balance = balance
        wallet.version += 1
        await self.session.flush()
        return SettlementResult(operation.id, key, wallet.user_id, stake, payout, payout - stake, balance, tuple(entries))
