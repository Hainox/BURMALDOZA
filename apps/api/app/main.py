from fastapi import FastAPI

from app.core.config import settings
from app.db.session import SessionFactory
from app.routers import auth, internal, rooms, wallet
from app.services.event_bus import EventBus

app = FastAPI(title="Burmaldoza API", version="0.1.0")
app.state.settings = settings
app.state.event_bus = EventBus()
app.state.session_factory = SessionFactory

app.include_router(auth.router)
app.include_router(wallet.router)
app.include_router(rooms.router)
app.include_router(internal.router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Liveness endpoint. Dependency health checks are added with their modules."""
    return {"status": "ok", "service": "api"}


@app.get("/health/live", tags=["system"])
async def health_live() -> dict[str, str]:
    return {"status": "ok", "service": "api"}


@app.get("/health/ready", tags=["system"])
async def health_ready() -> dict[str, str]:
    return {"status": "ok", "service": "api"}
