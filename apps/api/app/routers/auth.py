from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.telegram_auth import TelegramAuthError
from app.db.session import get_session
from app.dependencies import (
    CurrentUser,
    authenticate_raw_init_data,
    get_app_settings,
    get_current_user,
)

router = APIRouter(prefix="/api/v1", tags=["auth"])


class TelegramAuthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    init_data: str | None = Field(default=None, min_length=1)


class CurrentUserResponse(BaseModel):
    user_id: int
    telegram_user_id: int
    display_name: str
    username: str | None = None


def _user_response(user: CurrentUser) -> CurrentUserResponse:
    return CurrentUserResponse(
        user_id=user.user_id,
        telegram_user_id=user.telegram_user_id,
        display_name=user.display_name,
        username=user.username,
    )


@router.post("/auth/telegram", response_model=CurrentUserResponse)
async def authenticate_telegram(
    request: Request,
    payload: TelegramAuthRequest | None = None,
    session: AsyncSession = Depends(get_session),
) -> CurrentUserResponse:
    raw = (payload.init_data if payload is not None else None) or request.headers.get(
        "X-Telegram-Init-Data"
    )
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="init_data is required")
    try:
        user = await authenticate_raw_init_data(
            raw,
            session,
            get_app_settings(request),
            now=datetime.now(UTC),
        )
    except TelegramAuthError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid Telegram init data"
        ) from error
    return _user_response(user)


@router.get("/me", response_model=CurrentUserResponse)
async def me(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUserResponse:
    return _user_response(current_user)
