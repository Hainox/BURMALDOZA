# Бурмалдоза — локальный запуск foundation

## Требования

- Python 3.12+ и менеджер зависимостей `uv` для команд ниже.
- Node.js 24+ и pnpm 11.19.0 (зафиксирован в `package.json`).
- Docker Engine с Docker Compose для PostgreSQL и Redis.

## Подготовка

```bash
cp .env.example .env
# Задайте локальное значение POSTGRES_PASSWORD в .env.
pnpm install --frozen-lockfile
uv sync --locked --all-groups
docker compose up -d postgres redis
```

## Проверки

```bash
uv run pytest -q
uv run ruff check .
pnpm miniapp:check
pnpm miniapp:build
POSTGRES_PASSWORD=local-test-value docker compose config -q
```

Последняя строка использует синтаксис Bash. В PowerShell задайте `POSTGRES_PASSWORD` в локальной `.env` и выполните `docker compose config -q`.

## Одобрение install-script

Владелец проекта одобрил install-script `esbuild`; разрешение внесено в `pnpm-workspace.yaml`, а проверенная версия `0.28.2` зафиксирована в lockfile. Остальные пакеты автоматически не одобряются. Если при изменении зависимостей появляется `ERR_PNPM_IGNORED_BUILDS`, сначала просмотрите новый скрипт, затем отдельно решите вопрос доверия; не отключайте защиту глобально. Статическое Pages-демо не использует pnpm или esbuild.

## Запуск заготовленных сервисов

```bash
uv run uvicorn app.main:app --app-dir apps/api --reload
pnpm miniapp:dev
```

У бота пока есть только проверка конфигурации; polling/webhook runner и обработчики команд отсутствуют. Заполнение `BOT_TOKEN` и `MINIAPP_URL` само по себе не запускает бота. Реализация ожидает утверждения BuildSpec.
