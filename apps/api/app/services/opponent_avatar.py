"""Bounded, transient Telegram photos. Callers must authorize the room before get()."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field, StrictInt, ValidationError

_PRIVATE_TRANSPORT = ContextVar("avatar_private_transport", default=False)
MAX_BYTES = 256 * 1024


class _TransportPrivacy(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # httpx INFO and httpcore DEBUG include token-bearing paths. Hide only
        # records in this request context, without changing global log levels.
        return not _PRIVATE_TRANSPORT.get()


for _logger_name in (
    "httpx",
    "httpcore.connection",
    "httpcore.http11",
    "httpcore.http2",
    "httpcore.proxy",
):
    logging.getLogger(_logger_name).addFilter(_TransportPrivacy())


class AvatarError(Exception):
    def __init__(self, status: int = 503, retry_after: int = 30):
        super().__init__("avatar unavailable")
        self.status = status
        self.retry_after = retry_after


class Photo(BaseModel):
    file_id: str = Field(min_length=1, max_length=1024)
    width: StrictInt = Field(gt=0)
    height: StrictInt = Field(gt=0)


class Photos(BaseModel):
    photos: list[list[Photo]] = Field(max_length=1)


class TelegramFile(BaseModel):
    file_path: str = Field(min_length=1, max_length=512)
    file_size: StrictInt | None = Field(default=None, ge=0, le=MAX_BYTES)


@dataclass(frozen=True)
class CachedAvatar:
    expires: float
    value: tuple[bytes, str] | None = None
    error: tuple[int, int] | None = None


class AvatarService:
    def __init__(
        self,
        token: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        now: Callable[[], float] = time.monotonic,
    ):
        self.token = token
        self.transport = transport
        self.now = now
        self.cache: OrderedDict[int, CachedAvatar] = OrderedDict()
        self.viewers: dict[int, deque[float]] = {}
        self.loads: deque[float] = deque()
        self.inflight: dict[int, asyncio.Task] = {}
        self.semaphore = asyncio.Semaphore(2)
        self.blocked_until = 0.0

    async def aclose(self) -> None:
        tasks = list(self.inflight.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.cache.clear()
        self.viewers.clear()

    def check_viewer(self, user_id: int) -> None:
        now = self.now()
        for key in list(self.viewers):
            if not self.viewers[key] or self.viewers[key][-1] <= now - 60:
                del self.viewers[key]
        if user_id not in self.viewers and len(self.viewers) >= 4096:
            raise AvatarError(429, 60)
        window = self.viewers.setdefault(user_id, deque())
        while window and window[0] <= now - 60:
            window.popleft()
        if len(window) >= 30:
            raise AvatarError(429, max(1, int(window[0] + 60 - now) + 1))
        window.append(now)

    async def get(self, telegram_id: int) -> tuple[bytes, str] | None:
        now = self.now()
        cached = self.cache.get(telegram_id)
        if cached and cached.expires > now:
            self.cache.move_to_end(telegram_id)
            if cached.error:
                status, _ = cached.error
                raise AvatarError(status, max(1, int(cached.expires - now) + 1))
            return cached.value
        task = self.inflight.get(telegram_id)
        if task is None:
            if self.blocked_until > now:
                raise AvatarError(429, max(1, int(self.blocked_until - now) + 1))
            while self.loads and self.loads[0] <= now - 60:
                self.loads.popleft()
            if len(self.loads) >= 60:
                raise AvatarError(429, 60)
            self.loads.append(now)
            task = asyncio.create_task(self._load_cached(telegram_id))
            self.inflight[telegram_id] = task

            def finish(done: asyncio.Task) -> None:
                self.inflight.pop(telegram_id, None)
                if not done.cancelled():
                    done.exception()  # Retrieve failure even if all viewers disconnected.

            task.add_done_callback(finish)
        return await asyncio.shield(task)

    async def _load_cached(self, telegram_id: int) -> tuple[bytes, str] | None:
        try:
            async with asyncio.timeout(5):
                async with self.semaphore:
                    value = await self._download(telegram_id)
            cached = CachedAvatar(self.now() + (3600 if value else 300), value)
        except AvatarError as error:
            ttl = error.retry_after if error.status == 429 else 30
            if error.status == 429:
                self.blocked_until = max(self.blocked_until, self.now() + ttl)
            cached = CachedAvatar(self.now() + ttl, error=(error.status, ttl))
        except (httpx.HTTPError, TimeoutError, ValueError, ValidationError):
            cached = CachedAvatar(self.now() + 30, error=(503, 30))
        self.cache[telegram_id] = cached
        self.cache.move_to_end(telegram_id)
        while len(self.cache) > 64:
            self.cache.popitem(last=False)
        if cached.error:
            raise AvatarError(*cached.error) from None
        return cached.value

    async def _body(
        self, client: httpx.AsyncClient, url: str, payload: dict | None = None
    ) -> bytes:
        async with client.stream(
            "POST" if payload is not None else "GET", url, json=payload
        ) as response:
            if response.headers.get("content-encoding", "identity") != "identity":
                raise AvatarError()
            if response.status_code != 200:
                if response.status_code == 429:
                    # JSON retry_after is read below with the same byte cap.
                    data = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=16384):
                        data.extend(chunk)
                        if len(data) > MAX_BYTES:
                            raise AvatarError()
                    try:
                        retry = int(response.headers.get("Retry-After", "30"))
                    except ValueError:
                        retry = 30
                    try:
                        error = json.loads(data)
                    except (ValueError, UnicodeDecodeError):
                        error = {}
                    parameters = error.get("parameters", {}) if isinstance(error, dict) else {}
                    json_retry = (
                        parameters.get("retry_after") if isinstance(parameters, dict) else None
                    )
                    if type(json_retry) is int and 1 <= json_retry <= 86400:
                        retry = max(retry, json_retry)
                    if type(retry) is not int or not 1 <= retry <= 86400:
                        retry = 30
                    raise AvatarError(429, retry)
                raise AvatarError()
            data = bytearray()
            async for chunk in response.aiter_bytes(chunk_size=16384):
                data.extend(chunk)
                if len(data) > MAX_BYTES:
                    raise AvatarError()
            return bytes(data)

    async def _method(self, client: httpx.AsyncClient, name: str, payload: dict) -> dict:
        body = await self._body(client, f"https://api.telegram.org/bot{self.token}/{name}", payload)
        data = json.loads(body)
        if not isinstance(data, dict) or data.get("ok") is not True:
            raise AvatarError()
        result = data.get("result")
        if not isinstance(result, dict):
            raise AvatarError()
        return result

    async def _download(self, telegram_id: int) -> tuple[bytes, str] | None:
        if not self.token:
            raise AvatarError()
        context = _PRIVATE_TRANSPORT.set(True)
        try:
            async with httpx.AsyncClient(
                transport=self.transport,
                timeout=5,
                follow_redirects=False,
                trust_env=False,
                headers={"Accept-Encoding": "identity"},
            ) as client:
                photos = Photos.model_validate(
                    await self._method(
                        client, "getUserProfilePhotos", {"user_id": telegram_id, "limit": 1}
                    )
                )
                if not photos.photos or not photos.photos[0]:
                    return None
                photo = min(photos.photos[0], key=lambda p: p.width * p.height)
                file = TelegramFile.model_validate(
                    await self._method(client, "getFile", {"file_id": photo.file_id})
                )
                if (
                    not re.fullmatch(r"[A-Za-z0-9_/-]+\.[A-Za-z0-9]+", file.file_path)
                    or file.file_path.startswith("/")
                    or any(part in ("", ".", "..") for part in file.file_path.split("/"))
                ):
                    raise AvatarError()
                body = await self._body(
                    client, f"https://api.telegram.org/file/bot{self.token}/{file.file_path}"
                )
                if body.startswith(b"\xff\xd8\xff") and body.endswith(b"\xff\xd9"):
                    return body, "image/jpeg"
                if body.startswith(b"\x89PNG\r\n\x1a\n"):
                    return body, "image/png"
                raise AvatarError()
        finally:
            _PRIVATE_TRANSPORT.reset(context)
