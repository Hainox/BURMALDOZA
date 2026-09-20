from app.main import app
from fastapi.testclient import TestClient


def test_health_reports_api_liveness() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}


def test_split_health_endpoints_are_available() -> None:
    client = TestClient(app)

    assert client.get("/health/live").json() == {"status": "ok", "service": "api"}
    assert client.get("/health/ready").json() == {"status": "ok", "service": "api"}
