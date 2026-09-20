# Бурмалдоза — роадмап разработки

## Уже собранный foundation

Технический каркас первого релиза проходит по ветке `codex/platform-foundation-spec` и включает:

- Python/aiogram/FastAPI/domain/contracts, PostgreSQL/Alembic и Redis boundary;
- серверную Telegram auth, wallet ledger, idempotency и room snapshots/events;
- три domain skeletons: 3×7 Slot, Blackjack GFL, heads-up Hold’em / RGG Poker;
- SvelteKit Mini App shell, safe areas, reduced motion и state-driven CSS choreography;
- Dockerfile/Compose, CI workflow и Monte Carlo evidence.

Запуск production не считается готовым до прохождения ручного QA, свежего BotFather-токена, настройки домена и отдельной юридической проверки.

## Утверждённый порядок

`foundation → domain tests → ledger/API → Mini App → manual QA → thematic content → closed beta → public launch`

### Этап 0 — Product lock и доступы

**2–4 рабочих дня.**

Зафиксировать целевой чат, владельцев и модераторов, свежий токен через секретный канал, домены `dev/staging/prod`, визуальные права и контакт поддержки.

### Этап 1 — Foundation и окружение

**Завершён в текущей ветке.**

Python 3.12 + uv, Node 24 + pnpm, Docker Compose с PostgreSQL 16/Redis 7, Alembic, API health endpoints, CI и статическая сборка Mini App.

### Этап 2 — Domain rules и Monte Carlo

**Завершён в текущей ветке.**

Тестируемые правила трёх игр, injected CSPRNG, seeded offline simulation, integer payout/tie-split и фиксированные отчёты на 100 000 trials. Monte Carlo оценивает математику skeleton ruleset, но не утверждает монетизацию.

### Этап 3 — Ledger, Telegram auth и API

**Завершён в текущей ветке.**

Проверка сырого `initData`, users/wallets/rooms/rounds/actions, append-only ledger, request idempotency, state version conflict, WebSocket snapshot/event и безопасные bot routes.

### Этап 4 — Mini App и motion

**Foundation завершён; production wiring остаётся.**

Довести API/WebSocket client, pending action lifecycle, реальные legal actions, wallet/history/leaderboard и серверный result payload. Оставить motion state-driven: `intent → accepted → resolving → confirmed outcome → settle`.

### Этап 5 — Manual QA и закрытая приёмка

**5–7 рабочих дней.**

Проверить iOS, Android и Telegram Desktop на 390×844 и широком экране: safe areas, keyboard/focus, reduced motion, slow network, reconnect, повтор tap, stale state, отрицательный баланс, accessibility и отсутствие fake settlement.

Запустить PostgreSQL integration tests и Playwright на машине/CI с Docker и browser runtime; не считать пропущенный runtime зелёным тестом.

### Этап 6 — Тематическое наполнение

**После приёмки каркаса.**

Подключить утверждённый логотип/арт Memendoza, персонажей и знаковые мемные ситуации. Для каждой комнаты отдельно сделать asset pack, motion storyboard, звуковую политику, loading/empty/error states и visual regression review. Не смешивать final art с серверными правилами.

### Этап 7 — Закрытая beta

**5–7 рабочих дней.**

20–50 добровольных участников одного чата, ограниченные лимиты, support/FAQ, метрики без чтения истории сообщений, backup/restore, rate limits, error monitoring и план отката.

### Этап 8 — Public launch

**2–3 рабочих дня после beta.**

Включить production только после owner sign-off по ruleset, экономике, ролям, copy и legal/security review. Опубликовать `/help`, правила и контакт поддержки; первые 48 часов вести incident log.

## Экономика первого запуска

Временная baseline-конфигурация: `1 000 JOKERGEM` welcome, `250` daily раз в 24 часа, `300` relief ниже `50` раз в 72 часа. До отдельного решения отсутствуют покупки, Stars, вывод, обмен, призы и реальные деньги.

## Что двигает сроки

| Фактор | Влияние |
|---|---|
| Свежий токен, домен и доступы | Блокируют реальный Telegram/staging контур. |
| Финальные RTP/лимиты | Нужны до тематического наполнения и beta. |
| Согласование визуальных прав | Блокирует использование персонажей/аватаров в production. |
| Stars или любая платная ценность | Отдельный scope, legal review, support и возвраты. |
| Несколько чатов | Усложняют роли, настройки и нагрузочные сценарии. |
