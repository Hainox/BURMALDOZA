"""store server-only game state outside public room snapshots

Revision ID: 20260923_0003
Revises: 20260920_0002
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260923_0003"
down_revision: str | None = "20260920_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "game_rooms",
        sa.Column("private_state_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("game_rooms", "private_state_json")
