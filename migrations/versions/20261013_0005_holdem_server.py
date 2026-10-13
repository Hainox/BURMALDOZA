"""Hold'em turn deadlines and durable per-player hero bags."""

import sqlalchemy as sa
from alembic import op

revision = "20261013_0005"
down_revision = "20261013_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("game_rooms", sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_game_rooms_deadline_at", "game_rooms", ["deadline_at"])
    op.create_table(
        "holdem_hero_bags",
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("buy_in", sa.Integer(), primary_key=True),
        sa.Column("remaining_json", sa.JSON(), nullable=False),
        sa.CheckConstraint("buy_in IN (100, 500, 1000)", name="ck_holdem_hero_bags_buy_in"),
    )


def downgrade():
    op.drop_table("holdem_hero_bags")
    op.drop_index("ix_game_rooms_deadline_at", table_name="game_rooms")
    op.drop_column("game_rooms", "deadline_at")
