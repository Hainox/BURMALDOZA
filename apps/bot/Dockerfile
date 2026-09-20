FROM ghcr.io/astral-sh/uv:0.12.15 AS uv
FROM python:3.12-slim-bookworm

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/apps/bot:/app/packages/domain/src:/app/packages/contracts/src"

COPY pyproject.toml uv.lock ./
COPY apps/bot ./apps/bot
COPY packages ./packages

RUN uv sync --locked --no-dev

CMD ["python", "-m", "app.main"]
