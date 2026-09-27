from __future__ import annotations

import httpx
import pytest

from apps.bot.app.api_client import BotApiClient


@pytest.mark.asyncio
async def test_bot_sends_only_internal_token_to_api() -> None:
    seen_headers: list[httpx.Headers] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers)
        return httpx.Response(200, json=[])

    client = BotApiClient("https://api.example.test", "TEST_INTERNAL_TOKEN")
    await client._client.aclose()
    client._client = httpx.AsyncClient(
        base_url="https://api.example.test", transport=httpx.MockTransport(handle)
    )
    try:
        assert await client.get_top() == []
    finally:
        await client.close()

    assert seen_headers[0]["X-Internal-API-Token"] == "TEST_INTERNAL_TOKEN"
    assert "X-Bot-Token" not in seen_headers[0]
