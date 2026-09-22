# Бурмалдоза — локальный запуск foundation

## Требования

- Python 3.12+ и `uv`.
- Node.js 24+ и pnpm `11.19.0`.
- Docker Desktop с Compose v2 для PostgreSQL, Redis и контейнеров проекта.
- Chromium для Playwright e2e; устанавливается отдельной командой ниже.

## Подготовка зависимостей

```bash
cp .env.example .env
# Задайте POSTGRES_PASSWORD и свежий BOT_TOKEN.
# Не используйте токен, который был отправлен в чат или коммит.
pnpm install --frozen-lockfile
uv sync --locked --all-groups
pnpm --dir apps/miniapp exec playwright install chromium
```

Если CDN браузера недоступен, установите Chromium на хосте и укажите `executablePath` в локальном Playwright config; пропущенный browser runtime нельзя считать зелёным e2e.

## Полный Compose-контур

```bash
docker compose config -q
docker compose up -d postgres redis api bot miniapp
curl --fail http://localhost:8000/health/live
curl --fail http://localhost:8000/health/ready
```

Сервисы:

- `postgres` — PostgreSQL 16, durable volumes;
- `redis` — Redis 7 AOF, locks/presence/pub-sub boundary;
- `api` — Alembic upgrade + FastAPI на `API_PORT`;
- `bot` — aiogram polling, требует свежий `BOT_TOKEN`;
- `miniapp` — статический SvelteKit build через nginx на `MINIAPP_PORT`.

Для live-режима Mini App передайте API endpoint на этапе сборки:

```bash
PUBLIC_API_BASE_URL=http://localhost:8000 docker compose build miniapp
docker compose up -d miniapp
```

Если `PUBLIC_API_BASE_URL` не задан или Mini App открыт вне Telegram WebView без `initData`,
приложение остаётся в безопасном demo-режиме и не делает неподтверждённых запросов.

Остановить disposable stack без удаления данных:

```bash
docker compose down
```

Для удаления локальных volumes требуется отдельное осознанное действие `docker compose down -v`.

## Проверки

```bash
git diff --check
uv run --locked ruff check .
uv run --locked pytest -q
pnpm miniapp:check
pnpm miniapp:test
pnpm miniapp:build
pnpm miniapp:e2e
```

Интеграционные тесты автоматически подключаются, если задан:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://burmaldoza:local-test@localhost:5432/burmaldoza uv run --locked pytest tests/integration -q
```

Миграции можно проверить отдельно в disposable PostgreSQL:

```bash
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
```

## Без Docker

`pnpm miniapp:check`, `pnpm miniapp:test`, `pnpm miniapp:build`, Python unit-тесты и линтер работают локально. PostgreSQL integration, Alembic online cycle и Compose health checks требуют Docker/Compose; отсутствие Docker не маскируется skip-ами как успешный release check.
