# Project Log

## 2026-09-14 — аватар Memendoza в шапке Pages-пилота

- Вместо буквы в левом углу добавлен локальный JPEG аватара публичного канала Memendoza `@meodp` из официальной Telegram-страницы; runtime-загрузка с внешнего домена не нужна.
- Аватар отображается кругом 32×32 px и имеет осмысленный alt-текст.
- Верификация: `git diff --check`; headless Edge загрузил изображение 320×320, отрисовал его 32×32 с `border-radius: 50%`; скриншот проверен визуально. В mobile emulation при viewport 336 CSS px горизонтального переполнения и наложения в шапке нет.
- Открыто: нет.

## 2026-09-13 — проектная основа

- Подготовлен независимый пакет проектирования для Memendoza Bot.
- Зафиксированы результаты наблюдения за чатами Memendoza, «Сливы в очко» и HAVD discuss, а также полезные паттерны существующих комьюнити-ботов.
- Решение: Mini App как главный интерфейс, бот как точка входа и социальный слой, экономика через серверный неизменяемый журнал операций.
- Верификация: просмотр Telegram осуществлён без отправки команд, удаления или изменения закреплённых сообщений.
- Открыто: утвердить первую игру, правила экономики, админов, целевой чат и границы Stars.

## 2026-09-13 — фронтенд-решение

- Заменён предложенный React/Vite на SvelteKit + TypeScript + `adapter-static`.
- Причина: SvelteKit даёт компактный мобильный интерфейс и статическую сборку без смешивания фронтенда с FastAPI.
- Верификация: обновлена таблица стека, структура репозитория и граница ответственности Mini App/FastAPI.

## 2026-09-13 — название проекта

- Проект переименован в «Бурмалдоза».
- Memendoza зафиксирован как первое сообщество запуска, а не как название продукта.

## 2026-09-13 — репозиторий foundation

- Создан независимый Git-репозиторий `burmaldoza`.
- Добавлены FastAPI liveness endpoint, изолированная конфигурация бота, статический SvelteKit shell, Python-пакеты domain/contracts, Docker Compose для PostgreSQL/Redis и unit-test API.
- Не реализованы ставки, баланс, игровые алгоритмы, Stars и обработчики Telegram-команд: BuildSpec остаётся Draft.
- Верификация: Python-модули успешно скомпилированы через `compileall`. `pytest` не установлен в рабочем окружении; Docker Engine отсутствует, поэтому pytest и `docker compose config` нужно выполнить после установки зависимостей по `docs/Local-Setup.md`.

## 2026-09-13 — план реализации

- Добавлен поэтапный roadmap от Product lock до публичного запуска и пострелизных модулей.
- Базовая оценка: 7–9 календарных недель до запуска виртуального казино в одном сообществе без Stars в первом релизе.
- GitHub-коннектор подтверждает владельца `Hainox`, но не предоставляет операцию создания репозитория; публикация foundation ожидает создания пустого `Hainox/burmaldoza`.

## 2026-09-13 — Pages demo

- Добавлен отдельный статический demo-build рулетки в `docs/pages-demo` и workflow GitHub Pages.
- Решение: demo не использует Telegram, API, базу, деньги, платежи или сохранение баланса; локальная анимация нужна только для показа будущего UX.
- Верификация: HTML подготовлен как автономная статическая страница. Реальный deploy ожидает создания `Hainox/burmaldoza` и включения GitHub Pages через GitHub Actions.

## 2026-09-13 — README visual redesign (local preview)

- Добавлены hybrid hero source layout, растровый subject с прозрачностью, архитектурная SVG-схема и переписан README вокруг реальных границ foundation.
- Решение: generated subject сообщает тему виртуальной игровой комнаты; все названия, функции, команды и архитектурные данные остались в SVG/Markdown, а не внутри сгенерированного изображения.
- Центральный механизм subject исправлен: четыре равномерно расположенных рычажка. Так как генерация запекла служебную шахматную подложку, она удалена только по нейтральным пикселям, связанным с краем; исходная генерация сохранена в `assets/readme/source/hero-subject-generated.png`.
- Публикация в GitHub ожидает визуальной проверки локального preview и отдельного подтверждения владельца.

