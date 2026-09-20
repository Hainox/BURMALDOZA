FROM ghcr.io/astral-sh/uv:0.12.15-python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/apps/api:/app/packages/domain/src:/app/packages/contracts/src"

COPY pyproject.toml uv.lock ./
COPY apps/api ./apps/api
COPY packages ./packages
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini

RUN uv sync --locked --no-dev

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000"]
