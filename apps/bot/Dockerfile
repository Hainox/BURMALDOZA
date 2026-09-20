FROM ghcr.io/astral-sh/uv:0.12.15-python3.12-bookworm-slim

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