## 2026-09-13 — подготовка первой публикации и проверка README

- Владелец создал публичный `Hainox/BURMALDOZA` и явно разрешил push. Проверенная исходная ветка `main`: `9eee347af5389e475b346121ddb0e2504705a7ff`, только стартовый README. Публикация подготовлена поверх этой истории, без force push.
- README теперь разделяет реализованные заглушки, статическое Pages-демо и целевые функции. Добавлены запуск демо без Node.js/Telegram, сценарный характер исходов, правильный регистр URL Pages и ограничения текущего билда.
- Согласованы README, `Local-Setup.md` и `Pages-Deploy.md`: Python-команды используют `uv run`, отсутствие runner бота указано явно, создание репозитория больше не требуется.
- Верификация: upstream `audit_readme.py` проверил оба изображения; ссылки README, JSON, SVG и Python compileall прошли. В Node.js проверено 10 сценариев статического демо: границы ввода, три исхода, блокировка кнопки и сброс состояния. Браузерная проверка в этом проходе не выполнялась.
- Полные проверки не завершены: `pytest` и `ruff` отсутствуют; Docker не установлен. `pnpm miniapp:check` и `pnpm miniapp:build` остановились на `ERR_PNPM_IGNORED_BUILDS` для `esbuild@0.28.2`. Одобрение install-script не выдавалось и защита не отключалась. Сохранён полученный lockfile; автоматически добавленный pnpm незаполненный шаблон `allowBuilds` удалён.
- Открыто: решение владельца о доверии install-script, установка Python/Docker-зависимостей, полная проверка каркаса, включение Pages и утверждение BuildSpec. Публикация каркаса не означает запуск игрового сервера.

## 2026-09-13 — разрешение install-script и повторные проверки

- После явного разрешения владельца изучен install-script `esbuild@0.28.2` и добавлено адресное `allowBuilds: { esbuild: true }`. Разрешение на остальные dependency scripts не выдавалось.
- `pnpm install --frozen-lockfile` завершён; `svelte-check`: 0 ошибок и 0 предупреждений; `pnpm miniapp:build` успешно создал статическую сборку.
- Установлены Python-зависимости через `uv sync --all-groups`, сохранён `uv.lock`. Исправлено только форматирование импортов в API и его тесте после двух ошибок I001 линтера.
- Повторная верификация: `uv run ruff check .` — ошибок нет; `uv run pytest -q` — 1 passed, 2 deprecation-предупреждения Starlette/httpx/AnyIO. README и инструкции синхронизированы с этими результатами, команды установки используют lockfile.
- Открыто: Docker/Compose и браузерная проверка вёрстки; включение Pages; будущая миграция тестового клиента при обновлении зависимостей; утверждение BuildSpec.

## 2026-09-13 — коррекция README hero

- Убран правый текстовый блок, который перекрывался растровой рулеткой и делал копирайт нечитаемым.
- Создан новый прозрачный subject `hero-subject-v2.png`: ровно четыре одинаковых диагональных латунных рычажка вокруг центрального узла, без верхнего пятого рычага.
- Hero пересобран в `hero-v2.png`: текст помещён в независимую левую колонку, рулетка находится справа и не пересекается с текстом.
- Верификация: визуально проверен итоговый PNG 1200×470 и наличие alpha-канала у subject; исходный hero сохранён для истории.

## 2026-09-14 — расширение интерактивного пилота

- В статический Pages-пилот добавлены базовые блэкджек и слот. Все три игры используют общий виртуальный баланс и локальную историю только в памяти вкладки.
- Для демо зафиксированы последовательности рулетки, раздач и барабанов. Блэкджек показывает действия «Взять карту» и «Стоп»; параллельные игровые действия блокируются до завершения текущего раунда.
- Обновлены README и чек-лист Pages с границами пилота и точными ручными сценариями.
- Верификация: синтаксис встроенного JavaScript и структура HTML прошли локально. В браузере проверены рулетка, раздача и ход в блэкджеке, спин слота, валидация ставки, общий баланс, блокировка параллельных действий и сброс. Автоматизированная проверка узких экранов не запускалась: Playwright отсутствует, а доступный Corepack использует pnpm 11.9.0 при требуемом проектом pnpm 11.19.0.

