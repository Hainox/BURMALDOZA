from __future__ import annotations

from typing import Any

import httpx


class BotApiError(RuntimeError):
    """Raised when the bot cannot read a server-backed response."""


class BotApiClient:
    def __init__(self, api_base_url: str, internal_api_token: str, *, timeout: float = 5.0) -> None:
        self._internal_api_token = internal_api_token
        self._client = httpx.AsyncClient(base_url=api_base_url.rstrip("/"), timeout=timeout)

    async def get_balance(self, telegram_user_id: int) -> dict[str, Any]:
        return await self._get(f"/api/v1/internal/bot/users/{telegram_user_id}/wallet")

    async def get_top(self) -> list[dict[str, Any]]:
        payload = await self._get("/api/v1/internal/bot/top")
        if not isinstance(payload, list):
            raise BotApiError("invalid top response")
        return payload

    async def _get(self, path: str) -> Any:
        try:
            response = await self._client.get(
                path, headers={"X-Internal-API-Token": self._internal_api_token}
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise BotApiError("API request failed") from error

    async def close(self) -> None:
        await self._client.aclose()
