import pytest
from app.main import app
from fastapi.testclient import TestClient


def test_miniapp_origin_is_allowed_for_api_requests() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/health/live",
            headers={"Origin": "https://example.invalid"},
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://example.invalid"


def test_unlisted_origin_is_not_reflected() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/health/live",
            headers={"Origin": "https://untrusted.example"},
        )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_origin_strips_path_from_pages_miniapp_url() -> None:
    from app.core.config import cors_origin

    assert cors_origin("https://hainox.github.io/BURMALDOZA/") == "https://hainox.github.io"
    assert cors_origin("http://localhost:4173") == "http://localhost:4173"
    assert cors_origin("https://example.invalid") == "https://example.invalid"
    assert cors_origin("") is None
    assert cors_origin("not a url") is None


@pytest.mark.parametrize(
    ("url", "origin"),
    [
        ("HTTPS://Hainox.GitHub.io/BURMALDOZA/", "https://hainox.github.io"),
        ("https://example.test:443/app", "https://example.test"),
        ("http://example.test:80", "http://example.test"),
        ("https://example.test:8443/", "https://example.test:8443"),
        ("http://example.test:443", "http://example.test:443"),
        ("https://[2001:DB8::0001]:443/", "https://[2001:db8::1]"),
        ("http://[::1]:5173", "http://[::1]:5173"),
        ("  https://example.test/?x=1#frag  ", "https://example.test"),
    ],
)
def test_cors_origin_is_serialized_like_the_browser_origin(url: str, origin: str) -> None:
    from app.core.config import cors_origin

    assert cors_origin(url) == origin


@pytest.mark.parametrize(
    "url",
    [
        "https://user:x@example.test",
        "https://@example.test",
        "https://example.test@evil.test",
        "ftp://example.test",
        "https:///path-only",
        "https://example.test:notaport",
        "https://example.test:70000",
        "https://[::1",
        "https://[fe80::1%25eth0]",
        "https://[127.0.0.1]",
        "https://exa mple.test",
        "https://example_host.test",
        "https://-example.test",
        "https://example..test",
    ],
)
def test_cors_origin_rejects_malformed_or_userinfo_urls(url: str) -> None:
    from app.core.config import cors_origin

    assert cors_origin(url) is None
