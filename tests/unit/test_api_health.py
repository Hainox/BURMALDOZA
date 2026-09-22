from __future__ import annotations

from typing import Self

import pytest
from app.main import app
from fastapi.testclient import TestClient
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError


def test_health_reports_api_liveness() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}


def test_liveness_stays_available_when_dependencies_are_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_dependencies(
        monkeypatch,
        database_error=SQLAlchemyError("database unavailable"),
        redis_error=RedisError("redis unavailable"),
    )
    client = TestClient(app)

    assert client.get("/health/live").json() == {"status": "ok", "service": "api"}
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "service": "api",
        "dependencies": {"database": "unavailable", "redis": "unavailable"},
    }


class FakeSession:
    def __init__(self, error: Exception | None) -> None:
        self.error = error

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, statement: object) -> None:
        assert str(statement) == "SELECT 1"
        if self.error is not None:
            raise self.error


class FakeRedis:
    def __init__(self, error: Exception | None) -> None:
        self.error = error
        self.closed = False

    async def ping(self) -> bool:
        if self.error is not None:
            raise self.error
        return True

    async def aclose(self) -> None:
        self.closed = True


def configure_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    database_error: Exception | None = None,
    redis_error: Exception | None = None,
) -> list[FakeRedis]:
    monkeypatch.setattr(app.state, "session_factory", lambda: FakeSession(database_error))
    clients: list[FakeRedis] = []

    def create_redis(url: str, **kwargs: object) -> FakeRedis:
        assert url
        assert kwargs["socket_connect_timeout"] > 0
        client = FakeRedis(redis_error)
        clients.append(client)
        return client

    monkeypatch.setattr(app.state, "redis_client_factory", create_redis, raising=False)
    return clients


@pytest.mark.parametrize(
    ("database_error", "redis_error", "status_code", "database_status", "redis_status"),
    [
        (None, None, 200, "ok", "ok"),
        (SQLAlchemyError("database unavailable"), None, 503, "unavailable", "ok"),
        (None, RedisError("redis unavailable"), 503, "ok", "unavailable"),
        (
            SQLAlchemyError("database unavailable"),
            RedisError("redis unavailable"),
            503,
            "unavailable",
            "unavailable",
        ),
    ],
)
def test_readiness_checks_database_and_redis_without_exposing_errors(
    monkeypatch: pytest.MonkeyPatch,
    database_error: Exception | None,
    redis_error: Exception | None,
    status_code: int,
    database_status: str,
    redis_status: str,
) -> None:
    clients = configure_dependencies(
        monkeypatch, database_error=database_error, redis_error=redis_error
    )

    response = TestClient(app).get("/health/ready")

    assert response.status_code == status_code
    assert response.json() == {
        "status": "ok" if status_code == 200 else "unavailable",
        "service": "api",
        "dependencies": {"database": database_status, "redis": redis_status},
    }
    assert len(clients) == 1
    assert clients[0].closed is True
    assert "database unavailable" not in response.text
    assert "redis unavailable" not in response.text