## 2026-09-14 — клиентский пилот и SvelteKit-контур

- Из README, проектного журнала и документации убраны сравнения с внешними проектами.
- Статическое Pages-демо пересобрано в клиентский интерактивный пилот: выбор цвета и количества виртуальных жетонов, сценарный локальный результат, история и сброс без Telegram-авторизации, сети, платежей или сохранения данных.
- Зафиксирован стек Mini App: SvelteKit 2, Svelte 5, TypeScript, Vite и `adapter-static`; подключение Zod, Svelte Query и тестовых библиотек отложено до утверждённого BuildSpec и появления реальных API-контрактов.
- GitHub Pages включён с источником GitHub Actions; публикация запускается изменениями `docs/pages-demo` или workflow.
- Верификация: `git diff --check`, `docker compose config -q` с временным тестовым паролем, `uv run ruff check .`, `uv run pytest -q` (1 passed, 2 известные deprecation-предупреждения), `pnpm miniapp:check`, `pnpm miniapp:build`, синтаксис скрипта пилота и локальный браузерный сценарий выбора цвета, раунда и сброса прошли.

## 2026-09-14 — ремонт и обновление локального GSD

- Диагностирована рассинхронизация update-check: worker обращался к legacy-пакету, а hook-потребители читали несовпадающий cache. До правки три хука сохранены отдельно; перед global update создана проверенная копия 162 custom-записей (161 файл по SHA-256 и junction-ссылка).
- Codex global обновлён с GSD Core `1.4.4` до `1.14.0`; `update-context` подтверждает `GLOBAL / codex`, а `check-latest-version` — latest `1.14.0`. После установки `.cmd` записал `@opengsd/gsd-core` и `update_available: false`; синтаксис worker/statusline/banner проверен.
- Installer перенёс 67 GSD skill-каталогов из legacy `.codex/skills` и установил 72 GSD-навыка в `.agents/skills`. `agent-skills` plugin-cache и junction `skills/video-use` остались на месте. Старые context-monitor hook references/scripts удалены установщиком как устаревшие; резервная копия сохранена.
- Открыто: installer сообщил о 357 не заменённых `.claude` path references в 118 файлах, которые могут не разрешаться в Codex; vendor-файлы вручную не менялись. До установки changelog extractor отсутствовал, поэтому preview был недоступен.

## 2026-09-14 — анимации раундов Pages-демо

- Добавлены переходы рулетки, последовательная раздача/раскрытие карт блэкджека и независимые остановки барабанов слота; действия блокируются на время перехода.
- Верификация: `git diff --check`, синтаксис встроенного JavaScript; отдельный headless Edge проверил раунд каждой игры, сброс состояния, нулевые ошибки/предупреждения консоли и отсутствие внешних запросов. На ширине 390 px горизонтального переполнения нет; завершённое состояние слота проверено после конца stop-анимаций.
- Открыто по этому изменению: нет.

## 2026-09-20 — server-authoritative game platform foundation

