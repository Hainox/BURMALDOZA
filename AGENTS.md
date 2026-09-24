# AGENTS.md

Общая справка для всех ИИ-агентов проекта: Codex, Command Code (CCode) и Claude Code.
Роли, handoff и правила квот — в [docs/Command-Code-Workflow.md](./docs/Command-Code-Workflow.md);
правила Claude Code — в [CLAUDE.md](./CLAUDE.md). Этот файл их не заменяет и не противоречит им.

Бурмалдоза — игровой слой для Telegram-сообщества: aiogram-бот (вход), SvelteKit Mini App (UI),
FastAPI (источник подтверждённого состояния), PostgreSQL + Redis. Валюта Jokergem — без реальных денег.
Документация и коммуникация с владельцем — на русском; владелец не программист, объяснять простыми словами.

## Источники истины

Перед существенной работой: `dev/Vision.md` → `dev/BuildSpec.md` → `dev/ProjectLog.md` →
`docs/Command-Code-Workflow.md` и связанное issue. Черновики, картинки и старые записи журнала
не создают новых требований; при конфликте — актуальное решение владельца.

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
pnpm miniapp:e2e                       # Playwright; нужен Chromium той версии, что ждёт @playwright/test
```

Интеграционные тесты требуют PostgreSQL: `TEST_DATABASE_URL=postgresql+asyncpg://...`; в CI поднимаются сервисы.

## Инварианты (не нарушать)

- Сервер — единственный источник исхода: клиент только анимирует подтверждённый event, не генерирует результат.
- Баланс меняется только через `WalletService` (append-only ledger, целые единицы, idempotency key на операцию).
- Мутирующие запросы идемпотентны (`X-Request-ID` / `action_id` — UUID); комнаты версионируются `state_version`.
- Боевой RNG — `SystemRandomSource` (CSPRNG); `SeededRandomSource` только для тестов и Monte Carlo.
- Скрытые данные (колода, hole-card) — только в `private_state_json`, никогда в публичном состоянии/событиях.
- Секреты не коммитить и не открывать в сессиях агентов; `.env` в `.gitignore`, шаблон — `.env.example`.

## Совместная работа

| Агент | Префикс ветки | Роль (подробно — в workflow-документе) |
|---|---|---|
| Codex | `codex/<задача>` | архитектура, domain/RNG/ledger/API, безопасность, интеграция, финальная проверка |
| Command Code | `ccode/<задача>` | назначенные UI/motion handoff-задачи |
| Claude Code | `claude/<задача>` | read-only review, документация, тесты, небольшие задачи с точным allowlist |

- Один implementer на набор файлов; перед началом — `git fetch` и открытые PR, чтобы не взять чужие файлы.
- Domain, RNG, ledger, API-контракты, миграции и deployment — только по задаче с явным scope владельца
  и утверждённым BuildSpec.
- Одна задача — одна ветка — один PR в `main`. Не пушить в чужую ветку, без force-push; merge и deploy
  делает владелец.
- Незаконченная работа (например, кончился лимит) передаётся через PR-черновик с описанием «сделано /
  осталось / проверки» и запись в `dev/ProjectLog.md`; следующий агент продолжает в той же ветке.
- `dev/ProjectLog.md` — после значимого изменения; `ChangeLog.md` — только пользовательские, deploy- или
  compatibility-изменения.
- Отчёт: изменённые файлы, команды и их фактические результаты, остаточные риски, branch/commit.

## Штаб: задания и отчёты через GitHub

Штаб — закреплённый чат Codex «Бурмалдоза — штаб Codex / Claude / CCode». Он проверяет GitHub
раз в 30 минут и маршрутизирует задания и отчёты. Штаб видит **только GitHub**: то, что осталось лишь
в сессии агента, до него не доходит.

- **Задание** — issue с меткой адресата: `to:codex`, `to:claude` или `to:ccode`. В теле: исполнитель,
  модель/effort, базовая ветка и имя новой ветки, разрешённые файлы, критерии приёмки, обязательные
  проверки, зависимости («начать после #N»).
- **Отчёт** — комментарий в PR задачи; если PR нет — в issue задачи; если нет и issue — в закреплённое
  issue «Штаб: входящие» (метка `agent-report`). Каждый агент публикует отчёт сам через `gh` в конце
  задачи; пересылка через владельца — только если у агента нет доступа к GitHub.
- **Вопрос владельцу** или блокер, который снимает только он, — метка `needs-owner`.
- **Замещение:** если у агента кончился лимит, владелец может передать его задачи другому агенту.
  Заместитель продолжает в той же ветке (см. правило о незаконченной работе) и пишет в отчёте
  «замещает <агент>».
- Не публиковать транскрипты сессий, секреты, `.env`, IP серверов и пути на ПК владельца —
  репозиторий публичный. Хуки, отправляющие что-то на каждом шаге сессии, не использовать.

Формат отчёта (первая строка обязательна — по ней штаб находит отчёты):

```markdown
<!-- agent-report -->
**Кому:** <адресат> · **От:** <агент> · **Модель/effort:** <точно, либо «не отображается»> · **Тип:** отчёт | review | задание | блокер
**Задача:** #<issue> / PR #<n> · **Ветка/коммит:** `<branch>` / `<sha>`

- Сделано: …
- Проверки: `<команда>` — <фактический результат>
- Блокеры и риски: …
- Следующий шаг: …
```
