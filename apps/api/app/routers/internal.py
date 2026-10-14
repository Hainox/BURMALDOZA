from __future__ import annotations

import hmac
from uuid import UUID

from burmaldoza_contracts.wallet import WalletSnapshot
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Wallet
from app.db.session import get_session
from app.dependencies import get_app_settings
from app.services.admin_service import MAX_ADMIN_ADJUSTMENT, AdminError, AdminService
from app.services.wallet_service import WalletService

router = APIRouter(prefix="/api/v1/internal/bot", tags=["internal"])


def _require_internal_api_token(request: Request, provided: str | None) -> None:
    app_settings = get_app_settings(request)
    configured = app_settings.internal_api_token
    if (
        not configured
        or not provided
        or not configured.isascii()
        or not provided.isascii()
        or not configured.isprintable()
        or not provided.isprintable()
        or any(character.isspace() for character in configured)
        or (app_settings.bot_token and configured == app_settings.bot_token)
        or not hmac.compare_digest(provided, configured)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="internal auth required")


@router.get("/users/{telegram_user_id}/wallet", response_model=WalletSnapshot)
async def internal_wallet(
    telegram_user_id: int,
    request: Request,
    x_internal_api_token: str | None = Header(default=None, alias="X-Internal-API-Token"),
    session: AsyncSession = Depends(get_session),
) -> WalletSnapshot:
    _require_internal_api_token(request, x_internal_api_token)
    user = (
        await session.execute(select(User).where(User.telegram_user_id == telegram_user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    await session.commit()
    return await WalletService(session).get_or_create(user.id)


@router.get("/top")
async def internal_top(
    request: Request,
    x_internal_api_token: str | None = Header(default=None, alias="X-Internal-API-Token"),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, int | str]]:
    _require_internal_api_token(request, x_internal_api_token)
    rows = (
        await session.execute(
            select(User.display_name, Wallet.balance)
            .join(Wallet, Wallet.user_id == User.id)
            .order_by(Wallet.balance.desc(), User.id.asc())
            .limit(10)
        )
    ).all()
    return [{"display_name": display_name, "balance": balance} for display_name, balance in rows]


# --- Админ-команды бота: токен бота + Telegram ID действующего в списке админов сервера. ---

class AdminTargetOut(BaseModel):
    telegram_user_id: int
    display_name: str
    username: str | None
    balance: int


class AdminAdjustIn(BaseModel):
    actor_telegram_id: int
    target_telegram_id: int
    delta: int = Field(ge=-MAX_ADMIN_ADJUSTMENT, le=MAX_ADMIN_ADJUSTMENT)
    comment: str = Field(default="", max_length=200)
    idempotency_key: UUID


class AdminAdjustOut(BaseModel):
    target: AdminTargetOut
    delta: int
    balance_before: int
    balance_after: int
    operation_id: UUID
    replayed: bool


def _admin_service(request: Request, session: AsyncSession) -> AdminService:
    return AdminService(session, get_app_settings(request).admin_ids)


@router.get("/admin/users", response_model=AdminTargetOut)
async def internal_admin_lookup(
    request: Request,
    actor: int = Query(),
    query: str = Query(min_length=1, max_length=64),
    x_internal_api_token: str | None = Header(default=None, alias="X-Internal-API-Token"),
    session: AsyncSession = Depends(get_session),
) -> AdminTargetOut:
    _require_internal_api_token(request, x_internal_api_token)
    try:
        target = await _admin_service(request, session).lookup(actor, query)
    except AdminError as error:
        raise HTTPException(status_code=error.status, detail=error.detail) from error
    return AdminTargetOut(**target.__dict__)


@router.post("/admin/adjust", response_model=AdminAdjustOut)
async def internal_admin_adjust(
    payload: AdminAdjustIn,
    request: Request,
    x_internal_api_token: str | None = Header(default=None, alias="X-Internal-API-Token"),
    session: AsyncSession = Depends(get_session),
) -> AdminAdjustOut:
    _require_internal_api_token(request, x_internal_api_token)
    try:
        result = await _admin_service(request, session).adjust(
            payload.actor_telegram_id,
            payload.target_telegram_id,
            payload.delta,
            payload.comment,
            payload.idempotency_key,
        )
    except AdminError as error:
        raise HTTPException(status_code=error.status, detail=error.detail) from error
    return AdminAdjustOut(
        target=AdminTargetOut(**result.target.__dict__),
        delta=result.delta,
        balance_before=result.balance_before,
        balance_after=result.balance_after,
        operation_id=result.operation_id,
        replayed=result.replayed,
    )
