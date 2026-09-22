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