- Зафиксированы три комнаты первого skeleton: 3×7 Slot, Blackjack GFL и heads-up Hold’em / RGG Poker.
- Добавлены pure domain rules, OS-backed CSPRNG adapter, deterministic Monte Carlo runners, PostgreSQL/Alembic models, atomic Jokergem ledger, Telegram `initData` verification, room snapshots/events, reconnect handling и safe aiogram commands.
- Jokergem (`JOKERGEM`) оставлен provisional display name. Baseline economy: welcome `1000`, daily `250`, relief `300` below `50` once per `72h`; real money, Stars, withdrawal and exchange remain out of scope.
- Собран native mobile-first Mini App shell: dashboard, balance, three room views, safe areas, focus states, reduced-motion reducer, explicit `SERVER CONFIRMED · DEMO` boundary и CSS choreography for resolving/outcome/settle states.
- Верификация backend: `uv run --locked pytest -q` — 68 passed, 3 PostgreSQL integration tests skipped без `TEST_DATABASE_URL`; `uv run --locked ruff check .` — clean; `uv lock --check` — clean. Отдельный запуск integration с `TEST_DATABASE_URL=postgresql+asyncpg://...@127.0.0.1:5432/...` проведён и дал ожидаемый `ConnectionRefusedError`, потому что PostgreSQL/Docker в текущем runtime отсутствует.
- Верификация Mini App: `pnpm install --frozen-lockfile`, `uv sync --locked --all-groups`, `pnpm miniapp:check` — 0 errors/0 warnings; `pnpm miniapp:test` — 4 passed; `pnpm miniapp:build` — passed.
- E2E-сценарии добавлены для dashboard, reduced motion, result confirmation и reconnect. Запуск остановлен до тестов: в окружении нет Chromium, а CDN Playwright вернул timeout/502 при установке browser runtime. Это открытый инфраструктурный блокер, не зелёный результат.
- Добавлены Dockerfile для API, bot и Mini App, Compose services `postgres`, `redis`, `api`, `bot`, `miniapp` и обязательный CI job с PostgreSQL/Redis services и Monte Carlo artifacts. YAML/JSON/offline Alembic проверены; `POSTGRES_PASSWORD=local-test BOT_TOKEN=placeholder docker compose config -q` проведён и заблокирован отсутствующим бинарником `docker`.
- Зафиксированы отчёты `reports/monte-carlo/*.json`: 100 000 trials, seed `42`, ruleset version и source commit для трёх skeleton-симуляций. Эти числа не являются approval монетизации или юридической оценкой.

## 2026-09-21 — product lock и full-body README hero

- Временное название виртуальной валюты подтверждено как **Jokergem**; baseline welcome/daily/relief уже отражён в foundation.
- Slot v2 зафиксирован как motion-критичная задача: полная прокрутка барабанов, staged stop, подтверждённый `SlotOutcome`, payout highlight и пять Free Spins. Бонусная мини-игра вынесена на отдельную переделку.
- Для совместной работы с Command Code добавлен handoff workflow: каждая передаваемая задача получает точный model id, effort, ветку, границы файлов и acceptance criteria.
- README hero заменён на присланную full-body композицию трёх персонажей; точный текст и статусы остаются в SVG-слое, а новый raster hero пересобран из этой основы.
- Исправлен дрейф времени в auth route test: тестовая подпись теперь создаётся за пять минут до фактического запроса, а production TTL проверки Telegram не ослаблен.

## 2026-09-23 — server-first Blackjack room

- После слияния PR #3 и #4 на актуальную `main` начат Blackjack GFL server slice. Зафиксирован контракт в `docs/superpowers/specs/2026-09-23-blackjack-server-room-design.md`: ставка 25–100 JOKERGEM, дилер стоит на soft 17, натуральный блэкджек платит 3:2 целыми жетонами, split не входит в ruleset.
- Добавлено приватное server-only состояние комнаты с миграцией `20260923_0003`; hole card не попадает в snapshot, event или публичный JSON до завершения руки. `deal`, `hit`, `stand`, `double` используют доменный движок; списание ставок, доплата double, выплата, ledger и сохранённый action event проходят в одной PostgreSQL транзакции.
- Повтор `action_id` возвращает сохранённое событие; stale state version отклоняется существующим контрактом. Mini App разбирает только канонический результат сервера и восстанавливает баланс/результат из snapshot; payload `deal` содержит явную ставку. Промежуточные Blackjack-действия не выдаются за settlement, баланс после списания приходит в публичном состоянии solo-комнаты.
- Добавлена явная проверка push при натуральном блэкджеке обеих сторон; существующий domain расчёт уже возвращал ставку корректно, поэтому production-правило не менялось.
- Верификация: изолированный PostgreSQL 16, `uv run --locked alembic upgrade head`, `uv run --locked pytest -q` — 85 passed; `uv run --locked ruff check .` — clean; `pnpm@11.19.0 verify` — Svelte 0 ошибок/предупреждений, 24 Vitest passed, production build passed. E2E локально не запускался; CI остаётся обязательным PR gate. Два существующих Starlette/httpx deprecation warning остались без изменений.
- Открыто: CCode UI handoff Blackjack после фиксации контракта и отдельный server/domain slice для Hold’em. Публичный launch, staging и owner release decisions не выполнены.
