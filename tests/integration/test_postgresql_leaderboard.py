import pytest
from app.dependencies import CurrentUser
from app.routers.leaderboard import leaderboard

from tests.unit.test_leaderboard import END, NOW, START, add_player


@pytest.mark.asyncio
async def test_postgresql_week_query_with_tie_and_grant_exclusion(session_factory):
    await add_player(
        session_factory,
        1,
        "one",
        [
            ("game_stake", -100, START),
            ("game_payout", 150, NOW),
            ("daily_bonus", 9000, NOW),
            ("game_payout", 9000, END),
        ],
    )
    await add_player(session_factory, 2, None, [("game_payout", 50, NOW)])
    async with session_factory() as session:
        snapshot = await leaderboard(CurrentUser(1, 1, "Private"), session, NOW)
    assert [entry.model_dump() for entry in snapshot.entries] == [
        {"rank": 1, "nickname": "@one", "net_result": 50},
        {"rank": 2, "nickname": "Игрок без ника", "net_result": 50},
    ]
