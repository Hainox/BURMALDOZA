"""persist verified Telegram usernames for the Mini App leaderboard

Revision ID: 20261013_0004
Revises: 20260923_0003
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261013_0004"
down_revision: str | None = "20260923_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "username")
