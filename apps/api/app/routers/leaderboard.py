from datetime import UTC, datetime, timedelta, timezone

from burmaldoza_contracts.leaderboard import (
    LeaderboardEntry,
    LeaderboardOwnPlace,
    LeaderboardSnapshot,
)
from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LedgerEntry, User
from app.db.session import get_session
from app.dependencies import CurrentUser, get_current_user

router = APIRouter(prefix="/api/v1/leaderboard", tags=["leaderboard"])
# Moscow has used UTC+3 without seasonal transitions since 2014; no tzdata dependency.
MOSCOW = timezone(timedelta(hours=3), "MSK")
TOP_SIZE = 15


def get_leaderboard_now() -> datetime:
    return datetime.now(UTC)


def _nickname(username: str | None) -> str:
    return f"@{username}" if username else "Игрок без ника"


@router.get("", response_model=LeaderboardSnapshot)
async def leaderboard(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    now: datetime = Depends(get_leaderboard_now),
) -> LeaderboardSnapshot:
    local_now = now.astimezone(MOSCOW)
    monday = local_now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=local_now.weekday()
    )
    start = monday.astimezone(UTC)
    end = (monday + timedelta(days=7)).astimezone(UTC)
    # Net game result per wallet for the week; grants and bonuses are not counted.
    totals = (
        select(
            LedgerEntry.wallet_id.label("user_id"),
            func.sum(LedgerEntry.amount_delta).label("net_result"),
        )
        .where(
            LedgerEntry.reason.in_(("game_stake", "game_payout")),
            LedgerEntry.created_at >= start,
            LedgerEntry.created_at < end,
        )
        .group_by(LedgerEntry.wallet_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(User.id, User.username, totals.c.net_result)
            .join(totals, totals.c.user_id == User.id)
            # Stable order for equal results; internal ids never leave this query.
            .order_by(totals.c.net_result.desc(), User.id.asc())
            .limit(TOP_SIZE)
        )
    ).all()

    me = None
    if current_user.user_id not in {user_id for user_id, _, _ in rows}:
        own = await session.scalar(
            select(totals.c.net_result).where(totals.c.user_id == current_user.user_id)
        )
        if own is not None:
            ahead = await session.scalar(
                select(func.count())
                .select_from(totals)
                .where(
                    or_(
                        totals.c.net_result > own,
                        and_(totals.c.net_result == own, totals.c.user_id < current_user.user_id),
                    )
                )
            )
            username = await session.scalar(
                select(User.username).where(User.id == current_user.user_id)
            )
            me = LeaderboardOwnPlace(
                rank=int(ahead or 0) + 1, nickname=_nickname(username), net_result=int(own)
            )

    return LeaderboardSnapshot(
        week_start=start,
        week_end=end,
        entries=[
            LeaderboardEntry(rank=index, nickname=_nickname(username), net_result=result)
            for index, (_, username, result) in enumerate(rows, start=1)
        ],
        me=me,
    )
