from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import pytest
from app.core.telegram_auth import TelegramAuthError, verify_telegram_init_data

BOT_TOKEN = "test-bot-token"
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)


def make_init_data(
    *,
    auth_date: datetime = NOW - timedelta(minutes=5),
    user: dict[str, object] | None = None,
    query_id: str = "AAHtest-query",
) -> str:
    payload = {
        "auth_date": str(int(auth_date.timestamp())),
        "query_id": query_id,
        "user": json.dumps(
            user
            or {"id": 12345, "first_name": "Ada", "last_name": "Lovelace", "username": "ada"},
            separators=(",", ":"),
        ),
    }
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode([*payload.items(), ("hash", digest)])


def sign_payload(payload: dict[str, str]) -> str:
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode([*payload.items(), ("hash", digest)])


def test_valid_init_data_returns_minimal_context() -> None:
    context = verify_telegram_init_data(make_init_data(), BOT_TOKEN, NOW, 86400)

    assert context.telegram_user_id == 12345
    assert context.user_id == 12345
    assert context.display_name == "Ada Lovelace"
    assert context.username == "ada"


def test_altered_hash_is_rejected() -> None:
    raw = make_init_data().replace("hash=", "hash=0", 1)

    with pytest.raises(TelegramAuthError, match="signature"):
        verify_telegram_init_data(raw, BOT_TOKEN, NOW, 86400)


def test_altered_user_is_rejected() -> None:
    raw = make_init_data().replace("Ada", "Eve", 1)

    with pytest.raises(TelegramAuthError, match="signature"):
        verify_telegram_init_data(raw, BOT_TOKEN, NOW, 86400)


def test_expired_init_data_is_rejected() -> None:
    raw = make_init_data(auth_date=NOW - timedelta(days=2))

    with pytest.raises(TelegramAuthError, match="expired"):
        verify_telegram_init_data(raw, BOT_TOKEN, NOW, 86400)


def test_missing_auth_date_is_rejected() -> None:
    raw = sign_payload(
        {
            "query_id": "AAHtest-query",
            "user": json.dumps({"id": 12345}, separators=(",", ":")),
        }
    )

    with pytest.raises(TelegramAuthError, match="auth_date"):
        verify_telegram_init_data(raw, BOT_TOKEN, NOW, 86400)


def test_missing_user_is_rejected() -> None:
    raw = sign_payload({"auth_date": str(int((NOW - timedelta(minutes=5)).timestamp()))})

    with pytest.raises(TelegramAuthError, match="user"):
        verify_telegram_init_data(raw, BOT_TOKEN, NOW, 86400)


@pytest.mark.parametrize("raw", ["", "auth_date=%ZZ", "auth_date=123&auth_date=124"])
def test_malformed_or_ambiguous_payload_is_rejected(raw: str) -> None:
    with pytest.raises(TelegramAuthError):
        verify_telegram_init_data(raw, BOT_TOKEN, NOW, 86400)
