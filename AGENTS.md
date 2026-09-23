# AGENTS.md

Общие правила для всех ИИ-агентов проекта: Codex, Command Code (CCode) и Claude Code.
`CLAUDE.md` подключает этот файл; правила меняются только здесь.

Бурмалдоза — игровой слой для Telegram-сообщества: aiogram-бот (вход), SvelteKit Mini App (UI),
FastAPI (источник подтверждённого состояния), PostgreSQL + Redis. Валюта Jokergem — без реальных денег.
Документация и коммуникация с владельцем — на русском; владелец не программист, объяснять простыми словами.

## Карта репозитория

- `packages/domain` — чистые правила игр (slot, blackjack, holdem), экономика, RNG. Без I/O.
- `packages/contracts` — Pydantic-контракты API/событий, общие для API и клиента.
- `apps/api` — FastAPI: `routers/` (HTTP/WebSocket), `services/` (wallet_service, room_service), `db/models`.
- `apps/bot` — aiogram-бот; ходит в API через `/api/v1/internal/bot/*` с заголовком `X-Bot-Token`.
- `apps/miniapp` — SvelteKit + `adapter-static`; без `PUBLIC_API_BASE_URL`/Telegram `initData` работает в DEMO.
- `migrations/` — Alembic; `devtools/monte_carlo` — офлайн-симуляции RTP; `dev/`, `docs/` — спецификации и журнал.

## Команды

```bash
uv sync --locked --all-groups          # Python deps (Python 3.12 через uv)
pnpm install --frozen-lockfile         # frontend deps
uv run --locked ruff check .           # lint
uv run --locked pytest -q              # unit tests (integration skip без TEST_DATABASE_URL)
pnpm miniapp:check && pnpm miniapp:test && pnpm miniapp:build
pnpm miniapp:e2e                       # Playwright; нужен PLAYWRIGHT_BROWSERS_PATH (ставит session hook)
```

Интеграционные тесты требуют PostgreSQL: `TEST_DATABASE_URL=postgresql+asyncpg://...`.
В облачной сессии Docker недоступен — они пропускаются, в CI проходят.

## Инварианты (не нарушать)

- Сервер — единственный источник исхода: клиент только анимирует подтверждённый event, не генерирует результат.
- Баланс меняется только через `WalletService` (append-only ledger, целые единицы, idempotency key на операцию).
- Мутирующие запросы идемпотентны (`X-Request-ID` / `action_id` — UUID); комнаты версионируются `state_version`.
- Боевой RNG — `SystemRandomSource` (CSPRNG); `SeededRandomSource` только для тестов и Monte Carlo.
- Скрытые данные (колода, hole-card) — только в `private_state_json`, никогда в публичном состоянии/событиях.
- Секреты не коммитить; `.env` в `.gitignore`, шаблон — `.env.example`.

## Процесс

- Изменения в domain/ledger/RNG/контрактах — только с тестами; при изменении правил обновить Monte Carlo отчёты.
- Перед push: ruff, pytest, miniapp check/test/build; для UI-изменений — e2e.
- Значимые изменения фиксировать в `dev/ProjectLog.md` и `ChangeLog.md`.

## Совместная работа агентов

Подробно — [docs/Command-Code-Workflow.md](./docs/Command-Code-Workflow.md). Коротко:

| Агент | Префикс ветки | Роль по умолчанию |
|---|---|---|
| Codex | `codex/<задача>` | ведущий: архитектура, контракты, сложные merge, handoff-задачи для других |
| Command Code | `ccode/<задача>` | изолированные UI/motion-задачи по handoff-шаблону |
| Claude Code | `claude/<задача>` | облачные сессии: аудит и review, CI-фиксы, backend-задачи, доведение PR до зелёного |

- Одна задача — одна ветка — один PR в `main`. Не пушить в чужую ветку; правки к чужому PR — комментарием
  в PR или отдельной веткой поверх него.
- Перед началом: `git fetch`, посмотреть открытые PR — не брать файлы, которые уже меняет другой агент.
- Каждый PR указывает агента и модель в описании, список изменённых файлов, выполненные проверки и риски.
- Handoff между агентами — по шаблону из workflow-документа (цель, разрешённые файлы, «не менять»,
  acceptance criteria, проверки). Незаконченная работа передаётся через PR-черновик + запись в `dev/ProjectLog.md`,
  чтобы следующий агент (например, после исчерпания лимита) продолжил без потери контекста.
- Merge в `main` делает владелец (Hainox); агенты не мержат свои PR сами.
