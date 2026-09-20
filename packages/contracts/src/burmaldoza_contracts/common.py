from enum import StrEnum


class GameType(StrEnum):
    SLOT = "slot"
    BLACKJACK = "blackjack"
    HOLDEM = "holdem"


class RoomStatus(StrEnum):
    WAITING = "waiting"
    ACTIVE = "active"
    SETTLED = "settled"
    CLOSED = "closed"
