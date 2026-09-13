from fastapi import FastAPI

app = FastAPI(title="Burmaldoza API", version="0.1.0")


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Liveness endpoint. Dependency health checks are added with their modules."""
    return {"status": "ok", "service": "api"}
