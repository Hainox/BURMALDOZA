import asyncio
import logging

import httpx
import pytest
from app.services.opponent_avatar import AvatarError, AvatarService

JPEG = b"\xff\xd8\xff\xe0avatar-test\xff\xd9"


def source(kind="ok", calls=None):
    def handle(request):
        if calls is not None:
            calls.append(request)
        if kind == "timeout":
            raise httpx.ReadTimeout("private upstream URL", request=request)
        if kind == "429":
            return httpx.Response(429, json={"parameters": {"retry_after": 90}})
        if request.url.path.endswith("getUserProfilePhotos"):
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {
                        "photos": []
                        if kind == "none"
                        else [[{"file_id": "fixture", "width": 160, "height": 160}]]
                    },
                },
            )
        if request.url.path.endswith("getFile"):
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {"file_path": "../private" if kind == "path" else "photos/test.jpg"},
                },
            )
        if kind == "redirect":
            return httpx.Response(302, headers={"Location": "http://127.0.0.1/private"})
        return httpx.Response(200, content=b"x" * 262145 if kind == "oversize" else JPEG)

    return httpx.MockTransport(handle)


@pytest.mark.asyncio
async def test_avatar_cache_ttl_and_logs(caplog):
    now = [0.0]
    calls = []
    service = AvatarService("fixture-token", transport=source(calls=calls), now=lambda: now[0])
    caplog.set_level(logging.DEBUG)
    assert await service.get(1) == (JPEG, "image/jpeg")
    assert await service.get(1) == (JPEG, "image/jpeg")
    assert len(calls) == 3
    now[0] = 3601
    assert await service.get(1) == (JPEG, "image/jpeg")
    assert len(calls) == 6
    assert "fixture-token" not in caplog.text
    assert "photos/test.jpg" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["timeout", "429", "path", "redirect", "oversize"])
async def test_source_errors_are_bounded_and_cached(kind):
    calls = []
    service = AvatarService("fixture-token", transport=source(kind, calls))
    with pytest.raises(AvatarError) as error:
        await service.get(1)
    assert error.value.status == (429 if kind == "429" else 503)
    count = len(calls)
    with pytest.raises(AvatarError):
        await service.get(1)
    assert len(calls) == count
    assert "fixture-token" not in str(error.value)


@pytest.mark.asyncio
async def test_no_photo_negative_cache_and_request_limit():
    calls = []
    now = [0.0]
    service = AvatarService("fixture-token", transport=source("none", calls), now=lambda: now[0])
    assert await service.get(1) is None
    assert await service.get(1) is None
    assert len(calls) == 1
    now[0] = 301
    assert await service.get(1) is None
    assert len(calls) == 2
    for _ in range(30):
        service.check_viewer(10)
    with pytest.raises(AvatarError) as error:
        service.check_viewer(10)
    assert error.value.status == 429


@pytest.mark.asyncio
async def test_same_avatar_fetch_is_coalesced():
    calls = []
    service = AvatarService("fixture-token", transport=source(calls=calls))
    assert await asyncio.gather(*(service.get(1) for _ in range(8))) == [(JPEG, "image/jpeg")] * 8
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_global_rate_and_cache_memory_are_bounded():
    now = [0.0]
    service = AvatarService("fixture", transport=source("none"), now=lambda: now[0])
    for user in range(60):
        assert await service.get(user) is None
    with pytest.raises(AvatarError) as error:
        await service.get(100)
    assert error.value.status == 429
    now[0] = 61
    for user in range(60, 90):
        assert await service.get(user) is None
    assert len(service.cache) == 64
    await service.aclose()
    assert not service.cache


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [b"[]", b"invalid", b'{"ok":true,"result":"bad"}'])
async def test_malformed_source_is_unavailable(body):
    service = AvatarService(
        "fixture", transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))
    )
    with pytest.raises(AvatarError) as error:
        await service.get(1)
    assert error.value.status == 503


@pytest.mark.asyncio
async def test_upstream_retry_after_blocks_other_uncached_profiles():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "90"}, content=b"unavailable")

    service = AvatarService("fixture", transport=httpx.MockTransport(handle))
    for user in (1, 2):
        with pytest.raises(AvatarError) as error:
            await service.get(user)
        assert error.value.status == 429
        assert error.value.retry_after >= 89
    assert len(calls) == 1
