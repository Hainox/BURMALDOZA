from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import parse_qsl


class TelegramAuthError(ValueError):
    """Raised when Telegram Mini App init data cannot be trusted."""


@dataclass(frozen=True, slots=True)
class TelegramAuthContext:
    telegram_user_id: int
    display_name: str
    username: str | None
    auth_date: datetime
    query_id: str | None = None

    @property
    def user_id(self) -> int:
        """Compatibility alias for services that use user_id as their actor key."""
        return self.telegram_user_id


_INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9a-fA-F]{2})")
_HEX_DIGEST = re.compile(r"^[0-9a-fA-F]{64}$")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_pairs(raw: str) -> list[tuple[str, str]]:
    if not raw or _INVALID_PERCENT_ESCAPE.search(raw):
        raise TelegramAuthError("malformed init data")
    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True, max_num_fields=64)
    except ValueError as error:
        raise TelegramAuthError("malformed init data") from error
    if not pairs or any(not key for key, _ in pairs):
        raise TelegramAuthError("malformed init data")
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise TelegramAuthError("ambiguous init data")
    return pairs


def verify_telegram_init_data(
    raw: str, bot_token: str, now: datetime, max_age_seconds: int
) -> TelegramAuthContext:
    """Verify Telegram's signed raw WebApp initData without trusting browser fields."""
    if not bot_token:
        raise TelegramAuthError("bot token is not configured")
    if max_age_seconds <= 0:
        raise TelegramAuthError("auth freshness window is invalid")

    pairs = _parse_pairs(raw)
    values = dict(pairs)
    provided_hash = values.get("hash", "")
    if not provided_hash or not _HEX_DIGEST.fullmatch(provided_hash):
        raise TelegramAuthError("invalid signature")

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(pairs) if key != "hash"
    )
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, provided_hash.lower()):
        raise TelegramAuthError("invalid signature")

    raw_auth_date = values.get("auth_date")
    if raw_auth_date is None:
        raise TelegramAuthError("auth_date is required")
    try:
        auth_date = datetime.fromtimestamp(int(raw_auth_date), tz=UTC)
    except (TypeError, ValueError, OverflowError) as error:
        raise TelegramAuthError("invalid auth_date") from error

    current_time = _as_utc(now)
    age = (current_time - auth_date).total_seconds()
    if age < -30:
        raise TelegramAuthError("auth_date is in the future")
    if age > max_age_seconds:
        raise TelegramAuthError("init data is expired")

    raw_user = values.get("user")
    if raw_user is None:
        raise TelegramAuthError("user is required")
    try:
        user = json.loads(raw_user)
    except json.JSONDecodeError as error:
        raise TelegramAuthError("invalid user payload") from error
    if not isinstance(user, dict) or isinstance(user.get("id"), bool):
        raise TelegramAuthError("invalid user payload")
    try:
        telegram_user_id = int(user["id"])
    except (KeyError, TypeError, ValueError) as error:
        raise TelegramAuthError("invalid user id") from error
    if telegram_user_id <= 0:
        raise TelegramAuthError("invalid user id")

    first_name = str(user.get("first_name", "")).strip()
    last_name = str(user.get("last_name", "")).strip()
    username_value = user.get("username")
    username = str(username_value).strip() if username_value else None
    display_name = " ".join(part for part in (first_name, last_name) if part)
    display_name = display_name or username or str(telegram_user_id)

    return TelegramAuthContext(
        telegram_user_id=telegram_user_id,
        display_name=display_name[:255],
        username=username,
        auth_date=auth_date,
        query_id=values.get("query_id"),
    )
