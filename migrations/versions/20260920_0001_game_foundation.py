"""create game foundation tables

Revision ID: 20260920_0001
Revises:
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260920_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("telegram_user_id", name="uq_users_telegram_user_id"),
    )
    op.create_table(
        "communities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("telegram_chat_id", name="uq_communities_telegram_chat_id"),
        sa.UniqueConstraint("slug", name="uq_communities_slug"),
    )
    op.create_table(
        "chat_settings",
        sa.Column("community_id", sa.Integer(), sa.ForeignKey("communities.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("enabled_games", sa.JSON(), nullable=False),
        sa.Column("daily_bonus_config", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "admin_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("community_id", sa.Integer(), sa.ForeignKey("communities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("user_id", "community_id", name="uq_admin_roles_user_community"),
    )
    op.create_table(
        "wallets",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("welcome_granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("daily_bonus_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("relief_grant_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("balance >= 0", name="ck_wallets_balance_non_negative"),
    )
    op.create_table(
        "wallet_operations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("wallet_id", sa.Integer(), sa.ForeignKey("wallets.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation_type", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("reference_type", sa.String(length=64), nullable=False),
        sa.Column("reference_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("idempotency_key", name="uq_wallet_operations_idempotency_key"),
    )
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("operation_id", sa.Uuid(as_uuid=True), sa.ForeignKey("wallet_operations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("wallet_id", sa.Integer(), sa.ForeignKey("wallets.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount_delta", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("reference_type", sa.String(length=64), nullable=False),
        sa.Column("reference_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("balance_after >= 0", name="ck_ledger_entries_balance_after_non_negative"),
    )
    op.create_table(
        "game_rooms",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("community_id", sa.Integer(), sa.ForeignKey("communities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sequence_no", sa.Integer(), nullable=True),
        sa.Column("game_type", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("ruleset_version", sa.String(length=64), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("community_id", "sequence_no", name="uq_game_rooms_community_sequence"),
        sa.CheckConstraint("state_version >= 0", name="ck_game_rooms_state_version_non_negative"),
    )
    op.create_table(
        "game_players",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("room_id", sa.Uuid(as_uuid=True), sa.ForeignKey("game_rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seat", sa.Integer(), nullable=False),
        sa.Column("stack", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("room_id", "user_id", name="uq_game_players_room_user"),
        sa.UniqueConstraint("room_id", "seat", name="uq_game_players_room_seat"),
    )
    op.create_table(
        "game_rounds",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("room_id", sa.Uuid(as_uuid=True), sa.ForeignKey("game_rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_no", sa.Integer(), nullable=False),
        sa.Column("bet_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("outcome_json", sa.JSON(), nullable=False),
        sa.Column("payout_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("room_id", "round_no", name="uq_game_rounds_room_round"),
        sa.UniqueConstraint("idempotency_key", name="uq_game_rounds_idempotency_key"),
        sa.CheckConstraint("bet_amount >= 0", name="ck_game_rounds_bet_non_negative"),
        sa.CheckConstraint("payout_amount >= 0", name="ck_game_rounds_payout_non_negative"),
    )
    op.create_table(
        "game_actions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("room_id", sa.Uuid(as_uuid=True), sa.ForeignKey("game_rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("room_id", "sequence_no", name="uq_game_actions_room_sequence"),
    )
    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target", sa.String(length=255), nullable=False),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("admin_audit_log")
    op.drop_table("game_actions")
    op.drop_table("game_rounds")
    op.drop_table("game_players")
    op.drop_table("game_rooms")
    op.drop_table("ledger_entries")
    op.drop_table("wallet_operations")
    op.drop_table("wallets")
    op.drop_table("admin_roles")
    op.drop_table("chat_settings")
    op.drop_table("communities")
    op.drop_table("users")
