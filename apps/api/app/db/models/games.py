from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class GameRoom(Base):
    __tablename__ = "game_rooms"
    __table_args__ = (
        CheckConstraint("state_version >= 0", name="ck_game_rooms_state_version_non_negative"),
        UniqueConstraint("community_id", "sequence_no", name="uq_game_rooms_community_sequence"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    community_id: Mapped[int | None] = mapped_column(
        ForeignKey("communities.id", ondelete="SET NULL"), nullable=True
    )
    sequence_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    game_type: Mapped[str] = mapped_column(String(32), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    ruleset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    private_state_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GamePlayer(Base):
    __tablename__ = "game_players"
    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_game_players_room_user"),
        UniqueConstraint("room_id", "seat", name="uq_game_players_room_seat"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[UUID] = mapped_column(ForeignKey("game_rooms.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    seat: Mapped[int] = mapped_column(Integer, nullable=False)
    stack: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GameRound(Base):
    __tablename__ = "game_rounds"
    __table_args__ = (
        UniqueConstraint("room_id", "round_no", name="uq_game_rounds_room_round"),
        CheckConstraint("bet_amount >= 0", name="ck_game_rounds_bet_non_negative"),
        CheckConstraint("payout_amount >= 0", name="ck_game_rounds_payout_non_negative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    room_id: Mapped[UUID] = mapped_column(ForeignKey("game_rooms.id", ondelete="CASCADE"), nullable=False)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False)
    bet_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outcome_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    payout_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GameAction(Base):
    __tablename__ = "game_actions"
    __table_args__ = (UniqueConstraint("room_id", "sequence_no", name="uq_game_actions_room_sequence"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    room_id: Mapped[UUID] = mapped_column(ForeignKey("game_rooms.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
