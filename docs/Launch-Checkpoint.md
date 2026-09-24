# Чекпоинт запуска — 24 сентября 2026

Состояние подготовки боевого запуска Бурмалдозы. Сверено с `main` на коммите `80ef473`
(после слияния PR #8), `dev/BuildSpec.md` и `docs/Development-Roadmap.md`.

Репозиторий публичный. Поэтому здесь нет секретов и инфраструктурных идентификаторов:
пароли, токены, приватные ключи, IP-адрес сервера и пути на ПК владельца хранятся только у
владельца (менеджер паролей) и в `.env` на сервере.

## 1. Уже выполнено (подтверждено в репозитории)

| Что | Где |
|---|---|
| Правила и окружение Claude Code (`AGENTS.md`, `CLAUDE.md`, SessionStart hook) | PR #9, в `main` |
| Исправления аудита 1–4: welcome 1 000 при первом входе, `POST /api/v1/wallet/relief/claim`, CORS для `MINIAPP_URL` с путём, тайм-аут авторизации WebSocket, привязка idempotency key к кошельку | PR #10, в `main` |
| Review follow-up Codex к PR #10: непредсказуемый welcome key, сверка типа операции при replay, нормализация CORS origin | PR #12, в `main` |
| Blackjack Deck A — утверждённое визуальное направление (превью) | PR #8, в `main` |
| Методы клиента Mini App `claimDailyBonus` / `claimReliefGrant` (без UI) | `apps/miniapp/src/lib/api/client.ts` |
| Проверки здоровья API: `/health/live` и `/health/ready` (PostgreSQL + Redis) | `apps/api/app/main.py` |

## 2. Со слов владельца (в репозитории не проверяется)

- VPS HostKey NL (4 vCPU / 6 GB / 120 GB SSD) оплачен и ждёт переустановки. Сейчас на нём
  выводимый из эксплуатации YUVI-бот.
- Домены `burmaldoza.ru` и `burmaldoza.online` куплены у Рег.ру; `.ru` ждёт подтверждения данных
  владельца.
- SSH-ключ владельца `ed25519` создан; приватная половина хранится только на ПК владельца.

## 3. Принятые решения

- **YUVI выводится из эксплуатации.** Сервер переходит под Бурмалдозу, репозиторий
  `YUVI-BOT-v2` архивируется, токен YUVI-бота отзывается. Данные YUVI не переносятся.
- **Домен:** основной адрес — `https://burmaldoza.ru`, `burmaldoza.online` перенаправляется на него.
- **Схема:** Mini App и API на одном домене за Caddy с TLS от Let's Encrypt. Наружу открыты только
  80/443 и SSH; PostgreSQL, Redis и API без публичных портов.
- **Portainer — только через SSH-туннель** (решение Hainox, 24.09.2026): порт 9443 наружу не
  публикуется, контейнер слушает `127.0.0.1:9443`; вход — `ssh -L 9443:127.0.0.1:9443` и
  `https://localhost:9443` на ПК владельца.
- **Кто делает деплой:** локальный агент на ПК владельца. У облачного Claude нет SSH-доступа,
  поэтому он проверяет PR деплоя, а на сервер не заходит.
- **Ключи:** приватный SSH-ключ не попадает в репозиторий, `.env` и чаты. Для автодеплоя позже
  нужен отдельный deploy-ключ в GitHub Secrets.
- **Сертификаты:** Let's Encrypt через Caddy; платный DomainSSL и хостинг Рег.ру не нужны.

## 4. План (ещё не выполнено)

### Владелец (веб-панели)
1. **HostKey → переустановка:** указать публичный ключ `id_ed25519.pub`, удалить старый ключ,
   сгенерировать новый root-пароль, Ubuntu 22.04 **без** шаблона Portainer: шаблон публикует 9443
   наружу (см. R1).
2. **Portainer** ставит локальный агент на `127.0.0.1:9443`; пароль администратора владелец задаёт
   через SSH-туннель сразу после установки.
3. **DNS:** A-записи `@` и `www` для обоих доменов → IP сервера. Остальные записи не трогать.
4. **Рег.ру:** завершить подтверждение данных владельца для `burmaldoza.ru`.
5. **@BotFather:** создать бота Бурмалдозы и отозвать токен YUVI. Новый токен вводить только в
   `.env` на сервере.
6. **GitHub:** заархивировать `YUVI-BOT-v2`.
7. **Не трогать** домен и хостинг JiraJura в том же аккаунте Рег.ру.

### Локальный агент (Codex) — PR деплоя
Ветки `codex/production-deploy` и PR деплоя пока нет.
1. Пользователь `deploy`, ufw, fail2ban, unattended-upgrades, swap. Вход по паролю отключать
   только после проверки входа по ключу.
2. `docker-compose.prod.yml` с Caddy и `docs/Deploy-Production.md`. Caddy проксирует `/api/*`
   (включая WebSocket `/api/v1/rooms/{id}/events`) и `/health/*` в API, остальное — в Mini App.
3. Сборка Mini App с `PUBLIC_API_BASE_URL=https://burmaldoza.ru` — это **build-arg образа**, а не
   runtime-переменная (см. R3). В `.env` сервера: `MINIAPP_URL=https://burmaldoza.ru`,
   `ENVIRONMENT=production`, новый `BOT_TOKEN`.
4. Ночной зашифрованный `pg_dump` вне сервера; пароль шифрования хранится у владельца. Без
   него копии бесполезны — это урок YUVI.
5. BotFather: Mini App URL = `https://burmaldoza.ru`.

### CCode (очередь, по одной ветке на задачу)
1. **Issue #6** — UI Blackjack-комнаты по Deck A (PR #8 уже в `main`), ветка
   `ccode/blackjack-ui`.
2. **Issue #11** — только после #6, от свежего `main`, ветка `ccode/wallet-grants-ui`. Scope:
   - последовательная первичная загрузка: `getCurrentUser()`, затем `getWallet()`, не
     параллельно; баланс берётся только из ответа `getWallet()`;
   - кнопки **Daily** (`claimDailyBonus`) и **Relief** (`claimReliefGrant`) только в live API
     mode, новый `crypto.randomUUID()` на каждую попытку, баланс — только из `balance_after`,
     409 — ожидаемый отказ (cooldown или грант недоступен).
   - **Help UI в scope не входит** — только по отдельному решению Hainox.

### Claude
- Read-only review PR деплоя против этого чекпоинта, когда PR будет готов.

## 5. Открытые блокеры

| Блокер | Кто |
|---|---|
| Переустановка сервера, DNS, подтверждение `burmaldoza.ru` | Владелец |
| Новый BotFather-токен (отзыв YUVI) | Владелец |
| PR деплоя (`codex/production-deploy`) не создан | Codex |
| Daily/Relief UI и последовательная загрузка кошелька (Issue #11, ждёт #6) | CCode |
| Пункты 5–6 аудита (`docs/Code-Audit-2026-09-23.md`) | Codex |
| Слияние PR #14 (гонка первого входа) и PR #16 (граница одного API-воркера) | Hainox после review |

## 6. Условия запуска

### Технический запуск (закрытый контур)
- `https://burmaldoza.ru` открывает Mini App с валидным сертификатом; `burmaldoza.online`
  перенаправляет на него.
- `https://burmaldoza.ru/health/ready` → 200.
- Mini App работает в live API mode, а не в demo.
- `/start` в боте → Mini App → новый игрок получает 1 000 JOKERGEM → спин слота проходит.
- PostgreSQL, Redis и API недоступны снаружи напрямую.
- Резервная копия создаётся **и восстанавливается** на отдельной базе.
- CI на `main` зелёный: Python lint/tests, PostgreSQL integration, Mini App check/test/build,
  E2E (`pnpm verify`, `pnpm test:py`, `pnpm lint:py`, `pnpm miniapp:e2e`).

### Публичный запуск (по `dev/BuildSpec.md` и `docs/Development-Roadmap.md`)
- Ручной QA iOS, Android и Telegram Desktop на staging.
- Утверждённые RTP и лимиты, финальные ассеты; целевой чат, владельцы, модераторы, FAQ и поддержка.
- Юридическая проверка и security review.
- Опубликованы `/help`, правила и контакт поддержки; первые 48 часов ведётся журнал инцидентов.

## 7. Риски, найденные при сверке

- **R1. Docker в обход ufw.** Опубликованные Docker-порты (`ports: "9443:9443"`, `"8000:8000"`)
  открываются через iptables мимо ufw, поэтому правило ufw их не закрывает. Решение: Portainer
  только через SSH-туннель на `127.0.0.1:9443` (принято); в `docker-compose.prod.yml` у PostgreSQL,
  Redis, API и Mini App нет `ports` — наружу публикует только Caddy (80/443). Текущий
  `docker-compose.yml` для разработки публикует API и Mini App и для продакшена не годится.
- **R2. Публичный репозиторий.** В первой версии этого документа (коммит `b9d8b65` ветки
  `claude/launch-checkpoint`) были IP сервера и путь к ключу на ПК владельца; из текущей версии
  они убраны, но остаются в истории ветки. Если это критично — слияние через squash и удаление
  ветки после слияния.
- **R3. Demo-режим вместо live.** `PUBLIC_API_BASE_URL` читается при сборке
  (`import.meta.env`); при пустом значении `isLiveApiEnabled` возвращает `false`
  (`apps/miniapp/src/lib/api/runtime.ts`), и Mini App молча работает в demo. Условие
  «live API mode» в разделе 6 это проверяет.
- **R4. Первый вход.** Одновременный первый вход двумя запросами может дать `IntegrityError` на
  `users.telegram_user_id` (записано в `dev/ProjectLog.md`). Серверное исправление — PR #14
  (`codex/wallet-bootstrap-hardening`, открыт, в `main` ещё нет); последовательная загрузка из #11
  дополнительно снижает риск со стороны Mini App.
- **R5. Один API-воркер.** Пока EventBus живёт в памяти процесса, продакшен поддерживает только один
  процесс, один Uvicorn-воркер и одну реплику API (PR #16, открыт). `docker-compose.prod.yml` не
  должен масштабировать API.
