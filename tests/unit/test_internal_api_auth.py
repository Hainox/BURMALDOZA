from __future__ import annotations

from types import SimpleNamespace

import pytest
from app.core.config import Settings
from app.db.session import get_session
from app.routers.internal import _require_internal_api_token, router
from fastapi import FastAPI, HTTPException, Request
from httpx import ASGITransport, AsyncClient


def _request(internal_api_token: str, bot_token: str = "TEST_BOT_TOKEN") -> Request:
    app = SimpleNamespace(state=SimpleNamespace(settings=Settings(
        internal_api_token=internal_api_token,
        bot_token=bot_token,
    )))
    return Request({"type": "http", "app": app})


def test_valid_internal_token_is_accepted() -> None:
    _require_internal_api_token(_request("TEST_INTERNAL_TOKEN"), "TEST_INTERNAL_TOKEN")


@pytest.mark.parametrize("provided", [None, "wrong", "TEST_BOT_TOKEN", "é"])
def test_wrong_or_telegram_token_is_rejected(provided: str | None) -> None:
    with pytest.raises(HTTPException) as failure:
        _require_internal_api_token(_request("TEST_INTERNAL_TOKEN"), provided)
    assert failure.value.status_code == 401
    assert failure.value.detail == "internal auth required"


@pytest.mark.parametrize("configured", ["", " ", "é", "TEST_BOT_TOKEN"])
def test_missing_or_reused_internal_configuration_fails_closed(configured: str) -> None:
    with pytest.raises(HTTPException) as failure:
        _require_internal_api_token(_request(configured), configured)
    assert failure.value.status_code == 401
    assert failure.value.detail == "internal auth required"


@pytest.mark.asyncio
async def test_internal_route_accepts_only_the_separate_header() -> None:
    app = FastAPI()
    app.state.settings = Settings(
        bot_token="TEST_BOT_TOKEN", internal_api_token="TEST_INTERNAL_TOKEN"
    )
    app.include_router(router)

    class _Rows:
        def all(self):
            return []

    class _Session:
        async def execute(self, statement):
            return _Rows()

    async def override_session():
        yield _Session()

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        valid = await client.get(
            "/api/v1/internal/bot/top",
            headers={"X-Internal-API-Token": "TEST_INTERNAL_TOKEN"},
        )
        telegram_token = await client.get(
            "/api/v1/internal/bot/top", headers={"X-Bot-Token": "TEST_BOT_TOKEN"}
        )
    assert valid.status_code == 200
    assert valid.json() == []
    assert telegram_token.status_code == 401
