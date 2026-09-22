import asyncio
from collections.abc import Callable

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.session import SessionFactory
from app.routers import auth, internal, rooms, wallet
from app.services.event_bus import EventBus

app = FastAPI(title="Burmaldoza API", version="0.1.0")
app.state.settings = settings
app.state.event_bus = EventBus()
app.state.session_factory = SessionFactory
app.state.redis_client_factory = Redis.from_url

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.miniapp_url] if settings.miniapp_url else [],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Telegram-Init-Data", "X-Request-ID"],
)

app.include_router(auth.router)
app.include_router(wallet.router)
app.include_router(rooms.router)
app.include_router(internal.router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Backward-compatible liveness endpoint; dependency checks live under /health/ready."""
    return {"status": "ok", "service": "api"}


@app.get("/health/live", tags=["system"])
async def health_live() -> dict[str, str]:
    return {"status": "ok", "service": "api"}


async def _check_database(session_factory: async_sessionmaker[AsyncSession]) -> bool:
    try:
        async with asyncio.timeout(1.5):
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError, TimeoutError):
        return False
    return True


async def _check_redis(redis_client_factory: Callable[..., Redis], redis_url: str) -> bool:
    client = None
    healthy = False
    try:
        client = redis_client_factory(
            redis_url,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
        )
        async with asyncio.timeout(1.5):
            await client.ping()
        healthy = True
    except (RedisError, OSError, TimeoutError, ValueError):
        healthy = False
    finally:
        if client is not None:
            try:
                await client.aclose()
            except (RedisError, OSError, TimeoutError):
                healthy = False
    return healthy


@app.get("/health/ready", tags=["system"], response_model=None)
async def health_ready(request: Request) -> dict[str, object] | JSONResponse:
    session_factory = getattr(request.app.state, "session_factory", SessionFactory)
    redis_client_factory = getattr(
        request.app.state, "redis_client_factory", Redis.from_url
    )
    database_ok, redis_ok = await asyncio.gather(
        _check_database(session_factory),
        _check_redis(redis_client_factory, request.app.state.settings.redis_url),
    )
    dependencies = {
        "database": "ok" if database_ok else "unavailable",
        "redis": "ok" if redis_ok else "unavailable",
    }
    if database_ok and redis_ok:
        return {"status": "ok", "service": "api", "dependencies": dependencies}
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "unavailable", "service": "api", "dependencies": dependencies},
    )
