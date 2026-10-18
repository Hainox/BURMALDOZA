"""Админ-операции бота: поиск игрока и ручная корректировка баланса.

Права проверяются здесь же (Telegram ID админов из ADMIN_TELEGRAM_IDS сервера), а не только в боте.
Корректировка — одна транзакция: проводка в ledger (`admin_adjustment`, append-only, ключ идемпотентности)
и запись в admin_audit_log (кто, кому, сколько, баланс до и после, комментарий). Повтор того же ключа
возвращает прежний результат и не пишет журнал второй раз.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from burmaldoza_domain.economy import LedgerReason
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdminAuditLog, User, WalletOperation
from app.services.wallet_service import WalletService, WalletServiceError

# Потолок одной операции: опечатка не должна начислить миллиард.
MAX_ADMIN_ADJUSTMENT = 1_000_000
MAX_COMMENT_LENGTH = 200


class AdminError(ValueError):
    """Ошибка админ-операции с HTTP-кодом для бота."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


@dataclass(frozen=True)
class AdminTarget:
    telegram_user_id: int
    display_name: str
    username: str | None
    balance: int


@dataclass(frozen=True)
class AdminAdjustment:
    target: AdminTarget
    delta: int
    balance_before: int
    balance_after: int
    operation_id: UUID
    replayed: bool


class AdminService:
    def __init__(self, session: AsyncSession, admin_telegram_ids: frozenset[int]):
        self.session = session
        self.admin_telegram_ids = admin_telegram_ids
        self.wallet = WalletService(session)

    def require_admin(self, actor_telegram_id: int) -> None:
        if actor_telegram_id not in self.admin_telegram_ids:
            raise AdminError(403, "admin rights required")

    async def _find_user(self, query: str) -> User:
        text = query.strip()
        if text.lstrip("-").isdigit():
            statement = select(User).where(User.telegram_user_id == int(text))
        else:
            username = text.removeprefix("@")
            if not username:
                raise AdminError(422, "empty player reference")
            statement = select(User).where(func.lower(User.username) == username.lower())
        users = (await self.session.execute(statement.limit(2))).scalars().all()
        if not users:
            raise AdminError(404, "player not found")
        if len(users) > 1:
            # username не уникален: старый владелец ника мог не заходить после смены. Не угадываем.
            raise AdminError(409, "ambiguous username, use Telegram ID")
        return users[0]

    async def lookup(self, actor_telegram_id: int, query: str) -> AdminTarget:
        self.require_admin(actor_telegram_id)
        user = await self._find_user(query)
        await self.session.commit()
        wallet = await self.wallet.get_or_create(user.id)
        return AdminTarget(user.telegram_user_id, user.display_name, user.username, wallet.balance)

    async def adjust(
        self,
        actor_telegram_id: int,
        target_telegram_id: int,
        delta: int,
        comment: str,
        idempotency_key: UUID,
    ) -> AdminAdjustment:
        self.require_admin(actor_telegram_id)
        if (
            isinstance(delta, bool)
            or not isinstance(delta, int)
            or delta == 0
            or abs(delta) > MAX_ADMIN_ADJUSTMENT
        ):
            raise AdminError(422, f"amount must be a non-zero integer up to {MAX_ADMIN_ADJUSTMENT}")
        comment = comment.strip()[:MAX_COMMENT_LENGTH]
        async with self.session.begin():
            target = await self._find_user(str(target_telegram_id))
            actor = (
                (
                    await self.session.execute(
                        select(User).where(User.telegram_user_id == actor_telegram_id)
                    )
                )
                .scalars()
                .first()
            )
            # Сначала блокируем кошелёк, потом ищем ключ: параллельное подтверждение той же карточки
            # дождётся блокировки и увидит уже записанную операцию (без второго аудита и уведомления).
            before = (await self.wallet.get_or_create_in_transaction(target.id)).balance
            replay = (
                (
                    await self.session.execute(
                        select(WalletOperation).where(
                            WalletOperation.idempotency_key == idempotency_key
                        )
                    )
                )
                .scalars()
                .first()
            )
            if replay is None and before + delta < 0:
                raise AdminError(409, "insufficient balance")
            try:
                result = await self.wallet.apply_delta_in_transaction(
                    target.id, delta, LedgerReason.ADMIN_ADJUSTMENT, None, idempotency_key
                )
            except WalletServiceError as error:
                raise AdminError(409, "idempotency key belongs to another operation") from error
            if (
                result.user_id != target.id
                or result.delta != delta
                or result.reason != LedgerReason.ADMIN_ADJUSTMENT
                or result.reference_id is not None
            ):
                raise AdminError(409, "idempotency key belongs to another operation")
            if replay is None:
                self.session.add(
                    AdminAuditLog(
                        actor_id=actor.id if actor else None,
                        action="wallet.admin_adjustment",
                        target=f"user:{target.id}",
                        before_json={"balance": before},
                        after_json={
                            "balance": result.balance_after,
                            "delta": delta,
                            "comment": comment,
                            "operation_id": str(result.operation_id),
                            "actor_telegram_id": actor_telegram_id,
                        },
                    )
                )
            info = AdminTarget(
                target.telegram_user_id, target.display_name, target.username, result.balance_after
            )
            return AdminAdjustment(
                info,
                delta,
                result.balance_after - delta if replay is not None else before,
                result.balance_after,
                result.operation_id,
                replay is not None,
            )
