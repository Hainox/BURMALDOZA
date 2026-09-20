from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from app.db.models import Base
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL.startswith("postgresql+asyncpg://"),
    reason="integration tests require PostgreSQL via asyncpg; set TEST_DATABASE_URL",
)


@pytest_asyncio.fixture(scope="session")
async def database_engine() -> AsyncIterator[AsyncEngine]:
    if not TEST_DATABASE_URL.startswith("postgresql+asyncpg://"):
        pytest.skip("integration tests require PostgreSQL via asyncpg")
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clean_database(database_engine: AsyncEngine) -> AsyncIterator[None]:
    async with database_engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            await connection.execute(table.delete())
    yield


@pytest_asyncio.fixture
async def session_factory(database_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(database_engine, expire_on_commit=False)
