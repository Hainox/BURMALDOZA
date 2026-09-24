from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.core.telegram_auth import TelegramAuthContext, TelegramAuthError, verify_telegram_init_data
from app.db.conflict_insert import conflict_insert
from app.db.models import User
from app.db.session import get_session
from app.services.event_bus import EventBus
from app.services.wallet_service import WalletService

if TYPE_CHECKING:
    from app.services.room_service import RoomService


@dataclass(frozen=True, slots=True)
class CurrentUser:
    user_id: int
    telegram_user_id: int
    display_name: str
    username: str | None = None


def get_app_settings(request: Request) -> Settings:
    return getattr(request.app.state, "settings", settings)


async def _upsert_user(session: AsyncSession, context: TelegramAuthContext) -> CurrentUser:
    async with session.begin():
        inserted_id = await session.scalar(
            conflict_insert(session, User)
            .values(
                telegram_user_id=context.telegram_user_id,
                display_name=context.display_name,
            )
            .on_conflict_do_nothing(index_elements=[User.telegram_user_id])
            .returning(User.id)
        )
        if inserted_id is not None:
            # New players start with the welcome bonus; otherwise their first bet fails.
            await WalletService(session).claim_welcome_grant_in_transaction(inserted_id)
        else:
            user = (
                await session.execute(select(User).where(User.telegram_user_id == context.telegram_user_id))
            ).scalar_one()
            user.display_name = context.display_name
            user.last_seen_at = datetime.now(UTC)
    return CurrentUser(
        user_id=inserted_id if inserted_id is not None else user.id,
        telegram_user_id=context.telegram_user_id,
        display_name=context.display_name,
        username=context.username,
    )


async def authenticate_raw_init_data(
    raw: str, session: AsyncSession, app_settings: Settings, *, now: datetime | None = None
) -> CurrentUser:
    context = verify_telegram_init_data(
        raw,
        app_settings.bot_token,
        now or datetime.now(UTC),
        app_settings.telegram_init_data_max_age_seconds,
    )
    return await _upsert_user(session, context)


async def get_current_user(
    request: Request, session: AsyncSession = Depends(get_session)
) -> CurrentUser:
    raw = request.headers.get("X-Telegram-Init-Data")
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram auth required")
    try:
        return await authenticate_raw_init_data(raw, session, get_app_settings(request))
    except TelegramAuthError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid Telegram init data"
        ) from error


def get_event_bus(request: Request) -> EventBus:
    event_bus = getattr(request.app.state, "event_bus", None)
    if event_bus is None:
        event_bus = EventBus()
        request.app.state.event_bus = event_bus
    return event_bus


async def get_room_service(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> RoomService:
    from app.services.room_service import RoomService

    app_settings = get_app_settings(request)
    return RoomService(
        session=session,
        event_bus=get_event_bus(request),
        wallet_service=WalletService(session=session),
        bot_token=app_settings.bot_token,
        max_auth_age_seconds=app_settings.telegram_init_data_max_age_seconds,
    )
