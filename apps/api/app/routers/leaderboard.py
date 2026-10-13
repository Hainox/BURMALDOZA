from datetime import UTC, datetime, timedelta, timezone

from burmaldoza_contracts.leaderboard import LeaderboardEntry, LeaderboardSnapshot
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LedgerEntry, User
from app.db.session import get_session
from app.dependencies import CurrentUser, get_current_user

router = APIRouter(prefix="/api/v1/leaderboard", tags=["leaderboard"])
# Moscow has used UTC+3 without seasonal transitions since 2014; no tzdata dependency.
MOSCOW = timezone(timedelta(hours=3), "MSK")


def get_leaderboard_now() -> datetime:
    return datetime.now(UTC)


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
    net_result = func.sum(LedgerEntry.amount_delta).label("net_result")
    rows = (
        await session.execute(
            select(User.username, net_result)
            .join(LedgerEntry, LedgerEntry.wallet_id == User.id)
            .where(
                LedgerEntry.reason.in_(("game_stake", "game_payout")),
                LedgerEntry.created_at >= start,
                LedgerEntry.created_at < end,
            )
            .group_by(User.id, User.username)
            # Stable order for equal results; internal ids never leave this query.
            .order_by(net_result.desc(), User.id.asc())
            .limit(15)
        )
    ).all()
    return LeaderboardSnapshot(
        week_start=start,
        week_end=end,
        entries=[
            LeaderboardEntry(
                rank=index,
                nickname=f"@{username}" if username else "Игрок без ника",
                net_result=result,
            )
            for index, (username, result) in enumerate(rows, start=1)
        ],
    )
