"""index ledger entries by time and reason for the weekly leaderboard

Revision ID: 20261013_0006
Revises: 20261013_0005
Create Date: 2026-10-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261013_0006"
down_revision: str | None = "20261013_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The leaderboard sums game_stake / game_payout entries inside one calendar week.
    op.create_index(
        "ix_ledger_entries_created_at_reason", "ledger_entries", ["created_at", "reason"]
    )


def downgrade() -> None:
    op.drop_index("ix_ledger_entries_created_at_reason", table_name="ledger_entries")
