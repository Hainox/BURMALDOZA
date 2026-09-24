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
