import pytest
from app.core.config import Settings
from app.main import _check_database, _check_redis
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.mark.asyncio
async def test_readiness_probes_connect_to_postgres_and_redis(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = Settings()

    assert await _check_database(session_factory) is True
    assert await _check_redis(Redis.from_url, settings.redis_url) is True
