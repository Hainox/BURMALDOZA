from __future__ import annotations

import hmac

from burmaldoza_contracts.wallet import WalletSnapshot
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Wallet
from app.db.session import get_session
from app.dependencies import get_app_settings
from app.services.wallet_service import WalletService

router = APIRouter(prefix="/api/v1/internal/bot", tags=["internal"])


def _require_bot_token(request: Request, provided: str | None) -> None:
    configured = get_app_settings(request).bot_token
    if not configured or not provided or not hmac.compare_digest(provided, configured):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="internal auth required")


@router.get("/users/{telegram_user_id}/wallet", response_model=WalletSnapshot)
async def internal_wallet(
    telegram_user_id: int,
    request: Request,
    x_bot_token: str | None = Header(default=None, alias="X-Bot-Token"),
    session: AsyncSession = Depends(get_session),
) -> WalletSnapshot:
    _require_bot_token(request, x_bot_token)
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
    x_bot_token: str | None = Header(default=None, alias="X-Bot-Token"),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, int | str]]:
    _require_bot_token(request, x_bot_token)
    rows = (
        await session.execute(
            select(User.display_name, Wallet.balance)
            .join(Wallet, Wallet.user_id == User.id)
            .order_by(Wallet.balance.desc(), User.id.asc())
            .limit(10)
        )
    ).all()
    return [{"display_name": display_name, "balance": balance} for display_name, balance in rows]
