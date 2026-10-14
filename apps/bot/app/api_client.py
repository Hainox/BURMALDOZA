from __future__ import annotations

from typing import Any

import httpx


class BotApiError(RuntimeError):
    """Raised when the bot cannot read a server-backed response."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


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

    async def admin_lookup(self, actor_telegram_id: int, query: str) -> dict[str, Any]:
        return await self._get("/api/v1/internal/bot/admin/users", params={"actor": actor_telegram_id, "query": query})

    async def admin_adjust(
        self, actor_telegram_id: int, target_telegram_id: int, delta: int, comment: str, idempotency_key: str
    ) -> dict[str, Any]:
        return await self._post("/api/v1/internal/bot/admin/adjust", {
            "actor_telegram_id": actor_telegram_id,
            "target_telegram_id": target_telegram_id,
            "delta": delta,
            "comment": comment,
            "idempotency_key": idempotency_key,
        })

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        try:
            response = await self._client.post(
                path, json=payload, headers={"X-Internal-API-Token": self._internal_api_token}
            )
        except httpx.HTTPError as error:
            raise BotApiError("API request failed") from error
        if response.status_code >= 400:
            raise BotApiError("API request rejected", response.status_code)
        try:
            return response.json()
        except ValueError as error:
            raise BotApiError("API request failed") from error

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            response = await self._client.get(
                path, params=params, headers={"X-Internal-API-Token": self._internal_api_token}
            )
        except httpx.HTTPError as error:
            raise BotApiError("API request failed") from error
        if response.status_code >= 400:
            raise BotApiError("API request rejected", response.status_code)
        try:
            return response.json()
        except ValueError as error:
            raise BotApiError("API request failed") from error

    async def close(self) -> None:
        await self._client.aclose()
