# Project Log

## 2026-10-14 — хаб «Ночной атриум», #90

- Поручение владельца: полный редизайн только хаба; выбран вариант 2 Product Design.
  Дополнение: M4 SOPMOD / SOPPO — главный персонаж портала Blackjack по двум портретам.
  Объём утверждённого изменения записан в BuildSpec до реализации.
- Ветка `codex/hub-atrium-redesign`, база `5ea8697`; отдельный worktree, сторонние правки
  Blackjack и локальные настройки не затронуты. Один implementer UI, три asset-only агента
  по image-to-code skill. Маскоты/арки/фон/logo — отдельные WebP, иконки Tabler/Supericons MIT.
- Новый HubLobby: выбор трёх активностей и отдельный вход, реальные баланс/бонусы,
  Играть/Рейтинг/История, DEMO граница, декоративные циклы/переходы, pause/reduced motion
  и остановка background при скрытии вкладки. Игровые обработчики, комнаты и backend не менялись.
- Проверки: `pnpm miniapp:check` — 0 errors/warnings; `pnpm miniapp:test` — 44 passed;
  `E2E_PORT=4181 CI=true pnpm miniapp:e2e` — 51 passed, build successful внутри webServer;
  повтор hub-only для screenshot — 5 passed; `git diff --check` — passed.
  Доступны pnpm 11.19.0, Chromium нужной версии; Pillow использован только для WebP-конверсии,
  runtime-зависимости не добавлены. Непромоканные вспомогательные API в E2E дают 404;
  настоящий production/Telegram этим запуском не проверяется.
- CUA Chrome: combined сравнение источника и iframe; исправлены размер title,
  высота reception и избыточная строка selection, яркость порталов. Второй проход — passed.
  Вручную проверены вход Blackjack, возврат с сохранением выбора/паузы и панель рейтинга.
- Handoff: `assets/design/hub-atrium/README.md`, source/render screenshots,
  `apps/miniapp/design-qa.md`, `apps/miniapp/static/hub/sources.json` и лицензия иконок.
  Работа сохранена в draft PR по просьбе владельца обеспечить продолжение при остатке лимита 5%.
- Осталось: независимое review и CI на опубликованном head, Android/iOS Telegram manual QA.
  Параллельный PR #92 bet-picker может пересекаться с +page.svelte: сохранять его игровые
  изменения отдельно. #87 профиля Hold’em не входит в редизайн. Merge/Pages/server deploy не выполнялись.

## 2026-10-12 — инструкции для агентов: разделы «Неочевидное» и «Указатели» (PR #49)

- В `AGENTS.md` добавлены разделы «Неочевидное» (публикация, подводные камни, конвенции, причины решений, что не трогать) и «Указатели»; все прежние правила сохранены дословно. Новые `CODING_STANDARDS.md`, `docs/agents/security.md` и `docs/agents/git.md` подгружаются по указателям.
- `AGENTS.md` подключается один раз — через `@../AGENTS.md` в `.claude/CLAUDE.md`; упоминание несуществующей настройки `instructionFiles` в `CLAUDE.md` заменено.
- Плагин agents-kit в `.claude/settings.json` не подключается: облачные сессии не ставят плагины из настроек репозитория.
- Проверки: только документация; CI `verify` на PR. Остаточный риск: формулировки «Неочевидного» сверены с кодом и workflow, но не проверены владельцем.
## 2026-10-12 — правила слота внутри пакета домена (PR #50)

- `slot_skeleton.json` перенесён из `tests/fixtures/` в `packages/domain/src/burmaldoza_domain/games/`; `load_skeleton_config()` по умолчанию читает файл рядом с собой. Содержимое и `ruleset_version` (`slot-skeleton-1`) не менялись, отчёты Monte Carlo не перегенерировались.
- Из `docker-compose.prod.yml` убран mount `configs.slot_ruleset`: API-образ получает файл вместе с `packages/`. `docs/Deploy-Production.md` обновлён.
- Проверки: новый тест `test_default_ruleset_ships_inside_the_domain_package` сначала красный, после переноса зелёный; `pytest tests/unit` — 139 passed; `ruff check` и `ruff format --check` — чисто; CI `verify` (compose build + e2e) — passed.
- Review Codex недоступен (лимит), merge — по прямому разрешению владельца от 2026-10-12. Остаточный риск: после деплоя проверить создание комнаты со слотом.

## 2026-09-29 — demo-copy в игровых комнатах (#37, PR #40)

- По разрешению владельца расширен scope только на copy в `SlotRoom.svelte`, `BlackjackRoom.svelte` и `PokerRoom.svelte`: DEMO теперь прямо обозначает клиентское состояние без серверного подтверждения; live-формулировки сохранены. Баланс расчёта Blackjack в DEMO подписан `DEMO BALANCE`.
- E2E дополнен проверками DEMO Slot/Blackjack/Hold’em и live Slot/Blackjack. Проверены mobile viewport 375×812 и reduced motion; мобильные демо-состояния отрисовались без горизонтального переполнения и обрезанных подписей.
- Проверки: `pnpm miniapp:check` — 0 ошибок/предупреждений; `pnpm miniapp:test` — 25 passed; `pnpm miniapp:build` — passed; целевые Playwright E2E — 24 passed (Chromium, 375×812).
- Осталось: отправить изменения в draft PR #40, дождаться CI и завершить merge/Pages публикацию после принятия PR.

## 2026-09-28 — честные метки демо-результата (#37)

- `ResultBand.svelte` разделяет завершённость исхода и подтверждение сервера. Demo во время движения подписан `RESOLVING · DEMO RESULT`, после завершения — `DEMO ROUND · БЕЗ СЕРВЕРНОГО ПОДТВЕРЖДЕНИЯ`; выплата отображается как результат демо, а `confirmed-balance` остаётся только для live. Live-метка `SERVER CONFIRMED · LIVE` сохранена.
- В двух demo `detail` Slot и Hold’em убраны утверждения о серверном результате/подтверждённом действии. Ожидающий demo-исход также получил отдельный текст.
- Playwright покрывает промежуточное и завершённое состояние Slot, Blackjack и Hold’em; live Slot по-прежнему проверяет подтверждённые grid и balance. Красный Chromium run `36430637852` подтвердил регрессию до исправления: 6 проверок упали, 19 прошли.
- Проверки после исправления: `pnpm miniapp:check` — 0 errors/0 warnings; `pnpm miniapp:test` — 25 passed; `pnpm miniapp:build` — passed; GitHub Actions Verify game platform run #145 — success (148 Python tests, 25 Playwright e2e, Docker build и Monte Carlo evidence прошли). Изменения ограничены UI, двумя demo-строками и проверками; расчёты, API, live-результаты и deploy не менялись.
- Открыт draft PR #40 в `main`; merge и Pages-публикация не выполнялись.

## 2026-09-27 — изоляция внутренних API-маршрутов (#31)

- Назначение issue #31: Codex / `gpt-6-sol` / `high`; точная модель и effort текущего runtime не отображаются, поэтому совпадение runtime с метаданными не подтверждено.
- Ветка `codex/internal-api-isolation`: функциональный коммит `f371a94`, основанный на предыдущем `main`; перед передачей ветка локально обновлена merge с актуальным `origin/main` `d53af57`. Конфликты были только в append-only `ChangeLog.md` и `dev/ProjectLog.md`; записи обеих сторон сохранены.
- Production Caddy возвращает 404 для `/api/v1/internal/*` до публичного API proxy. Бот обращается по точному адресу `http://api:8000` через отдельную internal-сеть `bot_api`; production-конфигурация бота разрешает HTTP только для этого адреса. Токенная защита внутренних маршрутов сохранена.
- Runbook описывает внешний 404 и проверку `/balance` и `/top`; добавлены тесты разрешённого внутреннего URL и отклонения других HTTP URL.
- После синхронизации: Ruff — passed; `uv run --locked pytest -q tests/unit/test_bot_config.py` — 12 passed; `docker compose -f docker-compose.prod.yml config --quiet` — passed с синтетическими значениями; `git diff --check` — passed. До синхронизации Caddy прошёл `caddy validate` и smoke-тест публичных/внутренних маршрутов, включая encoded slash/name и двойной slash. Изолированный контейнерный прогон подтвердил доступ бота к API по внутренней сети; тестовый wallet-запрос вернул ожидаемый 404 для несуществующего пользователя.
- Открыто: draft PR #33 опубликован; CI и review ожидаются. Реальные `/balance` и `/top` в Telegram, production DNS/TLS и сервер не проверялись. Merge, deploy и SSH не выполнялись.

## 2026-09-27 — CCode issue #11: wallet grants UI (meta/muse-spark-1.3-contributor, high)

- От свежего `origin/main` (`01705de`, PR #14 принят) создана ветка `ccode/wallet-grants-ui`. Gate по issue #6 не пройден: PR #15 открыт и не слит.
- `apps/miniapp/src/lib/components/WalletGrantControls.svelte` (новый): daily/relief кнопки только в live-режиме, свежий `crypto.randomUUID()` на каждый claim, блокировка кнопки на время pending, баланс только из `balance_after`, 409 как ожидаемый cooldown, остальные ошибки как retryable.
- `apps/miniapp/src/routes/+page.svelte`: стартовая загрузка идёт одним `getWallet()` без параллельного `getCurrentUser()`; панель выдач показана только в live API mode; demo-выдача не имитируется.
- `apps/miniapp/tests/e2e/wallet-grants.spec.ts` (новый): daily success + повторный тап, relief 409, live/demo различие.
- Проверки: `pnpm miniapp:check` — 0/0; `pnpm miniapp:test` — 25 passed; `pnpm miniapp:build` — passed; `pnpm --dir apps/miniapp exec playwright test tests/e2e/wallet-grants.spec.ts --workers=1` — 3 passed (Chromium, Windows).
- Открыто: PR из `ccode/wallet-grants-ui` в `main` после завершения issue #6; ручная проверка на реальном Telegram WebView не выполнялась.

## 2026-09-27 — локальный интерактивный журнал проекта (#21)

- Повторная сверка 27.09.2026: `origin/main` `01705de935ee7f805dd829d6ddc1bde1b6846004`; встроенный снимок обновлён до 9 публичных issues и 20 PR. Он отражает слияние #16, #17 и #24, закрытие review #22 и открытые draft PR #25, #26, #28 вместе с PR #29. Очередь handoff приведена к этим состояниям: добавлено issue #27, указан текущий PR и его статус из снимка для каждой активной задачи, а устаревшие условия запуска убраны. При следующем обновлении страницы статусы вновь сверяются с GitHub API; редакционные зависимости требуют проверки в исходных issue перед передачей.
- Дополнительная браузерная проверка Chrome на локальном `file://`: поиск `#26` с фильтрами PR/открыт/Codex оставляет одну запись; слитые #14/#16/#17 видны; обновление получает GitHub API и сохраняет кэш, при отключённой сети показывает кэш и ошибку; копирование handoff #27 сработало. На ширине 320 px обнаружено и исправлено горизонтальное переполнение grid; повторная проверка 320/768/1440 px без переполнения. `prefers-reduced-motion` выключает плавную прокрутку; ошибок JavaScript нет. Продуктовые тесты не запускались.
- Добавлена автономная страница `docs/project-journal/` для локального открытия: этапы roadmap, поиск и фильтры публичных Issues/PR по типу, статусу и агенту, включая слитые PR, и очередь handoff с адресатом, моделью, effort, зависимостью, исходным issue и копируемым промтом. Mini App, API, domain, RNG, ledger и Pages workflow не менялись; внешних runtime-зависимостей нет.
- Статусы этапов 1–3 обозначены завершёнными только в пределах foundation/skeleton, этап 4 — частичным; production, ручная приёмка, beta и запуск не объявлены готовыми. Основания: `docs/Development-Roadmap.md`, `dev/BuildSpec.md` и исходные issue. Сверены публичный `main` (`07a7a750720def4054301c019113ad7000a9a813`) и GitHub API: стартовый снимок от 2026-09-27 00:10 UTC содержит 8 issues и 16 PR, включая слитый PR #14. Данные не содержат тел issue, секретов или персональных данных.
- Кнопка обновления читает публичные Issues/PR (до 1000 записей каждого типа) и SHA `main`, сохраняет ответ в `localStorage`; если история превышает лимит, неполный ответ отклоняется. При сетевой ошибке или лимите API показывает самый свежий ответ из памяти вкладки, кэша или датированного встроенного снимка с явным состоянием. Если браузер блокирует хранилище на `file://`, отображение и ручное обновление остаются доступными без сохранения между запусками.
- Проверка: `node --check` для JavaScript-файлов прошёл; `node docs/project-journal/test-offline.cjs` подтвердил сохранение свежего ответа после запрета `localStorage` и последующей сетевой ошибки. Этот тест также выявил и помог исправить неверную передачу `signal` при запросе SHA `main`. Node сверил структуру снимка, количество записей, SHA, URL и статус PR #14; Python `html.parser` проверил локальные ресурсы и основные ID, `tinycss2` — синтаксис CSS. Первоначально Browser Use заблокировал переход на `file://`, а Playwright MCP не подключился к расширению; последующая проверка через локальный Chrome описана выше. Ручной сценарий открытия, фильтров, обновления/офлайна и клавиатуры записан в `docs/project-journal/README.md`.
- Открыто: решение владельца о снятии draft и merge PR #25. Публикация отдельно не запрашивалась.

## 2026-09-23 — Claude Pro в рабочем процессе

- Claude Pro добавлен в процесс через отдельный Claude Code CLI: Codex отвечает за проектные решения и интеграцию, Claude Code — за изолированные небольшие задачи и независимый review, CCode сохраняет назначенную UI/motion handoff-роль. Один исполнитель на набор файлов; текущая Blackjack UI-задача #6 остаётся у CCode после gate PR #8.
- В `docs/Command-Code-Workflow.md` добавлены маршрутизация Claude Code, Pro-авторизация, shared usage, проверка `/status`, защита от случайного API-биллинга и шаблон handoff. Добавлен корневой `CLAUDE.md` с источниками истины и ограничениями проекта.
- Проверены текущие официальные документы Anthropic: Claude Code поддерживает вход Claude Pro; расход Pro общий с Claude.ai и IDE; `ANTHROPIC_API_KEY` может выбрать API-биллинг; tool output и прочитанное содержимое сессии попадают в локальные plain-text transcripts. Лимиты и доступные модели намеренно не закреплены числами/model ID; секретные файлы исключены из контекста.
- На этой рабочей станции `claude --version` отвечает `2.1.220 (Claude Code)`. Авторизация CLI, фактический Pro-вход и наличие API-переменной окружения не проверялись; каждая рабочая сессия обязана подтвердить Pro-вход через `/status`, не печатая секреты.
- Проверка изменений — документационная: `git diff --check`, локальные Markdown-ссылки разрешаются, code fences сбалансированы; продуктовый runtime не затрагивался.

## 2026-09-23 — интерактивное превью Blackjack Deck A/B

- В интерактивном Pages-превью добавлен переключатель Deck A / Deck B. Для Deck A закреплены RPK-16 на A♥ и AK-12 на K♥; состав и фильтры обновляются при переключении.
- После уточнения владельца Deck B скорректирована без дублей: M82A1 назначена на 6♥, PTRD — на 7♥ вместо PTRS. В каждом наборе 52 уникальные T-Doll. Портрет M82A1 скачан из IOP Wiki; ссылки на страницы файлов и статусы всех источников записаны в manifest. Согласие владельца ограничено некоммерческим GFL fan-preview/UI с атрибуцией и не является общей открытой лицензией.
- Для комнаты создан оригинальный концепт современного заброшенного здания с полицейским периметром. Это последнее решение владельца и оно заменяет более раннее «без оцепления»; мир — GFL 1 после Collapse, не WWII. Зафиксирована концепция фона звука: дождь, генератор/вентиляция, редкая приглушённая полицейская рация/сирена, тихий звук карт и подтверждённый сигнал результата; аудиофайлы и имитация воспроизведения не добавлялись.
- GitHub Pages workflow включает файлы Deck B и передаёт room concept вместе со страницей; Mini App runtime не менялся. Обновлён CCode handoff #6: Deck A для runtime, Deck B только для сравнения, UI-работа начинается после слияния PR #8.
- Локальный Playwright после замены прошёл: по 52 уникальные карты в каждой колоде, все 52 изображения B декодируются; поиск открывает 6♥ M82A1 и 7♥ PTRD; комната загружается; ширины 320/390/768 без переполнения, ошибок браузера и неуспешных запросов. Статус: `git diff --check` чистый. GitHub CI run `35879803569` и Pages deploy run `35880257002` завершились успешно. Живая страница и manifest отвечают HTTP 200; в браузере проверены A/B, 52 карты B, досье M82A1 на 6♥, PTRD на 7♥ и отсутствие PTRS в поиске. В GitHub Pages снова разрешена только ветка `main`.
- Открыто: PR #8 остаётся draft до отдельного решения о слиянии. CCode runtime UI не запускать до выполнения gate в issue #6.

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
- PR #5 (`71eff485`) слит в `main`; полный GitHub CI прошёл, включая E2E и Monte Carlo. CCode handoff зарегистрирован как issue #6, зависимость выполнена, задача готова к старту от свежего `main`.
- Hold’em server integration пока не начат: BuildSpec задаёт две позиции и действия, но отсутствуют join/seat API и утверждённая модель оппонента; текущий API умеет только создать solo-комнату для одного участника. Не угадывать эти продуктовые решения.
- Открыто: отдельная проверка `health/ready`, профиль/кошелёк/рейтинг и admin surfaces. Публичный launch, staging и owner release decisions не выполнены.

## 2026-09-24 — Claude Code: онбординг и исправления по аудиту

- PR #9 (Claude Code, облачная сессия) слит владельцем: `AGENTS.md` (общая справка агентов), `.claude/CLAUDE.md` (облачные заметки, импортирует `AGENTS.md`), SessionStart hook с зависимостями и Chromium для Playwright, `docs/Code-Audit-2026-09-23.md`. `CLAUDE.md` побайтно совпадает с версией из PR #8, чтобы PR сливались без конфликта. Запись размещена здесь, а не в начале или конце журнала, по той же причине.
- По явному разрешению владельца (API/ledger — зона Codex) ветка `claude/audit-fixes` закрывает находки аудита 1–4: welcome 1 000 начисляется при первом входе в той же транзакции, что и создание пользователя (случайный ключ на выдачу; однократность обеспечивается транзакцией и `welcome_granted_at`); добавлен `POST /api/v1/wallet/relief/claim`; CORS берёт origin из `MINIAPP_URL` без пути (Pages); WebSocket закрывается с 4401 через 5 с без авторизации; повтор idempotency key чужого кошелька отклоняется вместо выдачи чужого результата.
- Mini App получил только API-методы `claimDailyBonus`/`claimReliefGrant`; кнопки не добавлены — UI за CCode.
- **Для Codex (review):** (1) пользователи, созданные до этой правки, welcome не получат — в production их нет, backfill не делался; (2) одновременный первый вход двумя запросами по-прежнему может дать `IntegrityError` на `users.telegram_user_id` (было до правки); (3) `_db_get_or_create_wallet` всё ещё создаёт «фейкового» `User` при отсутствии пользователя — не трогал, это отдельное решение; (4) интеграционные PostgreSQL-тесты локально не запускались (нет Docker), проверяет CI.
- Верификация: `ruff` clean; `pytest` 88 passed / 6 skipped; `miniapp:check` 0/0; Vitest 25 passed; build ok; Playwright 9 passed. Новые тесты: CORS-origin с путём, WebSocket-тайм-аут, чужой idempotency key, полный путь «первый вход → welcome → relief 409 → daily → повторный daily 409» на SQLite.
- Открыто: кнопки daily/relief в Mini App (handoff для CCode); пункт 5–6 аудита.

## 2026-09-24 — review follow-up к PR #10

- Исходную реализацию PR #10 подготовил Claude Code CLI 2.1.281 через Pro с моделью `Opus 5.5 / High` (подтверждено владельцем); Codex (GPT-6, effort не отображался в runtime) в follow-up подтвердил три дефекта: предсказуемый welcome key позволял зарезервировать ключ для следующего пользователя; один UUID в разных типах wallet claims возвращал ложный успешный ответ; CORS не нормализовал регистр hostname и стандартные порты.
- В follow-up удалена derivation welcome key от последовательного user ID, wallet claims теперь сверяют тип операции при replay, а CORS приводит hostname/порт к browser Origin. Добавлены regressions для SQLite/API, памяти, client IDs и некорректных URL.
- Проверки на Windows / Python 3.13: `uv run --locked ruff check .` — clean; `uv run --locked pytest -q` — 115 passed, 6 skipped; `pnpm miniapp:check` — 0 ошибок/предупреждений; `pnpm miniapp:test` — 25 passed; `pnpm miniapp:build` — passed. Два существующих Starlette/httpx deprecation warnings остались.
- 6 пропусков — PostgreSQL integration tests: в локальном окружении не задан `TEST_DATABASE_URL`, PostgreSQL не запускался; их результат должен подтвердить GitHub CI на follow-up PR.
- GitHub Actions `Verify game platform`, run 74 (`35957785258`) на PR #12 завершился успешно: Python lint/tests, Mini App check/unit tests/build, Docker Compose image build, Playwright E2E и Monte Carlo evidence прошли.
- Дополнительно проверен реальный SQLite/API путь, где пользователь пытается повторно использовать чужой wallet request ID; операция отклоняется HTTP 409 и балансы обоих кошельков не смешиваются.
- Первый запуск Mini App всё ещё параллелит неиспользуемый `/api/v1/me` с `/api/v1/wallet`; исправление и wallet grants UI переданы в CCode issue #11 после PR #10 и issue #6, чтобы избежать пересечения `+page.svelte`.

## 2026-09-24 — чекпоинт подготовки запуска

- PR #10 (исправления по аудиту + review Codex из #12) слит владельцем.
- Инфраструктура (со слов владельца): VPS HostKey NL (4 vCPU / 6 GB / 120 GB) переходит под Бурмалдозу; YUVI выводится из эксплуатации без переноса данных. Куплены `burmaldoza.ru` (ждёт подтверждения данных) и `burmaldoza.online`.
- Решения: Caddy + TLS, один origin для Mini App и API; деплой делает локальный агент на ПК владельца (облачный Claude не имеет SSH), Claude проверяет PR деплоя. Приватный SSH-ключ не покидает ПК владельца.
- Полный чекпоинт, шаги и критерии готовности — `docs/Launch-Checkpoint.md`.
- Сверка чекпоинта с `main` (`80ef473`) и BuildSpec — Claude Code CLI 2.1.282, `Opus 5.5 / high` (effort подтверждён в сессии командой `/effort`): scope CCode #11 приведён к Issue #11 (Daily, Relief, последовательная загрузка `getCurrentUser()` → `getWallet()`; Help UI — только по отдельному решению Hainox); выполненное отделено от плана, блокеров и условий запуска; IP сервера и путь к ключу на ПК владельца убраны, так как репозиторий публичный. Добавлены риски: Portainer наружу, build-time `PUBLIC_API_BASE_URL` (пустое значение даёт demo-режим), гонка первого входа на сервере.
- Решение Hainox (24.09): Portainer — только через SSH-туннель, 9443 наружу не публикуется. В чекпоинт добавлено, что Docker публикует порты в обход ufw, поэтому в продакшен-compose наружу выходит только Caddy; R4 связан с PR #14, граница одного API-воркера — с PR #16.
- Открыто: переустановка сервера и DNS (владелец), PR деплоя `codex/production-deploy` (ещё не создан), Blackjack UI #6 и затем Daily/Relief #11 (CCode), пункты 5–6 аудита (Codex).

## 2026-09-23 — dependency-aware API readiness

- `/health/ready` проверяет PostgreSQL через `SELECT 1` и Redis через `PING` параллельно, с ограниченным временем ожидания и без публикации DSN или текста ошибок. Недоступность любой зависимости возвращает HTTP 503 со статусами зависимостей; `/health/live` остаётся независимой liveness-проверкой.
- Добавлены unit-сценарии готовых и недоступных PostgreSQL/Redis, включая проверку освобождения Redis-клиента и отсутствия текста ошибок в ответе; integration-тест действительно подключается к обоим сервисам.
- Верификация: изолированные PostgreSQL 16 и Redis 7, Alembic upgrade head, `uv run --locked pytest -q` — 90 passed; `uv run --locked ruff check .` — clean. Два прежних Starlette/httpx deprecation warning.
- Открыто: полный GitHub CI/PR readiness; Hold’em требует решения об оппоненте и способе входа второго игрока. Mini App профиль/история/рейтинг и admin surfaces остаются отдельными задачами.

## 2026-09-23 — направление оформления Blackjack GFL

- Владелец выбрал направление комнаты: передовая база Griffin & Kryuger в секторе 09. Blackjack визуально отделён от Rainbow Six-темы слотов: без полицейского оцепления и стилизации под WWII; референс — посткатастрофический научно-фантастический мир GFL 1 и операции рядом с территорией Sangvis Ferri.
- Карты оформляются как портретные досье T-Doll. Персонажи должны присутствовать и на числовых картах 2–10; номинал и масть остаются хорошо читаемыми в углах. Точное распределение персонажей по номиналам/мастям и права на каждый исходный файл ещё требуют проверки.
- В режиме против бота предлагается показывать случайную T-Doll как дилера; выбранный образ сохраняется на партию и после reconnect и не влияет на карты, RNG или результат.
- Звуковое направление комнаты: вентиляция/генератор базы, сдержанный терминальный интерфейс и короткие радиопомехи; звуки раздачи и действий карт отдельные и не маскируют подтверждённый исход сервера.
- В текущем `apps/miniapp` не найдено изображений персонажей или аудиофайлов; production card art и SFX зависят от подготовленных оригинальных/лицензированных ассетов. До этого CCode должен оставить явные места под изображения и не имитировать воспроизведение отсутствующего звука.
- CCode workflow: `meta/muse-spark-1.3-contributor`, effort `high`; домен, RNG, ledger и API-контракты остаются вне handoff. Существующий issue #6 обновлён утверждённым владельцем направлением; это уточнение UI handoff, реализация ещё не начата.

## 2026-09-23 — черновая матрица колоды Blackjack GFL

- Добавлены docs/design/blackjack-card-roster.html и docs/design/blackjack-card-roster-handoff.md: 52 карты, два полных варианта распределения персонажей, фильтр по масти/номиналу/поиску, смешанный выбор A/B, сохранение локально и экспорт CSV.
- В обоих наборах A и B по 52 уникальные T-Dolls; индексы и номиналы Blackjack сохранены. Выбор владельца по составу, стилю портрет/чиби, рубашке и звуку ещё не получен; документ помечен как черновик.
- Изображения и звук не копировались. Для каждого исходного портрета/чиби права надо проверить отдельно. Подготовлен ограниченный CCode handoff для issue #6, запуск после выбора владельца.
- Проверка: Playwright Chromium на локальном HTML — 52 строки; 13 карт на масть; 4 туза, 36 карт 2–10, 12 карт J/Q/K; оба состава уникальны; работают фильтры, поиск, сохранение выбора и настроек, CSV; ошибок JavaScript нет. Проверен viewport 390×844 без горизонтального overflow страницы.
- Далее: владелец выбирает A/B либо смешанный состав; затем CCode получает утверждённый roster и реализует только визуальный слой комнаты в границах handoff. Серверный контракт/домен не меняются.

## 2026-09-23 — Blackjack Deck A preview

- Владелец зафиксировал Deck A, портретный стиль досье и рубашку A / S09. Собраны оригинальные концепты комнаты Sector 09 и рубашки, создано локальное HTML-превью со всеми 52 портретами и раскладкой по мастям; исходная комната, рубашка и список источников отделены в design checkpoint.
- Портреты IOP Wiki сохранены только локально в assets/design/blackjack-gfl/deck-a/portraits/; sources.json фиксирует источники и статус прав. Они не включаются в публичный Git или Mini App без разрешения.
- CCode handoff #6 обновлён: UI может использовать выбранное направление и оригинальные концепты; для персонажей без разрешённых файлов оставить явные portrait slots. Сервер, RNG, ledger и API не менять.
- Проверка: отдельный Playwright Chromium verifier — 52 уникальные карты, 13 на масть, все 53 отображаемых портрета успешно декодированы, порядок/имена посимвольно совпадают с Deck A из матрицы; 390×844 без overflow, ошибок JS нет. Сохранены desktop, mobile и полный контактный лист.
- Открыто: получить разрешения/лицензированные портреты и звуки перед production; после публикации design checkpoint передать UI handoff CCode от свежего main. Полноцветное превью и исходные IOP-портреты остаются только в локальной рабочей папке.

## 2026-09-23 — мобильное превью Blackjack Deck A

- Владелец уточнил, что MICA публикует материалы GFL для распространения информации об игре и привлечения игроков; использование портретов в этом неофициальном дизайн-превью с атрибуцией одобрено владельцем проекта.
- В PR #8 добавлены 52 исходных портрета, список источников, пять облегчённых JPEG-превью и GitHub Markdown-страница для просмотра с телефона. Это дизайнерский checkpoint, не Mini App bundle и не заявление об открытой лицензии на повторное использование.
- В `sources.json` сохранены ссылки IOP Wiki на персонажей и изображения. Авторство T-Doll указано за MICA Team / SUNBORN; комната Sector 09 и рубашка созданы для проекта.
- Проверка: локальный Playwright verifier подтвердил состав, декодирование портретов и viewport 390×844; повторный GitHub Verify PR #8 прошёл: Python lint/tests, Mini App check/tests/build, Docker Compose build, E2E и Monte Carlo.
- CCode: issue #6 дополнен путями до портретов и границей ответственности; UI-задача остаётся отдельной и ждёт слияния PR #8 и server-first зависимости.
- Открыто: с телефона можно открыть мобильную README-страницу по GitHub branch URL; PR #8 остаётся draft checkpoint до слияния.

## 2026-09-23 — интерактивное превью Blackjack Deck A на Pages

- Локальное HTML-превью стало мобильной интерактивной страницей: добавлены поиск по имени/масти/номиналу, фильтры по масти и группе номиналов, счётчик результатов и доступное досье по нажатию на карту.
- Сохранена стилистика форпоста G&K / Sector 09, показаны лицевая карта, рубашка S09, все 52 карты и концепция звука. Игровые правила и звук браузером не имитируются.
- Для мобильной загрузки подготовлены WebP-версии комнаты, рубашки и портретов общим объёмом около 1,45 МБ; оригиналы PNG сохранены. GitHub Pages workflow копирует страницу и web-ассеты в отдельный маршрут `/design/blackjack-deck-a/`; Mini App runtime-ассеты и API не меняются.
- Проверка: `node --check`, `pnpm miniapp:check` (0 warnings), `pnpm miniapp:build` и `git diff --check` прошли. Playwright Chromium проверил локальный Pages build: 52 уникальные карты (13 каждой масти), фильтры (червы — 13, J/Q/K — 12), поиск UMP45, карточное досье, декодирование всех портретов, загрузку комнаты/рубашки и ширины 320–1440 px без горизонтальной прокрутки или ошибок браузера. Pages workflow `35852738946` для коммита `d7646a5` прошёл; live URL отвечает HTTP 200. Playwright на live странице проверил 52 карты, все 54 изображения, фильтры, поиск, досье и ширину 390 px без горизонтального overflow и ошибок браузера. Для ручного workflow на время добавлено точное разрешение `codex/blackjack-deck-a-preview` в окружение `github-pages`; сразу после деплоя оно удалено, поэтому снова разрешён только `main`.

## 2026-09-24 — CCode issue #6: Blackjack GFL UI (meta/muse-spark-1.3-contributor, high)

- От свежего `origin/main` (`80ef473`, PR #8 принят) создана ветка `ccode/blackjack-ui`.
- `apps/miniapp/src/lib/rooms/BlackjackRoom.svelte`: серверный snapshot как единственный источник (`game_phase`, `bet`, `player_cards`, `dealer_cards` с `{hidden:true}`, `dealer_hole_hidden`, `player_total`, `dealer_total` только после раскрытия, `wallet_balance`, `legal_actions`, `ruleset_version`, `last_result` через `result`). 52 уникальные карты Deck A (RPK-16 — A♥, AK-12 — K♥), рубашка A/S09 для скрытой карты без rank/suit/doll/total до серверного reveal. Ставка 25–100 целым числом; действия только из `legal_actions`; split отсутствует. Косметический аватар дилера стабилен на партию (`hash(roomId)`) и не влияет на RNG/выплату. Post-Collapse интерьер с полицейским периметром; без WWII/R6S. Фокус, safe areas, reduced motion сохранены; звука и новых зависимостей нет.
- `apps/miniapp/src/routes/+page.svelte`: только передача Blackjack snapshot/pending/apiError в комнату; добавлен `actionPending`-guard против двойного действия (флаг сбрасывается после settle/ошибки/resync/навигации). Остальная логика комнат не менялась.
- `apps/miniapp/tests/e2e/blackjack-room.spec.ts`: ставки 25–100, deal, hidden card (S09 без данных), legal actions, settlement только по серверу (`+62 JG`, `BALANCE 1037 JG`), блокировка повторного тапа, ошибка 409 + повтор с новым ключом, reconnect через `getRoom` без клиентского расчёта, reduced motion.
- Проверки: `pnpm miniapp:check` — 0/0; `pnpm miniapp:test` — 25 passed; `pnpm miniapp:build` — passed; `pnpm --dir apps/miniapp exec playwright test tests/e2e/blackjack-room.spec.ts` — 6 passed (Chromium, Windows). Серверный контракт совпал с заданным (`game_phase/bet/player_cards/dealer_cards/dealer_hole_hidden/player_total/dealer_total/wallet_balance/legal_actions/ruleset_version/last_result`), блокеров нет.
- Открыто: PR из `ccode/blackjack-ui` в `main`; issue #11 ждёт завершения #6 (общий `+page.svelte`).

## 2026-09-24 — роли, параллельность и model/effort

- Зафиксировано разделение: Codex владеет контрактами, сервером, доменом, интеграцией и финальной проверкой; Claude Code выполняет узкие серверные/документальные задачи или read-only review в отдельном worktree; CCode получает UI/motion handoff по принятому контракту.
- Параллельная реализация разрешена только для независимых задач с замороженным контрактом, разными allowlist файлов и отдельными ветками/worktree. Зависимости идут последовательно; на один файл назначается один implementer. Пример: CCode issue #11 ждёт Blackjack issue #6, потому что оба handoff меняют `+page.svelte`.
- Каждый issue, handoff, запуск и отчёт должен указывать точные модель и effort. Workflow задаёт маршруты Codex `gpt-6-sol/high` и `gpt-6-astra/xhigh`, Claude Code `Opus 5.5/high` для сложного review, `Sonnet 5/high` для обычных ограниченных изменений и `Haiku 4.5/low` для короткой документации, CCode `meta/muse-spark-1.3-contributor/high`. Владелец подтвердил, что Claude Code-сессия, подготовившая PR #10, использовала `Opus 5.5 / High`.
- По снимкам интерфейса владельца от 24.09.2026 зафиксированы имена Claude-моделей и effort-метки; `Fable 5.1` и `Fable 5` помечены как требующие usage credits. Локальный CLI `2.1.281` принимает effort `low|medium|high|xhigh|max`; отображения меток `Extra` и `Ultracode` на значения CLI не подтверждено.
- Claude Code подготовил серверные изменения PR #10; Codex завершил исправления аудита в stacked PR #12 и влил их в ветку `claude/audit-fixes`. PR #10 остаётся открытым, его текущий head `9b5b284` включает исправления из #12 и ещё ждёт приёмки/слияния в `main`. CCode #6 остаётся за визуальной Blackjack-комнатой после PR #8; issue #11 ждёт принятого PR #10 и завершения #6, чтобы не делить `+page.svelte`.
- Проверка документации: `git diff --check` — passed. Изменение внутреннего процесса; `ChangeLog.md` не обновлялся.

## 2026-09-24 — atomic wallet bootstrap (Codex PR A)

- Wallet creation now requires an existing `User` and uses conflict-safe insertion; it cannot create a placeholder user with a manually assigned primary key. HTTP and WebSocket first login share one atomic user insert and welcome grant transaction. The grant amount and API error contract are unchanged.
- SQLite regression tests cover a missing user, repeated/concurrent wallet creation, concurrent HTTP/HTTP, HTTP/WebSocket and WebSocket/WebSocket login, and a single welcome ledger entry. PostgreSQL integration cases cover concurrent logins. A failing mixed HTTP/WebSocket regression reproduced the original unique-key error before the fix.
- Local verification: `uv run --locked ruff check .` passed; `uv run --locked pytest -q` returned 120 passed, 9 skipped, 2 existing deprecation warnings. PostgreSQL integration was not run locally because `TEST_DATABASE_URL` is absent and Docker Desktop daemon is unavailable; GitHub CI PostgreSQL job is required before merge.
- GitHub Actions `verify`, run `36056757537`, passed with PostgreSQL integration: 129 passed, no skips. Owner review is still required before merge/deploy. The 32-bit balance and multiworker event transport remain separate decisions.
- Review follow-up (Claude Code CLI 2.1.282, `Opus 5.5 / high`, temporarily covering Codex): Codex Review P2 confirmed — every authentication ran the conflict-safe `INSERT`, and PostgreSQL draws `users.id` from the sequence before the conflict check, so each request burned an id of the 32-bit key. `_upsert_user` now looks the user up first and inserts only on first login, re-reading the row if a concurrent first login wins. PostgreSQL regression `test_repeated_login_does_not_consume_user_ids` failed on CI run `36058235402` before the fix (`assert 7 == 2` after five repeat logins). `wallets` is keyed by `user_id` and has no sequence, so its conflict insert is unaffected.

## 2026-09-24 — separate internal API token (Codex PR B)

- Internal bot routes now authenticate with `INTERNAL_API_TOKEN` and `X-Internal-API-Token`, separately from Telegram `BOT_TOKEN`. The API returns the existing 401 error when the internal token is absent, wrong, or identical to `BOT_TOKEN`; the bot refuses startup if its internal token is absent or reused. Telegram login verification is unchanged.
- Compose passes the setting to API and bot; `.env.example` leaves its value empty. Production must provision one separate matching value to both services before rollout. This is a coordinated deployment change, so it is recorded in `ChangeLog.md`.
- Local verification: `uv run --locked ruff check .` passed; `uv run --locked pytest -q` returned 127 passed, 6 skipped, 2 existing deprecation warnings; `docker compose --env-file .env.example config --quiet` and `git diff --check` passed. Tests cover valid/wrong/absent/reused/non-ASCII tokens, old header rejection, bot configuration, and client header. PostgreSQL integration did not run locally because `TEST_DATABASE_URL` is absent; GitHub CI is required before merge.
- Open: owner review and CI before merge/deployment; provision the real value outside repository and logs.

## 2026-09-24 — граница масштабирования API (Codex PR C)

- Проверено: `EventBus` хранит подписчиков в памяти процесса; `apps/api/Dockerfile` запускает Uvicorn без `--workers`. В `docs/Local-Setup.md` закреплён поддерживаемый production режим: один API worker и одна реплика до утверждения межпроцессной доставки событий.
- Redis Pub/Sub для игровых событий не реализован. Если владелец запросит несколько worker-ов/реплик, нужен отдельный архитектурный проект с отказами, порядком/повторами доставки, восстановлением из PostgreSQL и двухпроцессными тестами; этот PR его не внедряет.
- 32-битный `Integer` для баланса/ledger отмечен как отложенный риск. Миграция на `BigInteger` ждёт утверждённого владельцем порога и требований совместимости.
- Проверки: `git diff --check` и `uv run --locked ruff check .` прошли; `uv run --locked pytest -q` — 115 passed, 6 skipped, 2 прежних deprecation warnings. PostgreSQL integration локально не запускалась (`TEST_DATABASE_URL` отсутствует), CI обязателен перед merge. Код и поведение не изменены; `ChangeLog.md` не требуется. Merge/deploy — только после решения владельца.

## 2026-09-27 — сверка чекпоинта запуска после слияния PR #14

- Claude Code CLI через Claude Pro, `Opus 5.5` (`claude-opus-5-5`); effort интерфейсом сессии не показан, поэтому не указан. Ветка `claude/checkpoint-sync-after-14` от `main` `07a7a75`.
- `docs/Launch-Checkpoint.md` приведён к `main` после слияния PR #14, #17 и #16 и к review из issue #22: три PR перенесены в выполненное, R4 закрыт на сервере; из блокеров убраны слияния, добавлена генерация `INTERNAL_API_TOKEN` владельцем.
- Слияния по разрешению владельца от 27.09.2026 (Claude Code): #17 — как был, head `29de36e` уже содержал `main` `07a7a75`, CI run `36272570353` зелёный (142 passed, PostgreSQL integration без пропусков), merge `bf2e36e`. #16 — в ветку влит `main` с сохранением обеих записей журнала (`b230330`), CI run `36283554507` зелёный (142 passed), merge `7d56b95`.
- В план деплоя (issue #23) и риски добавлены: отдельный `INTERNAL_API_TOKEN` для API и бота с одновременным обновлением обоих сервисов (R6) и явный `--workers 1` без `WEB_CONCURRENCY`, так как Uvicorn по этой переменной сам поднимает несколько воркеров (R5).
- `docs/Code-Audit-2026-09-23.md`: после слияния #16 отмечено, что гонка создания кошелька исправлена PR #14, а отдельный внутренний токен — PR #17.
- Проверка: `git diff --check` — passed. Изменение только документации; `ChangeLog.md` не обновлялся.

## 2026-09-27 — cleanup Low-findings review #22 (issue #27)

- Claude Code CLI через Claude Pro, `Sonnet 5` (`claude-sonnet-5`); effort — `high` по настройкам Claude Code, интерфейсом сессии не подтверждён. Ветка `claude/review-22-cleanup` от `main` `01705de`.
- `_upsert_user` переименован в публичный `upsert_user` (`apps/api/app/dependencies.py`, `apps/api/app/services/room_service.py`); логика не менялась. Исторические записи журнала и аудита оставлены как были.
- `docs/Local-Setup.md`: строка про Redis больше не обещает Pub/Sub; добавлено, что без `INTERNAL_API_TOKEN` бот не стартует, и как сгенерировать значение локально. `docker-compose.yml` намеренно не менялся (`:?` ломает `compose config` на `.env.example`); production-вариант — в #23 / PR #26.
- Поведение и контракты не менялись; `ChangeLog.md` не обновлялся.

## 2026-09-27 — production Compose и runbook деплоя (issue #23)

- Исполнитель: Claude (Opus 5.5, приложение Claude), замещает Codex по решению владельца: у Codex закончился лимит. Effort интерфейсом не показан. Ветка `codex/production-deploy` от `main` `01705de`. Gate #23 пройден: #14, #17, #16 и #24 слиты, CI на `main` зелёный, review #22 актуализирован.
- `docker-compose.prod.yml`: наружу публикует только Caddy (80/443, 443/udp); PostgreSQL и Redis — во внутренней сети без выхода наружу; API строго одним процессом (явный `--workers 1`, без `WEB_CONCURRENCY` и `replicas`); Mini App собирается с `PUBLIC_API_BASE_URL=https://burmaldoza.ru`; `POSTGRES_PASSWORD`, `BOT_TOKEN` и `INTERNAL_API_TOKEN` обязательны через `:?` (закрыт Low-finding #22 про `INTERNAL_API_TOKEN:-`). Caddyfile встроен через `configs.content`, так как отдельный файл вне allowlist; требуется Docker Compose 2.23.1+. `apps/miniapp/Dockerfile` не менялся — build-arg wiring достаточен.
- `docs/Deploy-Production.md`: подготовка сервера, `.env` без вывода секретов, предварительные проверки, запуск и проверки из раздела 6 чекпоинта, ночной `pg_dump` с шифрованием открытым ключом `age` (закрытый ключ только у владельца), проверка восстановления на отдельной базе без передачи ключа на сервер, обновление и откат, в том числе после миграции.
- Проверки: `docker compose -f docker-compose.prod.yml config` — passed (с заглушками вместо секретов); без `INTERNAL_API_TOKEN` конфиг падает, как задумано; опубликованные порты — только у `caddy`; `caddy validate` (Caddy 2.10.2) — Valid configuration; маршрутизация `/api/*` / `/health*` / остальное проверена на локальных заглушках. Сборка образов не запускалась (Docker daemon на ПК не был запущен) — её выполняет CI и первый запуск на сервере. На сервер не заходили, `.env` и деплой не трогались.
- `docs/Launch-Checkpoint.md` вне allowlist #23: строка «PR деплоя не создан» в разделе 5 обновляется отдельной задачей после слияния.

## 2026-09-27 — Codex: runtime-проверка и исправление production PR #26 / issue #23

- Инструмент — Codex; назначенный владельцем маршрут — `gpt-6-astra / xhigh` (независимые runtime model/effort metadata интерфейс не показывает). Продолжена существующая ветка `codex/production-deploy`, исходный head `7466272`, база `01705de935ee7f805dd829d6ddc1bde1b6846004`. Повторно проверены слияния #14/#17/#16, закрытый review #22 и зелёный CI `main` run `36283896543`. Gate выполнен; новый PR не создавался.
- Реальная локальная проверка выявила два дефекта исходного Compose: `BotConfig` отклонял `API_BASE_URL=http://api:8000` при `ENVIRONMENT=production`; создание комнаты в собранном API давало 500 из-за отсутствия `/app/tests/fixtures/slot_skeleton.json`. Исправлено в allowlist: бот ходит на HTTPS Caddy по Docker DNS alias `burmaldoza.ru`, запускается после Caddy и больше не подключается к сети БД; существующий ruleset подключён в API как read-only Compose config. Dockerfile, domain, contracts и сами правила не менялись.
- Runbook: защищено первичное создание `.env`, добавлен безопасный валидатор конфигурации без печати секретов, bot HTTPS/API probe перед polling, уточнены health/redirect/EXPOSE проверки. Копии создаются с `umask 077`, блокировкой и остановкой при ошибке конвейера. Для восстановления используются отдельные базы с уникальными именами; откат сохраняет старую базу вместо её удаления. Перед обновлением сохраняются образы; откат использует `--no-build --pull never`. Учтены config/manifest/index digest в Docker containerd store. Все Bash-блоки останавливаются при ошибке.
- Локальное окружение: Docker Desktop engine `29.8.0`, Compose `v5.5.1`, отдельный проект `burmaldoza-issue23`. Production Compose проверен с синтетическими credentials; локальный override снимает все host ports и включает Caddy local CA. Production `.env`, SSH, сервер и Telegram Bot API не использовались. Тестовые подписи созданы только для вымышленных локальных пользователей.
- Проверки: `docker compose ... -f docker-compose.prod.yml config --quiet` и структурные проверки итогового JSON — passed; отсутствие каждого из трёх обязательных секретов — ожидаемый отказ. Production `build api bot miniapp` — passed. `caddy validate` — passed. Четыре healthcheck-сервиса healthy; один API Uvicorn process с `--workers 1`; собранный Mini App содержит `https://burmaldoza.ru`.
- HTTPS с проверкой локального CA: статика, ready/live, 401 без авторизации, production-конфигурация бота и реальные `BotApiClient` wallet/top запросы — passed. Подписанный вход → welcome 1000 → создание Slot-комнаты → spin → WSS snapshot/event, совпадающий с HTTP result, → идемпотентный повтор — passed. Поочерёдная остановка PostgreSQL и Redis даёт readiness 503 при liveness 200; после восстановления readiness 200.
- Backup/rollback: `pg_dump -Fc` → `age` → расшифровка → `pg_restore --exit-on-error --single-transaction` в отдельную PostgreSQL базу — passed; совпали counts users/wallets/operations/ledger/rooms/actions, суммы балансов/ledger и Alembic revision; несогласованных кошельков 0. Проверены права архива 600 в Linux, отказ повреждённого архива и отсутствие опубликованной копии после ошибки источника. `docker image save/load` и перезапуск API/Mini App без сборки сохранили platform manifest digests. Проверено переключение на восстановленную базу с сохранением старой; ready 200, агрегаты прежние. Несовместимая миграция не имитировалась; проверена процедура переключения копии текущей схемы.
- `bash -n` — passed для 15 Bash-блоков runbook (плейсхолдеры заменены только для синтаксического разбора); `git diff --check` — passed. Независимый read-only reviewer: Codex subagent / `gpt-6-sol / high`; исправлены замечания о повторном имени восстановительной базы и остановке сохранения неполного набора образов; итог — approve, открытых findings нет.
- Границы доказательств: прежний CI #26 run `36284938226` собирал dev Compose, а production runtime проверен локально. Публичные DNS/Let's Encrypt, BotFather, настоящий Telegram polling/WebView, доставка копий вне сервера и серверная аварийная тренировка остаются owner/deploy gates. Нужны Docker Engine/Compose, Bash, PostgreSQL client tools в контейнере, `age`, `flock`, OpenSSL и Python 3 для команд runbook; внешний backup destination выбирает владелец. Изменены только `docker-compose.prod.yml`, `docs/Deploy-Production.md`, `ChangeLog.md`, `dev/ProjectLog.md`.

## 2026-09-27 — runbook: точные команды установки Docker (issue #23)

- Исполнитель: Command Code по прямому указанию владельца; фактические модель/effort интерфейсом сессии не подтверждены и здесь не заявляются. Ветка `codex/production-deploy`, база `b704060`; новый PR не создавался.
- В `docs/Deploy-Production.md`, раздел 3, описательная строка про установку Docker заменена исполняемым блоком из официального apt-репозитория Docker: ключ в `/etc/apt/keyrings/docker.asc`, `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`, `docker-compose-plugin`, `systemctl enable --now docker`, `usermod -aG docker deploy` и проверка `docker compose version`. Добавлены пояснения: почему не подходят snap и Ubuntu-пакет `docker.io`, требование Compose 2.23.1+ из-за `configs.content`, необходимость нового SSH-сеанса после `usermod` и связь Docker с `ufw` (R1).
- Проверки: `bash -n` для всех 16 Bash-блоков runbook — исполнимые блоки разбираются, единственный отказ у пред-существующего плейсхолдера `git checkout <SHA …>`, который намеренно не является валидным shell; `git diff --check` — passed. На сервер не заходили, `SSH`, production `.env` и деплой не трогали.
- Изменены только `docs/Deploy-Production.md` и `dev/ProjectLog.md`.

## 2026-09-27 — эксплуатационные замечания к runbook PR #26

- Codex продолжил `codex/production-deploy` от базы `main` `01705de`, исходный head `7a34618`; назначенный маршрут — `gpt-6-sol / high`, фактические runtime model ID/effort отдельно не подтверждены. Изменения ограничены allowlist issue #23: `docs/Deploy-Production.md`, `ChangeLog.md` и этот журнал.

- В Compose shell variables имеют приоритет над `--env-file`, поэтому runbook теперь останавливает preflight/startup/backup/restore/rollback, если shell экспортирует используемые production interpolation variables. Проверка печатает только имя переменной, значение не выводит.

- Установка ночного backup cron теперь работает и при отсутствии crontab и не добавляет одну и ту же задачу повторно. В разделах 8–9 явно описано, какие SSH/Bash-переменные должны сохраняться между блоками; для сбоя переименования БД добавлено безопасное восстановление по фактическому состоянию имён.

- Проверки: `bash -n` — 18 блоков runbook разобраны успешно после нормализации текстовых placeholders; `git diff --check` — passed. Последний опубликованный CI run `36296832893` на базовом head `7a34618` успешен, но ещё не включает эти локальные изменения; после обновления PR нужен новый CI. Новые контейнеры не запускались; сервер, `.env`, merge и deploy не затрагивались.

- Осталось: новая CI проверка опубликованного diff; read-only review PR #26 и решение владельца. `docs/Launch-Checkpoint.md` не менять до отдельного шага после merge #26.

## 2026-09-25 — штаб: маршрутизация заданий и отчётов через GitHub

- По решению Hainox закреплённый чат Codex стал штабом проекта и проверяет GitHub раз в 30 минут. В `AGENTS.md` добавлен раздел «Штаб»: задания — issue с метками `to:codex` / `to:claude` / `to:ccode`, отчёты — комментарии в PR или issue задачи с первой строкой `<!-- agent-report -->` и шапкой «Кому / От / Модель/effort / Тип», прочее — в закреплённое issue #19 «Штаб: входящие». Метка `needs-owner` — для решений владельца. Правило замещения: при исчерпанном лимите владелец передаёт задачи другому агенту.
- Созданы метки `to:codex`, `to:claude`, `to:ccode`, `agent-report`, `needs-owner`; issue #1, #2, #6, #11 помечены `to:ccode`.
- Хуки на каждый шаг сессии отклонены: шумно и есть риск вынести куски транскрипта в публичный репозиторий. Автоматическая доставка достигается тем, что каждый агент сам публикует отчёт через `gh` в конце задачи.
- Исполнитель: Claude Code CLI 2.1.282, `Opus 5.5 / high`, временно замещает Codex. Проверка: `git diff --check` — passed. Внутренний процесс; `ChangeLog.md` не обновлялся.

## 2026-09-26 — штаб: фактическое устройство, сверка CLAUDE.md и AGENTS.md

- Раздел «Штаб» в `AGENTS.md` приведён к работающей схеме: локальный узел на ПК владельца собирает задания и финальные ответы из хуков Codex, Claude Code и Command Code (только в этом репозитории, без шагов сессии) и опрашивает GitHub раз в 5 минут; всё раскладывается в журнал и приватный inbox-репозиторий владельца. В чат Codex уходят только задания с адресатом Codex и отчёты (решение владельца: каждая пересылка расходует лимит Codex). Формулировка «хуки не использовать» заменена на «хуки на каждый шаг не добавлять; хуки штаба ставит только владелец».
- Claude Code загружает `CLAUDE.md` и `AGENTS.md` вместе (`instructionFiles: claude-md-and-agents-md`). Из `CLAUDE.md` убраны дубли общих правил; снята неувязка с `/status` (агент не может вызвать её сам — проверяет владелец, агент проверяет только наличие `ANTHROPIC_API_KEY`); добавлены префикс ветки `claude/` и явное правило публикации (своя ветка, черновой PR и отчёт — без отдельного запроса; остальное — с разрешения владельца), согласованное с разделом «Штаб».
- Сквозной тест штаба 26.09: задания и отчёты Codex, Claude Code и Command Code доходят ровно один раз.
- Исполнитель: Claude (Opus 5.5), замещает Codex. Проверка: `git diff --check` — passed. Внутренний процесс; `ChangeLog.md` не обновлялся.

## 2026-09-27 — разбор открытых PR и слияния по разрешению владельца

- Claude Code CLI через Claude Pro (`claude auth status`: `authMethod: claude.ai`, `subscriptionType: pro`; `ANTHROPIC_API_KEY` не задан), `Opus 5.5` (`claude-opus-5-5`); effort `high` по настройкам, в интерфейсе сессии не подтверждён. Владелец разрешил довести все открытые PR и слить нужные.
- Слиты после review и зелёного CI на проверенном head: #28 (`427c163`), #25 (`15f1cd9`), #26 (`87eecdb`, закрыт #23), #15 (`817afd8`, закрыт #6), #29 (`bc23663`, закрыт #11), #20 (`aa94979`). В ветки #26, #15, #29 и #20 перед слиянием вливался `main`; конфликты были только в `dev/ProjectLog.md`/`ChangeLog.md`, сохранены обе записи. Совместный `+page.svelte` (#15 + #29) прошёл CI.
- PR #18 не слит и возвращён в черновик. Вывод «дефект #1 не воспроизводится» неверен: в `apps/miniapp/src/lib/game/slot.ts` все три барабана по `easeInOutCubic` одновременно гасят скорость к 2000 мс, затем центральный и правый стоят 160/320 мс и стартуют landing из покоя со скоростью ≈ 19,6 ряда/с. Новый тест этого не ловит. #1 открыт, #2 закрыт как дубликат.
- Follow-up: #30 (CCode — DEMO-стол Blackjack, resync после 409, точность тестов; портреты/кредит — после решения владельца), #31 (Codex — убрать `/api/v1/internal/*` с публичного сайта Caddy).
- `docs/Launch-Checkpoint.md` приведён к `main` `aa94979`: выполненное, план деплоя по runbook, очередь CCode/Codex, блокеры, R4–R6 и новый R7. `docs/Code-Audit-2026-09-23.md`: пункт 5 отмечен исправленным в PR #14 (проверено по `wallet_service.py`).
- Проверка: `git diff --check` — passed. Изменение только документации; `ChangeLog.md` не обновлялся.

## 2026-09-27 — CCode issue #1: исправление остановки барабанов (meta/muse-spark-1.3-contributor, high)

- Задание штаба из issue #1 (комментарий `5855186680`): продолжить ветку `ccode/slot-stop-continuity-followup`, влить свежий `main` без force-push, исправить формулы движения и тесты. Исправлена неверная запись этой ветки о том, что «дефект не воспроизвёлся»: корневая причина подтверждена по review PR #18 (комментарий `5854955079`) — общий `easeInOutCubic` гасил скорость всех барабанов к 2000 мс, затем центральный и правый стояли 160/320 мс и стартовали landing из покоя со скачком ≈ 19,6 ряда/с.
- `apps/miniapp/src/lib/game/slot.ts`: у каждого барабана своя кривая — разгон 260 мс с задержкой 0/110/220 мс, равномерная крейсерская скорость до собственного stop-start (2000/2160/2320 мс), затем торможение, начинающееся с той же скорости (landing-дистанция = v·T/3) и заканчивающееся точно на `-SLOT_FINAL_OFFSET_ROWS`. Общий `easeInOutCubic` в конце travel убран. Добавлены `SLOT_RAMP_DURATION`, `getSlotReelCruiseVelocityRowsPerMs` и `getSlotReelVelocityRowsPerMs`.
- `apps/miniapp/src/lib/game/slot.test.ts`: скорость каждого барабана непрерывна на stop-start (|v(t−8) − v(t+8)| ≤ 15% крейсерской, v после границы ≥ 80% крейсерской), движение монотонно без остановки до stop-start (≥ 80% крейсерской с конца разгона), финальный offset = `-SLOT_FINAL_OFFSET_ROWS`. В ревью-раунде добавлены независимая от проверяемой функции оценка крейсерской скорости (`SLOT_FINAL_OFFSET_ROWS / (RAMP/2 + cruiseWindow + LANDING/3)`) и проверка сходимости к `-SLOT_FINAL_OFFSET_ROWS` на `stopEnd − 1`.
- `apps/miniapp/tests/e2e/slot-stop.spec.ts`: телеметрия спина пишет время кадра, transform и `--reel-offset-rows` всех барабанов; когда левый барабан уже `landed`, transform центрального и правого продолжает меняться. Первая версия теста общий дефект не ловила: замеры покрывали только начало travel и окно после `landed` левого барабана, поэтому простой 160/320 мс и скачок на границе оставались вне окна. В ревью-раунде добавлено требование скорости ≥ 0,002 ряда/мс в ~120 мс до собственного stop-start каждого барабана — это и ловит прежний дефект. Существующие тесты фаз/порядка/settlement/reconnect/reduced motion оставлены.
- Проверки: `pnpm miniapp:check` — 0/0; `pnpm miniapp:test` — 25 passed; `pnpm miniapp:build` — passed; `pnpm miniapp:e2e` — 19 passed (Chromium, Windows). Reduced motion, финальная сетка = сервер, payline/result только после остановки — без изменений.
- Ручная проверка iOS/Android WebView и Telegram WebView не выполнялась — ограничение, оно же остаётся открытым.

## 2026-09-27 — CCode issue #1: ревью-раунд, усиление регрессий и слияние

- Ревью-задача #34 (read-only review PR #18 на head `2ac6537`) выполнена независимым ревьюером на модели другого вендора (`zai-org/GLM-5.3`) плюс собственное воспроизведение проверок исполнителем; фактические model/effort этой сессии интерфейсом не подтверждены. Verdict первой итерации: блокирующая находка по критерию 3 — Playwright-регрессия на `2ac6537` не ловила прежний дефект; по продакшн-коду `slot.ts` замечаний нет.
- Численная проверка `slot.ts` (независимо от тестов): |Δv| на границах разгон→круиз и круиз→торможение ≤ 6,6e-5 ряда/с, участков простоя до stop-start нет, суммарный путь ровно −21 ряд у всех трёх барабанов, смещение на границе travel→landing непрерывно.
- Блокирующая находка воспроизведена эмпирически: с восстановленной старой кривой (`finalOffset·0.9·easeInOutCubic`, затем `0.1·easeOutCubic` из покоя) e2e-спека на head `2ac6537` давала 5 passed, то есть дефект действительно не ловился. Единичный unit-тест при этом падал (`|Δv|` = 0,0187 против порога 1,74e-5), то есть дефект ловил именно он.
- Исправлено в allowlist: `tests/e2e/slot-stop.spec.ts` требует для каждого барабана скорость ≥ 0,002 ряда/мс в ~120 мс до его собственного stop-start. На исправленном коде замеры 0,0102 / 0,0102 / 0,0099 ряда/мс (запас ≈5x), на старой кривой тест падает с сообщением «reel 0 stalled before its own stop start».
- Проверки после правок: `pnpm miniapp:check` — 0/0; `pnpm miniapp:test` — 25 passed; `pnpm miniapp:build` — passed; `pnpm miniapp:e2e` — 19 passed (Chromium, Windows).
- Ограничения: реальный Telegram WebView, iOS и Android не проверялись; плавность 60 fps оценивалась по формулам и телеметрии transform, а не визуально.

## 2026-09-28 — CCode issue #30: демо-стол Blackjack, resync после 409 и точность тестов

- Задание из issue #30 (метка `to:ccode`); ветка `ccode/blackjack-followup` от свежего `main` `1cf20bb` — очередь снята после слияния PR #18 и PR #33, журнальные файлы освободились. Назначенный маршрут — `meta/muse-spark-1.3-contributor` / `high`; фактические model/effort этой сессии интерфейсом не подтверждены.
- Демо-режим Blackjack: снимок был `{demo: true}`, поэтому после «Раздать» стол оставался пустым, а HIT/STAND/DOUBLE не появлялись. Добавлена детерминированная демо-рука (10♠ + 7♥ против 9♣ и скрытой карты), добор, double, раскрытие дилера и итог. Демо помечено явно: баннер «ДЕМО · стол без сервера», итог подписан `DEMO ROUND · БЕЗ СЕРВЕРНОГО ПОДТВЕРЖДЕНИЯ`, строка статуса и кнопка раздачи больше не говорят про сервер. В live-режиме исходы по-прежнему не генерируются.
- `apps/miniapp/src/routes/+page.svelte`, `runLiveAction`: `catch` не обновлял снимок, поэтому повтор уходил с тем же устаревшим `state_version` и снова получал 409. Теперь при любой ошибке действия клиент перечитывает комнату через `getRoom` (общий `reloadRoomSnapshot`, он же используется кнопкой resync), показывает актуальный снимок и остаётся занятым до конца перечита. Текст ошибки в `BlackjackRoom.svelte` больше не обещает, что простой повтор сработает.
- Дубль `actionPending`/`isRunning` убран: остался один флаг `isRunning`, он же передаётся в `pending`.
- `tests/e2e/blackjack-room.spec.ts`: заглушка теперь ведёт версию сервера и отвечает 409 при несовпадении `expected_state_version`; натуральный блэкджек (A♥ + K♥) завершается прямо в ответе на `deal`, фаза player_turn не появляется. Тест повторного тапа реально нажимает второй раз во время ожидания (ответ задержан на 250 мс) и проверяет ровно один запрос; кейс с внешней записью проверяет, что повтор уходит с новой версией (`[0, 1]`). Добавлены тесты натурального блэкджека и демо-стола.
- Проверки: `pnpm miniapp:check` — 0 errors, 0 warnings; `pnpm miniapp:test` — 25 passed; `pnpm miniapp:build` — passed; `pnpm --dir apps/miniapp exec playwright test tests/e2e/blackjack-room.spec.ts` — 8 passed; `pnpm miniapp:e2e` — 21 passed (Chromium, Windows).
- Ассеты из #6 (портреты Deck A, кредит MICA Team / SUNBORN, фон `room-police-perimeter.png`) не переносились: это требует отдельного решения владельца и расширения allowlist.
- Ограничения: реальный Telegram WebView, iOS и Android не проверялись; серверный контракт 409 подтверждён только заглушкой e2e, а не живым API.

## 2026-09-30 — право Claude Code сливать PR

- Решение владельца Hainox: Claude Code может сливать PR в `main` без отдельного запроса при условиях из раздела «Merge силами Claude Code» в `AGENTS.md` (зелёный CI, без конфликтов и блокирующих замечаний, без обхода `needs-owner`, review другого агента для кода; для domain/RNG/ledger/API/миграций/production-конфигурации — review Codex). Deploy и серверные действия по-прежнему делает владелец.
- Обновлены `AGENTS.md`, `CLAUDE.md` (раздел «Публикация») и шаг 6 в `docs/Command-Code-Workflow.md`.
- Поправка по review Codex (P1 в PR #46, пришёл до merge, но был пропущен при слиянии): squash не очищает опубликованные данные — исходные коммиты остаются видны в PR. Правило изменено: если в ветке оказался секрет или приватные данные, PR не сливается, ставится `needs-owner`, чистку истории и отзыв секрета решает владелец. Вывод для Claude: перед merge перечитывать review-комментарии на текущем head, а не только статус CI. Та же поправка — в риске R2 `docs/Launch-Checkpoint.md`.


## 2026-10-03 — сверка штаба и запуск просмотра

- Codex, фактические model/effort не отображаются. База `main` `e1be100`; ветка `codex/hq-status-2026-10-03`. Scope владельца: только BURMALDOZA, запуск просмотра и актуализация сводок.
- По GitHub REST через подключённый GitHub: открытых PR нет; открыты только #41, #43 и постоянный штаб #19. CI базы — success (run 36710993820). Это не подтверждение production или ручной приёмки устройств.
- Обновлены публичный снимок журнала и QA-очередь, Launch-Checkpoint, Development-Roadmap, Slot-V2-Status, инструкция просмотра. Исторические записи не переписывались.
- Mini App Vite и журнал Vite запущены в текущем облачном окружении на 5173/5174, обе страницы HTTP 200. Подхват файлов Vite; GitHub в журнале обновляется кнопкой. На ПК владельца процессы не запускались; hooks/poller не менялись.
- Проверки: `pnpm install --frozen-lockfile` — passed; `pnpm miniapp:check` — 0 errors / 0 warnings; `node docs/project-journal/test-offline.cjs` — passed; `node --check` для app.js/seed.js — passed; `git diff --check` — passed.
- Ограничения: production, live API, Telegram WebView и browser/mobile QA #41/#43 не проверялись; игровые исходы DEMO не подтверждаются сервером.

## 2026-10-12 — продолжение документационной задачи PR #48

- По текущему назначению в PR #48 Codex продолжил `codex/hq-status-2026-10-03` от head `5140eb5` в изолированном worktree. Границы переданы через штаб #19: только Launch-Checkpoint, Development-Roadmap, Slot-V2-Status и этот журнал; Antigravity — read-only review, Claude Code/CCode новых задач не имеют. Подтверждения получения handoff и нового review пока нет. Точный runtime-вариант модели и effort не отображаются.
- GitHub сверён 12.10.2026: `main` `d715ca393071d83eed41a0b70d6bbead31d09a4c`; verify run 38261015713 success. PR #39/#40/#45 merged, #41/#42/#43 closed; открыты только постоянный штаб #19 и draft PR #48. Старые записи остаются историческими снимками.
- Три сводки больше не выдают закрытые QA за активную очередь. Разделены статический review #41, review copy #42 и принятый отчёт Chromium/mock QA #43; Low из #42 сохранён как замечание сопровождения, без нового продуктового scope. Встроенный снимок журнала от 03.10.2026 не обновлялся; актуальные GitHub данные доступны через существующую кнопку обновления.
- Проверки: `git diff --check` — passed; `node docs/project-journal/test-offline.cjs` и `node --check docs/project-journal/app.js`, `node --check docs/project-journal/seed.js` — passed после явного выбора worktree (первый запуск относительных путей попал в домашнюю папку и дал MODULE_NOT_FOUND). Продуктовый код в этом продолжении не менялся; серверные и browser E2E заново не запускались.
- Ограничения: реальный Telegram WebView, iOS/Android и production не проверялись. Чужие незакоммиченные файлы не затрагивались; hooks/poller, workflows, merge и deployment не запускались. Осталось: независимый review всего PR #48, повторная проверка совместимости нового head со свежим main и решение владельца; draft сохранён.

## 2026-10-13 — Codex принимает весь PR #48 и завершает журнал

- Прямое назначение владельца «Бери на себя #48»: Codex принимает всю задачу, ожидание Antigravity снимается; метка PR `to:antigravity` удалена, `to:codex` сохранена. Маршрут опубликован в штабе #19. Точная модель/effort runtime не отображаются; внешний клиент Antigravity не запускался.
- Исправлены оставшиеся расхождения в журнале: встроенный снимок обновлён с живого GitHub (50 записей, `main` `d715ca3`, открыты #19/#48); закрытые передачи #41/#43 убраны, пустая очередь показана явно. README содержит актуальный ручной сценарий; три сводки закрепляют назначение Codex. ChangeLog обновлён только для видимого поведения локального журнала.
- Регрессия очереди добавлена в существующий `test-offline.cjs`: на старом состоянии падает (две карточки вместо сообщения), после исправления проходит. Offline/cache regression и `node --check` app.js/seed.js/test-offline.cjs — passed; `git diff --check` — passed. Read-only code-reviewer и JS reviewer по skill code-review-and-quality не нашли блокеров; это внутренние проверки Codex, не отчёт внешнего Antigravity.
- Локальный Chrome через отдельный HTTP preview: snapshot показывает #19/#48, фильтр PR/open/Codex/#48 находит один PR, обновление получает GitHub API и сохраняет кэш, очередь явно пуста. Реальный offline fallback проверен автоматизированной регрессией; viewport/reduced-motion вручную не проверялись в этой сессии. Точный сценарий дальнейшего ручного QA — в README.
- CI исходного `c763a3f` — success (run 38306834046); на новом head нужен свежий Verify. Ветка не синхронизировалась merge/rebase, GitHub подтверждал mergeable. Чужие изменения, hooks/poller, сервер, merge и deploy не затрагивались. Готовность production/Telegram/реальных устройств не заявляется.

## 2026-10-13 — чеклист ручной приёмки (#56)

- Claude Code (claude-opus-5-5, effort не отображается), ветка `claude/manual-qa-checklist` от `main` `5785e30`.
- Новый `docs/Manual-QA-Checklist.md` для этапа 5: бот, первый вход, Daily/Relief, Slot, Blackjack, Hold'em как известное ограничение (#53), сеть и повторные нажатия, экран и reduced motion, шаблон issue. Тексты ожидаемых результатов сверены с `apps/miniapp` и `apps/bot` в `main`; новых требований нет.
- Ссылки на чеклист добавлены в этап 5 `docs/Development-Roadmap.md` и в условия публичного запуска `docs/Launch-Checkpoint.md`.
- Проверки: `git diff --check` — passed.

## 2026-10-13 — история операций в Mini App (#51)

- Codex (точный вариант и effort не отображаются) реализовал задачу в ветке `codex/miniapp-ledger-history`; на финальных проверках у Codex закончился лимит. Claude Code (claude-opus-5-5, effort не отображается) замещает Codex: довёл ветку, проверил и открыл PR. Command Code недоступен, задача передана Codex владельцем.
- Сделано: `ApiClient.getWalletLedger()` читает `GET /api/v1/wallet/ledger` и отклоняет некорректный ответ; компонент `LedgerHistory.svelte` показывает причину, время МСК, изменение и баланс после, состояния загрузки, ошибки с повтором и пустого списка. В DEMO запросов нет, записи не выдумываются. История перечитывается с сервера после подтверждённого гранта, ответа на действие, события и снимка комнаты. Сервер не менялся.
- Правка Claude Code: при повторной загрузке последний подтверждённый список остаётся на экране, без мигания «Загружаем историю…»; временный конфиг Playwright Codex удалён.
- Проверки: `pnpm miniapp:check` — 0 errors / 0 warnings; `pnpm miniapp:test` — 27 passed; `pnpm miniapp:build` — passed; полный Playwright — 31 passed в трёх прогонах подряд (на порту 4175, так как 4173 занят посторонним локальным сервером).
- Риск: тест `slot-stop.spec.ts` «renders the live canonical grid…» изредка падает при параллельном прогоне — так же и на `main` без этой задачи (1 из 4 прогонов), к истории операций не относится.

## 2026-10-13 — правки после review PR #48 (#55)

- Claude Code (claude-opus-5-5, effort не отображается), ветка `claude/journal-followups-48` от `main` `5785e30`. Закрыты четыре некритичных замечания из review PR #48.
- Журнал: сообщение пустой очереди больше не ссылается на конкретный PR, а направляет к открытым issues с метками `to:*` и штабу #19; `test-offline.cjs` проверяет, что в сообщении нет номера PR (на прежнем тексте проверка падает).
- `docs/Launch-Checkpoint.md`: актуальная очередь — задачи #51–#57 по исполнителям, PR #48 слит, локальный узел штаба включён.
- `docs/project-journal/README.md`: dev-серверы по умолчанию только на localhost; `--host 0.0.0.0` — только для облачного контейнера.
- `ChangeLog.md`: убрана пустая строка внутри списка `## Unreleased`.
- Проверки: `node docs/project-journal/test-offline.cjs` — passed; `node --check` app.js и test-offline.cjs — passed; `git diff --check` — passed.

## 2026-10-13 — review Codex и синхронизация PR #60 после merge #58

- По прямому разрешению владельца Codex слил PR #58 обычным merge commit `8ddfe3c`, затем синхронизировал ветку `codex/miniapp-ledger-history` с этой базой для PR #60. Единственный конфликт — в этом журнале; обе записи #51/#55 сохранены. Mini App при синхронизации не менялся.
- Перед merge проверены точные head: #58 `4cddba5`, #60 `4094e04`; Verify зелёный, блокирующих review нет. Независимая проверка #60: check 0/0, unit 27 passed, build passed, Chromium E2E 31 passed; регрессии обоих PR подтверждены mutation checks в изолированных копиях. Review опубликован в каждом PR.
- После разрешения конфликта: offline regression журнала, `node --check` app.js и `git diff --cached --check` — passed. На новом head PR #60 требуется новый Verify перед merge. Сервер и hooks/poller не затрагивались; публикация Pages при merge #60 разрешена владельцем вместе с merge.

## 2026-10-13 — проект раздела Hold'em v1 в BuildSpec (#53)

- Claude Code (claude-opus-5-5, effort не отображается) по поручению владельца, пока Codex недоступен по лимиту. Ветка `claude/holdem-buildspec` от `main`.
- В `dev/BuildSpec.md` добавлен раздел «Hold’em v1»: утверждённые владельцем режимы (бот и живой соперник), столы 100 / 500 / 1 000 JOKERGEM и тайм-аут 20 секунд; предложения на утверждение — блайнды 5 % / 10 % входа, check-или-fold по тайм-ауту, без тайм-аута в режиме против бота, поиск соперника 60 секунд, бот «от дома» с обязательным Monte Carlo.
- Технические требования для реализации: снимки и события по месту игрока (закрытые карты только своему месту), бот без доступа к картам игрока и колоде, ledger `game_stake`/`game_payout` с idempotency.
- Код не менялся. Проверки: `git diff --check` — passed.
- Решение владельца 13.10.2026: пункты 1–5 раздела Hold’em v1 утверждены (блайнды 5 % / 10 %, check-или-fold по тайм-ауту, без тайм-аута против бота, поиск 60 с, бот «от дома» с обязательным Monte Carlo). Добавлены герой-соперник на каждую раздачу из пула стола и аватар Telegram в живом режиме (#53, PR #63).
- Решение владельца 13.10.2026: пункты 1–5 раздела Hold’em v1 утверждены (блайнды 5 % / 10 %, check-или-fold по тайм-ауту, без тайм-аута против бота, поиск 60 с, бот «от дома» с обязательным Monte Carlo). Добавлены герой-соперник на каждую раздачу из пула стола и аватар Telegram в живом режиме (#53, PR #63).

## 2026-10-13 — порядок записей ledger (#67)

- Codex, точный вариант модели/effort не отображаются. В API истории при равном timestamp операции группируются по operation_id, внутри одного settlement выплата идёт перед ставкой (последние операции первыми), UUID остаётся только последним tie-break. Суммы, баланс, limit 100 и авторизация не менялись; миграция и правка существующего ledger не нужны.
- Регрессия создаёт ставку/выплату с одинаковым timestamp и UUID в обратном порядке: до фикса падает, после — проходит. Проверяет серверные balance_after, изоляцию другого пользователя и отказ без авторизации.
- Проверки: `uv run --locked ruff check .` — passed; `uv run --locked pytest -q` — 140 passed, 10 skipped (PostgreSQL TEST_DATABASE_URL не задан). Ветка `codex/ledger-entry-order`; merge/deploy не выполнялись. Нужны CI PostgreSQL и независимый review перед merge.

## 2026-10-13 — рейтинг Mini App за календарную неделю МСК (#52)

- Решение владельца: топ-15 по сумме `game_stake` + `game_payout` за текущую неделю МСК, понедельник 00:00 включительно — следующий понедельник 00:00 исключительно. Welcome/daily/relief и admin исключены; участвуют игроки с игровыми операциями в этом интервале. Равные результаты сортируются стабильно по внутреннему id, который не выходит в ответ; места порядковые.
- Утверждённое расширение scope: nullable `User.username`, миграция `20261013_0004` после `20260923_0003`, обновление/удаление ника только из проверенного Telegram initData. Старые строки остаются с NULL до следующего входа. Без ника — «Игрок без ника»; имя и идентификаторы не раскрываются. Точное решение записано в BuildSpec.
- Новый авторизованный `/api/v1/leaderboard`, отдельный контракт с периодом и максимум 15 строк; Mini App проверяет ответ на границе, показывает загрузку/ошибку/повтор/пустую неделю и период МСК. Повторное чтение после серверных игровых действий; DEMO без выдуманного рейтинга и запроса API.
- Проверки: `uv run --locked ruff check .` — passed; `uv run --locked pytest -q` — 143 passed, 11 skipped (нет локального PostgreSQL / TEST_DATABASE_URL), две предупреждающие записи зависимостей. Добавлен отдельный PostgreSQL тест для CI и обратимый SQLite тест миграции с существующим пользователем. `pnpm miniapp:check` — 0 errors, 0 warnings; `pnpm miniapp:test` — 33 passed; production build выполнялся webServer Playwright и passed. Первичный `pnpm miniapp:e2e` с 6 workers — 31 passed / 4 timeout старых room-click кейсов (снимок оставался на dashboard до hydration). Повтор всего suite с `CI=true pnpm --dir apps/miniapp exec playwright test --workers=2` — 35 passed; исходные тесты не менялись. Все четыре новых E2E прошли в обоих запусках, включая 320/1440 px и reduced motion.
- TDD: backend тест упал на отсутствующем router до реализации, 6 frontend transport тестов упали на отсутствующем getLeaderboard до реализации; затем passed.
- Ручная приёмка после deploy: в Telegram открыть Mini App с @username; сравнить сумму игровых ledger за неделю и показанный результат; удалить ник и повторно войти — «Игрок без ника»; на телефоне проверить список/повтор загрузки при отключении сети и новую неделю в понедельник. Telegram WebView/iOS/Android и production PostgreSQL локально не проверены. Docker daemon локально недоступен; CI должен проверить PostgreSQL и Compose build. Новый endpoint использует ту же auth dependency, что wallet; общего rate limiting в соседних endpoints нет.
- Осталось: независимый Claude Code review API/миграции, CI Verify на текущем head, приёмка владельцем. Merge, Pages-публикация и серверный deploy не выполнялись; перед серверным запуском нужна штатная `alembic upgrade head`.

## 2026-10-13 — Slot Siege ruleset (#64)

- Codex, точный вариант/effort не отображаются. Новые API-комнаты Slot получают `slot-siege-1` из утверждённого предложения: 8 кодов, 3×7, 3 линии, W wild, ленты по 30 позиций. JSON упакован в domain; skeleton-файл не менялся. Registry принимает только известные версии; CLI Monte Carlo получил --ruleset, старый default skeleton сохранён.
- Ранее созданные комнаты сохраняют их persisted ruleset для spins, snapshots и events. Метаданные games/rulesets приведены к новому default; старый endpoint версии сохранён. Правка supporting router необходима, чтобы каталог не противоречил выбору RoomService. Изменения Mini App/портретов, ротации операций и Free Spins не входят в #64.
- Регрессия API выбора версии сначала падала на старом default, после фикса проходит. Unit и SQLite HTTP-тесты проверяют восстановленную skeleton-комнату через новый сервис; старые deterministic tests получили явный skeleton_config, чтобы продолжать проверять прежнюю конфигурацию.
- Проверки: Ruff passed; полный pytest 211 passed / 10 PostgreSQL skipped; после добавления durable HTTP регрессии focused API/room suite 23 passed. Domain payout/strip/registry/CLI tests прошли. MC: seed42,200000,bet10 — RTP0.977405,hit_rate0.311505; точное перечисление символов даёт25989/27000=0.9625555555555556. Отчёт slot-siege-1.json получен CLI, не правился вручную. PostgreSQL/Compose локально недоступны (Docker daemon не запущен), CI и внешний review нужны до merge.

## 2026-10-13 — превью направлений Slot и Hold'em (#62)

- Claude Code (claude-opus-5-5, effort не отображается); дизайн-задача Command Code, переданная владельцем на время недоступности CCode. Ветка `claude/design-slot-holdem`.
- Решение владельца: у каждой комнаты своя вселенная — Blackjack: Girls' Frontline (уже есть), Slot: Rainbow Six Siege, Hold'em: игры RGG Studio.
- Добавлены интерактивные превью `assets/design/slot-r6/preview.html` и `assets/design/holdem-rgg/preview.html` с README; раздел «Темы комнат» в `docs/Design-Concept.md`. Всё нарисовано с нуля, без официальных материалов Ubisoft и SEGA / RGG Studio. Mini App, правила и сервер не менялись.
- Проверки: локальный Playwright Chromium, 390×844 и 1280×900 — ошибок консоли нет, горизонтальной прокрутки нет, спин и записанная раздача проходят до итога; `git diff --check` — passed.
- Осталось: утверждение направлений владельцем и решение о портретах/официальных материалах; затем встраивание в комнаты и публикация на Pages отдельными задачами.
- Дополнение: по решению владельца символы слота — портреты оперативников Rainbow Six Siege (© Ubisoft, официальный список оперативников): `A` Twitch, `B` Thermite, `C` Montagne, `W` Tachanka. Четыре PNG в `assets/design/slot-r6/portraits/`, источник и SHA-256 сверены с манифестом загрузки и записаны в `sources.json` с атрибуцией, как у GFL.
- Дополнение: по решению владельца больше оперативников без расширения поля — 8 символов вместо 4 (Rook, Bandit, Jäger, Smoke, Twitch, Thermite, Montagne; Tachanka — wild). Предложение ruleset `slot-siege-1` в `assets/design/slot-r6/ruleset-proposal.json`: точный RTP 0,9626, Monte Carlo на движке domain 0,9774 / 0,9643 (2 × 200 000 спинов), выигрыш ≈ 31 % спинов. Production ruleset не менялся. Free Spins в движке слота не реализованы — отдельная задача.
- Дополнение: в ячейках слота вместо касок — кадры лиц (обрезка портретов, `portraits/faces/`). Hold'em: по решению владельца боты-соперники — герои RGG: стол 100 — Итибан Касуга, 500 — Горо Мадзима, 1 000 — Кадзума Кирю; квадратные обрезки кадров из игр, источник и SHA-256 сверены с манифестом архива владельца и записаны в `assets/design/holdem-rgg/sources.json`. Проверки: Playwright Chromium 390 и 1280 px — ошибок консоли нет, горизонтальной прокрутки нет.
- Дополнение (новый визуал комнат по референсам владельца): Slot — холодный монохром, дым и прожекторы, «операции» как ротация лиц на постоянных кодах символов (4 сезона по 14 дней + ивент «Арена»), пул без шлемов 15 атакующих + 14 защитников, Tachanka — постоянный wild; кадры лиц центрированы по силуэту головы (`assets/design/slot-r6/faces/`). Hold'em — тушь и васи, печать-ханко, кинематографичная раздача, заставка героя; 229 героев RGG по столам (34 / 85 / 110), соперник раздачи — «мешком» из пула стола; аватары центрированы по найденному лицу (OpenCV), два кадра вручную, один герой исключён. Проверки: Playwright Chromium 390 и 1280 px — ошибок консоли нет, горизонтальной прокрутки нет; найдена и исправлена ошибка — невидимый слой заставки перехватывал нажатия.
- Решения владельца 13.10.2026 по превью: визуал Slot, выплаты `slot-siege-1` (RTP ≈ 96 %), составы операций — утверждены; ротация — 7 дней вместо 14; бесплатные вращения («Овертайм») отложены; раскладка героев RGG по столам оставлена; визуал Hold'em — на доработку.
- Доработка Hold'em по замечаниям владельца (13.10.2026): заставка героя как в серии — ч/б кадр 4:5 с размытыми краями, имя и подпись красным маркером с белой обводкой (подписи-титулы у 17 героев, у остальных — игра); `intro/` — 229 кадров 640×360 (2,6 МБ); рубашка — золотой дракон; ворота Камуро-тё на заднем плане стола. Проверки: Playwright Chromium 390 и 1280 px — ошибок консоли нет, горизонтальной прокрутки нет.
- Фон стола Hold'em — кадр ворот Камуро-тё из игры, присланный владельцем (обрезана полоса интерфейса фоторежима, 53 КБ), вместо нарисованных ворот; атрибуция в `sources.json` (раздел `scene`).

## 2026-10-13 — саунд-дизайн комнат (#65)

- Claude Code (claude-opus-5-5, effort не отображается), ветка `claude/sound-design`. Поручение владельца: продумать звук; CCode недоступен.
- `docs/Sound-Design.md`: принципы (звук только после подтверждения сервером, без «почти выиграл», выплата меньше ставки не звучит как победа, громкость по размеру выигрыша, звук по умолчанию выключен — предложение), карта звуков и вибрации Telegram для интерфейса, Blackjack GFL, Slot «Siege» и Hold'em «Камуро-тё», настройки и технический план.
- `assets/design/sound/preview.html`: 36 звуков и три сцены (интерфейс, Blackjack GFL, Slot Siege, Hold'em RGG), синтез Web Audio без аудиофайлов и без звуков из игр.
- Найдено: `apps/miniapp/src/lib/telegram/webapp.ts` ожидает `WebApp.haptic`, которого в Telegram нет (настоящий API — `WebApp.HapticFeedback`), поэтому вибрация сейчас не срабатывает; исправление — при встраивании звука.
- Проверки: Playwright Chromium 390 и 1280 px — все кнопки и сцены без ошибок консоли, горизонтальной прокрутки нет; `git diff --check` — passed.

## 2026-10-13 — слияние всех PR и исправление замечаний

- Claude Code (claude-opus-5-5, effort не отображается) по прямому решению владельца («сливай все» и исправить все наблюдения). Слиты #68, #69, #70, #71, #63, #66 (вместе с ранее слитыми #61, #72). Codex недоступен по лимиту; Hold'em слит без его независимого review.
- Исправлено по ходу слияния: оформление теста #68; в #69 — своё место игрока вне топ-15 (`me`), рейтинг не мигает и обновляется не чаще раза в 15 с; в #70 — неизвестная версия правил комнаты даёт ошибку комнаты, а не 500.
- Ветка `claude/cleanup-observations`: тест CORS не зависит от локального `.env`; обёртка вибрации Telegram использует `WebApp.HapticFeedback` (раньше вибрация не срабатывала); e2e открывают комнаты через `openRoom` с повтором клика до гидратации (нестабильный `slot-stop.spec.ts` — 6 чистых прогонов подряд); индекс `ix_ledger_entries_created_at_reason` и миграция `20261013_0006`; README, чекпоинт запуска и роадмап — по состоянию после слияния.
- Проверки: `ruff check` — passed; `pytest -q` с PostgreSQL 16 / Redis 7 — 269 passed; `alembic upgrade head` / откат на шаг — passed; `pnpm miniapp:check` — 0/0; `pnpm miniapp:test` — 38 passed; `pnpm miniapp:e2e` — 35 passed ×6.

## 2026-10-13 — оперативники Siege в комнате слота (#77)

- Codex, точные модель/effort клиента не отображаются; запрошен high. Подключены faces/sources, lineup JSON из #76, постоянные D1-D4/A1-A3/W с approved множителями; Tachanka всегда wild. operation_id из snapshot/result, fallback op1 без поля. Отдельные helper/component не выбирают календарь и не меняют сетку/выплату; game/slot.ts и motion math не менялись.
- Холодный монохром/прожекторы/дым, названия операций, состав Защита/Атака, ч/б лица и цвет на выигрышной ячейке, SVG beams по серверным winning_lines после третьей остановки, next operation banner только в последних 24 часах по серверному сроку. Источники/атрибуция доступны в комнате. Legacy skeleton A/B/C/W оставлен; DEMO использует Siege-сетку и честные DEMO claims. Free Spins Siege не показываются по ранее принятому решению владельца (отложены); legacy panel остаётся.
- Регрессия выявила ранний показ луча при WS snapshot: parent восстановил motion outcome, пока локальные reels ещё travel. Показ grid/highlight/beam теперь gated local settled; восстановленный результат без локального спина сразу ставит reels на финальный offset. Лица и next metadata завершённого спина берутся из неизменного last_result; следующий спин — из текущего snapshot.
- Проверки: miniapp:check 0/0, miniapp:test 40 passed; build passed в Playwright webServer; полный E2E 37 passed, после уточнения frozen next metadata focused Siege suite 2 passed. Проверены 375×812 (screenshot просмотрен), 1440×900/reduced motion, live op1→op2 во время первого спина с сохранением оп1 и сменой во втором, неизменная final grid, отсутствие раннего луча, старые staged-stop/continuity и legacy canonical grid тесты. Старый generic demo E2E проверяет новый SVG beam вместо прежней payline; assertions bonus заменены отсутствием отложенных Siege Free Spins.
- Ручная приёмка: Telegram → Slot → проверить состав/источники на телефоне; spin → последовательные stops → color/beam только после третьей; повтор действия после смены операции даёт прежние лица; новый spin — актуальные. Проверить op1/op2/arena, анонс за 24h, legacy room и reduced motion. Telegram WebView/production не проверены.
- Осталось: сервер PR #83 перед выпуском, CI Verify на head, Claude Code review, ручная приёмка владельца. Merge/Pages/deploy не выполнялись.

## 2026-10-13 — серверная ротация операций Siege (#76)

- Codex, точные модель/effort клиента не отображаются; запрошен medium. Решение владельца в сессии: старт op1 19.10.2026 00:00 МСК; до старта op1, первая смена op2 26.10, далее op1/op2/op3/op4 каждые 7 дней. Составы lineups.js перенесены в packaged slot_operations.json, lineage test сверяет точное совпадение. W Tachanka и все выплаты/ленты/ruleset остаются прежними.
- Domain выбирает календарную операцию по aware времени; arena через три настройки SLOT_EVENT_OPERATION_ID/STARTS_AT/ENDS_AT, [start,end), без сдвига недельного цикла. Settings валидирует комплектность, ID, timezone и порядок дат при старте; input скрыт в тексте validation errors, чтобы не раскрыть другие настройки. Admin/community trigger не реализован.
- SlotOperationMetadata: operation_id, next_operation_id, operation_changes_at — snapshot и каждый spin result/event. Операция фиксируется до RNG/await ledger, replay сохраняет исходную операцию. Snapshot сообщает актуальную операцию следующего спина; last_result остаётся неизменным с прежней операцией. Skeleton rooms не получают эти поля.
- TDD: новые тесты первоначально упали на отсутствующем модуле. Проверки: Ruff passed; pytest на отдельной локальной PostgreSQL 18/Redis 8 — 277 passed, 2 предупреждения зависимостей. Проверены МСК/UTC boundary, 4-week wrap, prelaunch, event start/end, invalid config и отсутствие input в error text, пересечение границы во время settlement, durable replay/restart без второго списания, legacy skeleton. Monte Carlo slot-siege-1 seed42/trials200000/bet10 совпал с reports/monte-carlo/slot-siege-1.json по всем 10 полям (RTP0.977405, hit_rate0.311505); отчёт и paytable не менялись.
- Осталось: CI Verify на head, внешний Claude Code review, UI #77. Docker daemon недоступен, Compose build — CI gate. Merge/deploy/серверные действия не выполнялись.

- Дополнение к #76: действующий docker-compose.prod.yml перечисляет environment API явно и пока не передаёт новые SLOT_EVENT_* поля. Календарная ротация не требует новых env; для arena в production перед включением требуется отдельный deployment-конфигурационный change/override, передающий все три поля. Production Compose не входил в allowlist #76 и не менялся. Одной записи этих переменных в host .env недостаточно.

## 2026-10-13 — Hold’em UI «Камуро-тё» (#75)

- Codex, модель/effort клиента не отображаются; запрошен high. Серверный контракт проверен в #74; cancel требует PR #79. PokerRoom теперь имеет лобби bot/pvp и столы 100/500/1000, самостоятельный seat snapshot, WS + polling/reconnect, восстановление UUID запросов из sessionStorage после потери ответа/reload. Баланс меняется только из подтверждённого снимка; DEMO — записанная сцена без wallet mutation.
- Встроены утверждённые roster/intro/scene и sources.json, рубашка дракона из превью, локальный Permanent Marker с Apache license. Герой только по hero_code. Скрытые карты до явного showdown; legal_actions, текущие пределы рейза, банк, улицы, таймер pvp, печать/текст результата. Заставка имеет keyboard focus, underlying table inert; reduced motion без заставки/удара. Источники доступны в комнате.
- Решение владельца в этой сессии: сервер не отдаёт ник/аватар PvP; сейчас нейтральное «Живой игрок», отдельная серверная задача #81. Новые API-поля не выдуманы, сервер в этой ветке не менялся.
- Проверки: miniapp:check 0 errors/0 warnings; miniapp:test 41 passed; build прошёл как webServer E2E; весь Playwright suite 43 passed (2 workers, изолированный порт 4175, стандартный 4173 занят другим preview). Проверен screenshot 375×812, широкий экран/reduced motion E2E. Тест поля рейза выявил молчаливый сброс ввода на минимум; код исправлен, отрицательный кейс теперь passed. Три прежних E2E обновлены под утверждённый lobby → start → call и новое имя комнаты вместо CHECK на skeleton; проверки честной DEMO-пометки сохранены.
- Ручная приёмка: Telegram → Hold’em → bot → каждый стол → заставка → К столу → ход → итог; PvP двумя аккаунтами → поиск → match → 20 s без хода → серверный check/fold; cancel до match без списания; потеря сети при ходе → reload → повтор с прежним UUID; iOS/Android safe area, Tab/Enter, reduced motion. Telegram WebView и production не проверены.
- Осталось: CI Verify на head, внешний Claude Code review, #79 перед выпуском UI; #81 отдельный approved BuildSpec. Merge/Pages/серверный deploy не выполнялись.

## 2026-10-13 — независимый post-merge review Hold'em (#74)

- Codex, точная модель/effort клиента не отображаются; запрошен high. Проверены create/match, sorted wallet locks, ledger mismatch rollback, seat-specific HTTP/WS и replay до showdown, private bot observation/RNG, durable deadlines/hero bags и цепочка миграций 0005/0006. Новых блокеров по деньгам и закрытым картам не найдено.
- Найден недостающий серверный путь отмены поиска для #75. Action `cancel` закрывает только waiting pvp, очищает deadline, версионирует состояние; membership/replay/conflict проверяются до отмены, начатая раздача отменой не прерывается. Регрессия сначала упала на `Hold'em hand is not active`, после исправления passed; проверены повтор без второго события, отсутствие списания и отсутствие матча с закрытым поиском.
- Проверки: Ruff passed; pytest с отдельной локальной PostgreSQL 18 и Redis 8 — 270 passed, 2 предупреждения зависимостей. Alembic upgrade head → downgrade 20261013_0004 → upgrade head — passed на отдельной тестовой базе. Docker daemon недоступен; Compose build остаётся gate CI. Не подключались к рабочей базе/серверу, merge/deploy не выполнялись.
- Осталось: CI Verify на head draft PR и внешнее review. UI может использовать `payload: {action: 'cancel'}` через существующий endpoint действий.

## 2026-10-13 — браузерный QA демо (#57) и DOUBLE в демо-Blackjack (PR #78)

- Google Antigravity (Gemini) проверил опубликованное демо в Chromium (375×812 и 1440×900, обычный режим и reduced motion): ошибок консоли и сети нет, горизонтального скролла нет, DEMO-контур нигде не выдаёт себя за серверный результат; `slot-v2/` — 404 (превью публикуется вручную, не дефект). Отчёт передан владельцем и опубликован в #57.
- Единственное замечание — в демо-Blackjack после HIT оставался DOUBLE. Claude Code (claude-opus-5-5): `runDemoBlackjackAction` в `+page.svelte` после HIT сужает действия до `hit`/`stand`, как домен и сервер; новый e2e-тест сначала красный, после правки зелёный.
- Проверки: `pnpm miniapp:check` — 0/0; `pnpm miniapp:test` — 38 passed; весь Playwright e2e — 36 passed; CI `verify` на PR — passed. Локально порт 4173 может быть занят другим сервером — тогда Playwright тестирует не тот сайт.

## 2026-10-14 — интеграция очереди по поручению владельца

- Владелец явно поручил Codex «Мерджи все», включая автоматическую Pages-публикацию UI. Открытая очередь: #78, #80, #79, #82, #83, #84. #78 и #80 уже слиты обычными merge commits; остальные ветки собраны последовательной цепочкой зависимостей для проверки CI на точных head перед каждым merge.
- Конфликты только в ProjectLog/ChangeLog разрешены с сохранением записей обеих сторон; изменения +page и E2E применились автоматически. Удалён один trailing-whitespace в сгенерированной SVG-рубашке (вид изображения не меняется). Force-push не выполнялся, чужие ветки не менялись.
- Совместный локальный прогон четырёх Codex-изменений до merge: Ruff passed, PostgreSQL/Redis pytest 278 passed, miniapp check 0/0, frontend unit 43 passed, E2E 45 passed. Дополнительный DOUBLE-тест #78 и конфигурация E2E_PORT #80 проверяются в CI объединённой цепочки. Итоговые merge SHA и статусы CI/Pages публикуются в комментариях PR.
- Серверный deploy не входит в поручение и не выполняется. Ручная Telegram/iOS/Android приёмка, nickname/avatar #81 и передача SLOT_EVENT_* в production environment остаются отдельными задачами.

## 2026-10-14 — первый деплой на сервер и исправления по живому Telegram

- Claude Code (claude-opus-5-5) по поручению владельца: сервер переустановлен владельцем, по `docs/Deploy-Production.md` выполнены разделы 3–6; `BOT_TOKEN` ввёл владелец. Работают postgres, redis, api, miniapp, caddy и bot (@Burmaldoza_bot), сертификаты Let's Encrypt на четыре домена, миграции до `20261013_0006`.
- В живом Telegram найдены и исправлены: Mini App оставалась в DEMO — не был подключён `telegram-web-app.js` (PR #85); Hold'em не начинался — клиент не принимал масть словом (`hearts`) из домена (PR #88); колода Deck A существовала только на превью — портреты и рубашка S09 подключены в комнату Blackjack с атрибуцией (PR #89). Runbook дополнен по итогам деплоя (PR #86).
- Проверки: `/health/ready` — ok; внутренние маршруты снаружи — 404; наружу слушаются только 22/80/443; `pnpm miniapp:test` — 44 passed; e2e — 46 passed. `slot-siege.spec.ts` «server faces stay…» дважды падал в CI и проходил на перезапуске — нестабилен (Codex).
- Осталось: резервное копирование (разделы 7–8, ключи `age` владельца), Portainer, решение владельца о числе линий слота.

## 2026-10-14 — выбор ставки: пять сумм и слайдер

- По запросу владельца (Claude Code, claude-opus-5-5): общий `BetPicker.svelte` — пять быстрых сумм, слайдер и поле ввода. Слот: 10/20/30/50/100 и любая сумма 10–100, спин отправляет выбранную ставку (раньше всегда 10). Blackjack: 25/40/50/75/100 и 25–100 вместо поля и трёх фишек. Hold'em: размер рейза — мин., ½ банка, ¾ банка, банк, ва-банк и слайдер до всего стека. Столы Hold'em (100/500/1000) не менялись.
- Сервер не менялся: он уже принимал ставку слота 10–100 и проверяет каждую сумму.
- Проверки: `pnpm miniapp:check` — 0/0; `pnpm miniapp:test` — 44 passed; Playwright e2e — 48 passed, включая новый `bet-picker.spec.ts` (живой спин отправляет выбранную ставку, превышение блокирует кнопку).

## 2026-10-14 — проект спецификации профиля Hold’em PvP (#81)

- Владелец поручил Codex выполнить #81. В отдельной ветке codex/holdem-opponent-profile подготовлен раздел BuildSpec на утверждение: проверенный username, аватар через Bot API и авторизованный room endpoint, ограниченный временный кэш в памяти, отсутствие миграций и раскрытия идентификаторов/URL источника.
- Предлагаемые лимиты: 64 фото по 256 KiB, TTL 1 час / 5 минут без фото / 30 секунд при сбое; 30 запросов/минуту на игрока, 60 загрузок/минуту глобально, две одновременно, deadline 5 секунд. Фото не участвует в snapshot/action/ledger и не задерживает игру.
- Проверки: git diff --check — passed; документы сверены с текущими auth/project_public и официальным Telegram Bot API. Код и конфигурация production не менялись, тесты реализации пока не запускались.
- Осталось: явное утверждение этого дополнения BuildSpec владельцем, затем реализация API/UI и тесты приватности, ошибок источника и reconnect. needs-owner в #81 сохраняется до решения.

## 2026-10-14 — профиль живого соперника Hold’em (#81)

- Владелец утвердил предложенную схему после объяснения в сессии: «Делай». Gate needs-owner снят. Ник берётся из User.username, подтверждённого initData; нейтральное имя при отсутствии/удалении. Одна seat-specific проекция для HTTP/WS; профиль не сохраняется в room state/events/ledger и не раскрывает ID/display_name/закрытые карты. Исторические события показывают последний подтверждённый ник, как утверждено BuildSpec.
- Авторизованный room avatar endpoint проверяет членство до кэша и определяет противоположное место сам. Bot API getUserProfilePhotos/getFile, ограниченный streaming download только с api.telegram.org, без redirects/произвольного URL. Фото JPEG/PNG, no-store/nosniff; token-bearing transport logs подавляются только в контексте этих запросов. Кэш 64 фото до 256 KiB, TTL 1 час / 5 минут без фото / 30 секунд при сбое; лимиты 30 запросов/мин на игрока, 60 загрузок/мин глобально, две одновременно, deadline 5 секунд и upstream Retry-After. Совпадающие загрузки объединяются; остановка API отменяет незавершённые загрузки. Новых зависимостей, env или миграций нет.
- UI показывает проверенный ник, получает фото с auth header и локальным blob URL; отменяет устаревший запрос, освобождает URL при уходе, использует нейтральную иконку при ошибке/отсутствии фото. DEMO не делает запросов аватара. Polling snapshot не перезапрашивает картинку каждые 2 секунды; reload/reconnect/явный resync допускает повтор. Старый API без профиля совместим.
- TDD: профильная регрессия сначала упала с KeyError opponent_profile, затем passed. Проверки: Ruff passed; полный pytest с изолированной PostgreSQL 18/Redis 8 после синхронизации с актуальным main — 293 passed, 2 предупреждения зависимостей. Mini App check — 0 errors/0 warnings; unit — 45 passed; build и полный Playwright Chromium — 47 passed. Проверены освобождение blob URL при уходе и восстановление после reload; после синхронизации с main полный E2E повторно дал 47 passed. Исходный порт тестовой PostgreSQL был запрещён Windows; на новом loopback-порту проверки прошли. Рабочая база/production не использовались.
- Ручная приёмка после серверного выпуска: двумя аккаунтами открыть PvP на одинаковом столе, проверить чужой @username/аватар и закрытые карты; выйти/вернуться и reload; удалить ник/скрыть фото у одного аккаунта и повторить вход (фото может обновляться до часа); отключить доступ API к Telegram — игра продолжается с нейтральной иконкой. Telegram WebView/iOS/Android и настоящий Bot API не проверены, внешний HTTPS необходим. Docker daemon локально недоступен: Compose build проверяет CI.
- PR #87; перед merge требуется Verify на текущем head и независимый review. Merge/Pages/серверный deploy не выполнялись. Production compose, RNG, правила игр, wallet/ledger и схема БД не менялись.

## 2026-10-14 — слот: 9 линий, ruleset `slot-siege-2` (#91)

- Claude Code (claude-opus-5-5) замещает Codex по поручению владельца. Решение владельца: 9 линий — 7 рядов и 2 диагонали, ставка 10 JG за спин, RTP ≈ 0.9626.
- `slot_siege_2.json`: таблица множителей прежняя (D1 ×1 … W ×50); при 9 линиях симметричные барабаны не дают нужный RTP (минимум 0.9676), поэтому барабаны разные: на каждом свои частые символы, не больше 10 одинаковых из 30, у каждого символа минимум одна позиция. Точный перебор 30³ остановок: RTP 0.962667, выигрышный спин 44.18 %, максимум ×72 ставки. Monte Carlo 200 000 спинов (seed 42): RTP 0.959, hit rate 0.4415, дисперсия 482 (у siege-1 — 1266) → `reports/monte-carlo/slot-siege-2.json`.
- Новые комнаты создаются на `slot-siege-2`; комнаты `slot-siege-1` и `slot-skeleton-1` доигрывают по своим правилам; ротация операций работает для обеих Siege-версий. Клиент: «LINES 9 active», лучи для любых рядов и диагоналей.
- Нестабильный `slot-siege.spec.ts`: причина в интерфейсе — кнопка спина включалась после остановки барабанов, а родитель снимал занятость только после анимации итога и молча отбрасывал быстрое нажатие (барабаны крутились без запроса). Теперь `SlotRoom` получает `busy` и держит кнопки спина и Free Spin выключенными до конца итога.
- Проверки: `ruff check` — passed; `pytest -q` — 261 passed, 14 skipped (PostgreSQL — CI); `pnpm miniapp:check` — 0/0; `pnpm miniapp:test` — 46 passed; Playwright e2e — 56 passed, включая `slot-lines.spec.ts`.

## 2026-10-14 — ставки до баланса, дилер, анимация раздачи, заголовок хаба

- Замечания владельца после проверки в Telegram (Claude Code, claude-opus-5-5). Ставки: «стандартные пять и отдельно своя ставка вплоть до всего баланса» — `BetPicker` разделён на пять сумм и блок «Своя ставка · до N JG» (слайдер и ввод до текущего баланса); сервер: минимум прежний (слот 10, Blackjack 25), верхняя граница — технический потолок 1 000 000, нехватку баланса отклоняет кошелёк; `/rulesets` отдаёт `max_bet` 1 000 000.
- Blackjack: портрет куклы-дилера вместо буквы; убраны подпись «GFL DOSSIER · DECK A» и штамп «S09 / РУБАШКА A» (решение владельца отменяет замечание review #89); карты привязаны к номеру раздачи — на повторной раздаче монтируются заново и снова проигрывают анимацию сдачи, портреты грузятся сразу (`eager`).
- Хаб: заголовок «Где сегодня сливаем хату?».
- Проверки: `ruff check` — passed; `pytest -q` — 262 passed, 14 skipped; `pnpm miniapp:check` — 0/0; `pnpm miniapp:test` — 46 passed; Playwright — 57 passed (новые: повторная раздача пересоздаёт карты, портрет дилера, ставка до баланса).

## 2026-10-14 — комнаты в стиле хаба: оболочка и Blackjack; порталы Тачанка и Кирю

- Поручение владельца: «все три комнаты привести к виду хаба, не меняя их концепцию»; рейтинг и история из комнат убраны (решение владельца). Claude Code (claude-opus-5-5), этап 1 из 3.
- `RoomShell.svelte`: тема комнаты, сцена во весь экран с «дыханием» (Blackjack — утверждённый `room-police-perimeter` → `static/blackjack/room.webp`, мигалки; Slot — дым и прожекторы на CSS; Hold'em — ворота Камуро-тё с неоном), шапка как в хабе (назад, название, баланс-«пилюля» = `resync-button`), пауза хаба и reduced motion останавливают фон. `ResultBand`: без «RESULT BAND/RESOLVING», ожидание — точки, выплата «выпрыгивает»; тексты подтверждения сервера сохранены.
- Blackjack: убраны дубль заголовка и строка «PHASE … v…», стол со свечением и бликом, кнопки действий в один ряд со стеклом и откликом.
- Порталы хаба (поручение владельца): Slot — Тачанка, Hold'em — Кирю из Like a Dragon: Infinite Wealth; собраны из прежних порталов и портретов из наборов проекта (Ubisoft / SEGA RGG, некоммерческий фан-интерфейс), происхождение — `static/hub/sources.json`.
- Проверки: `pnpm miniapp:check` — 0/0; `pnpm miniapp:test` — 46 passed; Playwright — 60 passed; скриншоты 390px проверены.

## 2026-10-14 — комнаты в стиле хаба: Slot Siege (этап 2 из 3)

- `SlotRoom.svelte` (только Siege-версии; старые комнаты skeleton не тронуты): убраны дубль заголовка и служебные «RULESET/MOTION», «LINES 9 active» — значок; стеклянный контейнер поверх тактической сцены, холодное свечение автомата, при вращении рамка разгорается и по барабанам идёт луч сканера; светлая тактическая кнопка спина с откликом; reduced motion отключает луч.
- Проверки: `pnpm miniapp:check` — 0/0; `pnpm miniapp:test` — 46 passed; Playwright — 57 passed.

## 2026-10-14 — комнаты в стиле хаба: Hold'em «Камуро-тё» (этап 3 из 3)

- `PokerRoom.svelte`: стекло над воротами Камуро-тё, «Камуро-тё» — неоновая вывеска с мерцанием, выбор соперника и стола — карточки-«таблички» (переключатели остаются внутри для доступности и тестов), красная неоновая кнопка старта с откликом; дубль метки «神室町 · HEADS-UP» убран (он в шапке). Стол и правила не менялись.
- Проверки: `pnpm miniapp:check` — 0/0; `pnpm miniapp:test` — 46 passed; Playwright — 57 passed (в первом полном прогоне два теста Blackjack/Slot упали по времени под нагрузкой, отдельно 3×3 зелёные, повторный полный прогон зелёный).
- Производительность: CI поймал «reel stalled» в `slot-stop.spec.ts`. Стресс-прогоны (8 повторов × 6 потоков) показали причину — анимированный `filter: blur` дыма в сцене слота и `backdrop-filter` поверх вращающихся барабанов. Размытие дыма убрано (мягкость дают градиенты), большие контейнеры (Slot, стол Blackjack, Hold'em) — без `backdrop-filter`, плотнее фон; луч сканера на отдельном слое оставлен. Итог: 24/24 стресс-прогона вместо 3–4 падений из 24 (исходная версия — 1 из 16), полный e2e 57 passed за 29 с вместо 42 с.

## 2026-10-14 — цельные иллюстрации порталов героев (#99)

- Codex: коллажи Slot и Hold'em заменены цельными иллюстрациями встроенного ImageGen, с композицией и золотой рамкой портала SOPPO. Тачанка — Maska «Д 045», Кирю Infinite Wealth — седые волосы, бородка, тёмная рубашка. Референсы личности не добавлены в репозиторий. © Ubisoft / © SEGA RGG, некоммерческий фан-интерфейс.
- Два runtime WebP 640×1280: Slot 196 558 байт, Hold'em 195 514 байт, ≤200 000 каждый. sources.json содержит происхождение, размеры и SHA256. README описывает промпты и встроенный ImageGen; скриншоты до/после 390×844 сохранены рядом. Код и комнаты не менялись.
- Проверки: miniapp:check — 0 errors/0 warnings; miniapp:test — 46 passed; miniapp:e2e на изолированном порту 4198 — 57 passed, включая hub 320px и загрузку всех изображений. Визуально проверены надписи и набор порталов на 390px; git diff --check — passed.
- Осталось: CI на опубликованном head, review Claude/владельца и ручная приёмка Telegram iOS/Android. Merge, Pages и серверный deploy не выполнялись.

## 2026-10-14 — сцены, анимации и компоновка трёх комнат (#100)

- Codex, ветка codex/rooms-design-polish от 33746af: три вертикальные сцены встроенного ImageGen 1080×1920, каждая ≤250 000 байт, с происхождением и SHA256 в sources.json. GFL — полицейский периметр над столом; Siege — бетон/прожекторы/дым; Камуро-тё — ворота, красный неон и дождь. Сервер, domain, RNG, API, ставки/лимиты не менялись.
- Переход хаб ↔ комната — масштаб/затемнение 340 мс с центром выбранного портала. RoomShell передаёт паузу оформления через context; пауза хаба и reduced motion отключают декор, не блокируя действия и подтверждённые исходы. Сцены анимируются transform/opacity; размытие поверх движущихся карт/барабанов не добавлено, анимация filter при приземлении барабана заменена opacity.
- Blackjack: колода у дилера, полёт карт, две стороны при flip закрытой карты, золотая вспышка и фишки при победе / затемнение при поражении. Рука компактна, ставка только между руками; повторный итог не дублируется визуально, LIVE/DEMO подпись сохранена. Slot: сворачиваемые ставка/справочник, выигрышные клетки, счётчик до точной подтверждённой выплаты и эффект ≥×20 по ставке завершённого спина (восстановление gross−net при reconnect). Hold'em: неоновые действия, BetPicker рейза, карты/борд по порядку, фишки в банк, реальное вскрытие рубашки в лицо и штамп итога; кольцо у текущего места по серверному deadline.
- Регрессия высоты Blackjack сначала красная, после правок зелёная. Новые E2E проверяют полные итоги всех комнат без скролла при 390×844, 320px без горизонтального скролла, загрузку сцен, паузу и доступность действий; fixtures имеют согласованные карты, линии, суммы и последовательные балансы. 24 PNG до/после + промпты/ручная приёмка — assets/design/rooms-polish. До снято с отдельного чистого checkout 33746af; это mocked LIVE Chromium, не настоящий Telegram/сервер.
- Проверки: miniapp:check — 0 errors/0 warnings; miniapp:test — 46 passed; полный miniapp:e2e — 63 passed. Стресс Slot slot-stop.spec.ts:9, repeat-each=8/workers=6 — три прогона по 8, 24/24. Весь blackjack-room.spec.ts с теми же параметрами — три прогона по 80, 240/240. Размеры/хэши трёх сцен и размеры всех 24 PNG проверены; git diff --check — passed.
- Два независимых read-only review (code и TypeScript, gpt-6-sol/high): исправлены зеркальное лицо при flip, обрезка итога и противоречивые fixtures; блокирующих замечаний после исправлений нет. Изменённые старые тесты открывают новую панель ставки, проверяют новые человеческие подписи и ждут cleanup после outro; data-testid сохранены.
- Осталось: Verify на опубликованном head, review Claude/владельца и ручная Telegram iOS/Android приёмка после выпуска. Новых runtime-зависимостей нет; для проверок использованы pnpm 11.19.0, проектные frontend зависимости, Playwright Chromium и Pillow 12.2.0 для сжатия арта. Docker/серверные проверки — CI, настоящий API/Telegram здесь не тестировался. Merge/Pages/server deploy не выполнялись.

## 2026-10-14 — доводка комнат (#100, PR #103): завершение за Codex

- Claude Code замещает Codex (лимит). Закоммичены незавершённые правки Codex: переходы только по `transform`/`opacity`, лучи линий появляются через `opacity`; e2e 320px ждёт LIVE, паузу хаба и загрузку сцены вместо разового чтения (причина падения CI на `a0ca2a0`).
- Review: ячейки слота Codex уменьшил до `clamp(38px, 10.25vw, 50px)` ради «всё в экран» — это противоречило решению владельца (#101). Возвращено `clamp(48px, 14.2vw, 70px)`; кнопка спина остаётся в первом экране (низ на 802 px из 844), e2e проверяет именно её. Имена на картах Blackjack больше не рвутся посреди слова. Скриншоты «после» обновлены.
- Проверки: `pnpm miniapp:check` — 0/0; `pnpm miniapp:test` — 46 passed; Playwright — 63 passed; стресс `slot-stop.spec.ts:9` — 16/16, `rooms-polish` 320px ×5 — 15/15.

## 2026-10-14 — резервное копирование и проверка восстановления (runbook 7–8)

- Claude Code (claude-opus-5-5) по поручению владельца. Ключи `age` создал владелец на своём ПК; закрытый ключ только у владельца (права файла — только его учётная запись), на сервере — открытый ключ.
- Сервер: `/usr/local/bin/burmaldoza-backup` по runbook 7.2, каталог копий 700 / файлы 600, cron пользователя `deploy` — `30 3 * * *` (время сервера, Europe/Amsterdam ≈ 04:30 МСК). Первая копия `burmaldoza-20261014T081129Z.dump.age` (64 КБ) при коде `eb554ae`.
- Проверка восстановления (раздел 8): расшифровка на ПК владельца, поток по SSH в отдельную базу `burmaldoza_restore_20261014081145`, `pg_restore --single-transaction --exit-on-error` — успешно. Агрегаты копии и боевой базы совпали: users 2, wallets 2, operations 74, entries 96, sum(balance) 1136 = sum(ledger) 1136, `inconsistent_wallets = 0`, ревизия `20261013_0006`. Проверочная база удалена.
- Копия вне сервера (7.3, решение владельца): ПК владельца — задача планировщика Windows ежедневно в 12:00 и при входе в систему забирает новые `*.dump.age`, журнал и предупреждение, если свежей копии нет больше 48 часов. Скрипт и копии — вне репозитория. Старые архивы на сервере не удаляются автоматически (хранить минимум 14 дней).

## 2026-10-14 — звук и вибрация (пакет владельца)

- Поручение владельца: использовать его пакет `Game_Audio` (OST и голоса GFL, OST/звуки R6, OST Yakuza, звуки интерфейса GFL). Решение владельца: файлы из игр — только на сервере (риск DMCA для публичного репозитория и Pages).
- Сборщик `devtools/audio/build_pack.py` + отбор `selection.json` (ffmpeg → AAC, выровненная громкость, музыка ≤ 4 мин): 10 треков по сценам, 5 эффектов, голоса 6 кукол-дилеров; 59 файлов, 21 МБ → `/srv/burmaldoza-audio`. Caddy: `/audio/*` из тома только для чтения (синтаксис проверен `caddy validate` на сервере).
- Клиент `lib/audio/sound.ts`: переключатель в шапках (по умолчанию выключено, запоминается), музыка сцены с плавной сменой через Web Audio, синтез коротких сигналов, R6-сэмплы в слоте, голос дилера в Blackjack (пул дилеров — куклы с голосом и портретом: HK416, G36, M4 SOPMOD II, Makarov, Mosin-Nagant, PPSh-41), звуки интерфейса GFL; вибрация Telegram на тех же подтверждённых событиях (раньше обёртка нигде не вызывалась).
- Найдено по ходу: реактивные `$:` с объектом сессии в `+page.svelte` сбивали порядок обновлений (демо-слот не получал результат) — сцена и reduced motion передаются звуку явными вызовами.
- Проверки: `pnpm miniapp:check` — 0/0; `pnpm miniapp:test` — 49 passed (3 новых); Playwright — 64 passed (`sound.spec.ts`); `ruff check devtools/audio` — passed.

## 2026-10-14 — звуковой пакет: повторный просмотр после докачки

- Пакет вырос до 2950 файлов / 8,9 ГБ (Yakuza 5–Infinite Wealth, Gaiden, Ultimate Quotes, новые треки GFL). Отбор обновлён: Hold'em — музыка казино и игорного дома из Yakuza 5 (`minig casino/toba kinpaku`), Gaiden «Gambling Match» и «The Sleepless Castle», «The Dawn of the Cabaret Club»; Blackjack — плюс GFL «Secret Agent»; заставка «новая глава» Yakuza (`system chapter`) на представлении соперника в Hold'em (событие `intro`, без пакета — синтез тайко).
- Не взяты: `mahjong reach` (музыка «почти выиграл» — запрещено принципом 2), Ultimate Quotes (99 безымянных фраз по 10–45 с — для реплик за столом длинные, содержание без названий неизвестно).
- Сборщик: эффект может задать свою длину (`{"src", "max"}`). Пакет 63 файла, 25 МБ — на сервере.
- Проверки: `pnpm miniapp:check` — 0/0; `pnpm miniapp:test` — 49 passed; Playwright — 64 passed; `ruff check devtools/audio` — passed.

## 2026-10-14 — голос Кирю в Hold'em

- Владелец уточнил: Ultimate Quotes CD — фразы и звуки Кирю (99 треков, 42 мин). Сборщик режет склейки по паузам (тишина ниже -35 dB дольше 0,35 с), берёт куски 0,5–4 с равномерно по диску: 48 реплик (0,7–3,8 с, в среднем 1,9 с) → голос `Kazuma_Kiryu`, группа `quip`.
- Hold'em: когда соперник — Кирю, он подаёт реплику после заставки «новая глава» и после итога каждой раздачи; подключение общее по `hero_code` — другие герои заговорят, когда их реплики появятся в отборе.
- Пакет 111 файлов, 26 МБ — на сервере. Проверки: `miniapp:check` 0/0; `miniapp:test` 49 passed; Playwright 64 passed; `ruff` passed. Реплики нарезаны автоматически и не прослушаны агентом — неудачные куски владелец отмечает, отбор фильтруется.

## 2026-10-14 — независимое review #94/#95 и исправление #105

- Codex, GPT-6; точный effort клиента не отображается (запрошен high).
  Review опубликован комментариями в #94 и #95. База `main` `eb554ae`.
- #94: замечаний нет. Независимый перебор JSON без движка по 27 000 остановкам:
  RTP 361/375 = 0.9626666667, hit 11 929/27 000 = 44.1815%, максимум ×72.
  Monte Carlo siege-2 seed42/200000/bet10 полностью совпал с report (RTP 0.959).
- #95: P1 — разрешённая выплата переполняет INTEGER balance_after:
  баланс 2 100 000 000, ставка 1 000 000, stops (15,16,17), выплата 72 000 000,
  итог 2 171 000 000; PostgreSQL/asyncpg падает с value out of int32 range.
  P2 — Slot/Blackjack предлагают ставку выше существующего API ceiling 1 000 000.
- Владелец явно утвердил BIGINT и исправления; дополнение записано в BuildSpec.
  Миграция 20261014_0007 переводит шесть денежных полей в BIGINT, UI ограничен
  min(balance, 1 000 000). RNG/paytable/правила и стековый cap Hold'em не менялись.
- Красные регрессии до правки: реальная выплата ×72 — int32 overflow;
  два browser ceiling теста ожидали 1 000 000 и получили 2 171 000 000.
  После правки: pytest с PostgreSQL18/Redis — 303 passed; ruff — passed;
  miniapp:check — 0/0; miniapp:test — 46 passed; полный E2E workers=2 — 65 passed.
  Новый concurrency-тест: две ставки на весь баланс в разных Blackjack-комнатах,
  одна принята; DOUBLE без средств не меняет ни room state, ни ledger.
  Durable slot replay в новой DB-сессии возвращает ту же выплату без повторного RNG.
- Реальная Alembic-проверка на отдельной локальной БД: upgrade с 0006, все шесть
  денежных типов bigint; downgrade/upgrade с 2.1b сохраняет баланс; при 2.171b
  downgrade отклоняется до изменения типов, ревизия/суммы остаются прежними.
  alembic check выявил 12 расхождений nullability timestamp вне этой задачи;
  metadata comparison подтвердил отсутствие денежных/type diffs. Это не зелёный
  общий alembic check; несвязанные timestamp не исправлялись.
- Code/Python/TypeScript независимые read-only review: подтверждённых блокеров нет.
  Старый E2E assertion обновлён только под уточнённую подпись лимита; новый Slot-тест
  переоткрывает сворачиваемый блок после изменения суммы. Во время параллельных
  локальных прогонов были timing flakes и конфликт двух сборок EPERM; финальный
  изолированный полный E2E зелёный, flaky unrelated тесты не переписывались.
- Dependencies: uv locked groups, Python 3.13.13, pnpm 11.19.0, Chromium,
  локальные PostgreSQL18 и Redis (WSL); Docker daemon недоступен, compose build
  остаётся CI. Новых runtime dependencies нет. Production/Telegram не проверялись.
- Осталось: CI текущего head, review Claude/владельца; миграцию выполнять в окне
  обслуживания (ALTER TYPE берёт блокировки/переписывает таблицы), backup и остановка
  API перед upgrade, затем запуск нового API. Downgrade больших сумм запрещён,
  безопасный путь отката кода — сохранить BIGINT-схему. Server deploy/merge не делались.

## 2026-10-14 — портал TACHANKA’S LUCK (#106)

- Codex, модель GPT-6; точный effort клиента не отображается (запрошен low).
  Встроенный ImageGen перегенерировал арт из PR #102 (`b6196d0`): светлая
  TACHANKA’S с U+2019 и золотая LUCK вписаны в иллюстрацию, таблички нет.
- Runtime `slot-portal.webp`: 640×1280, 194 736 байт, SHA256
  `c064e61ee967140216541b1767f7a91d297cf51e389781004ba123fbd731d700`.
  Происхождение/хэш/байты обновлены в sources.json, промпт и ручная приёмка —
  assets/design/hub-atrium/README.md; before/after Chromium DEMO 390×844 сохранены.
- Проверки: miniapp:check — 0/0; miniapp:test — 46 passed;
  полный E2E с workers=1 — 63 passed, включая hub 320/390/1440.
  В первом параллельном прогоне wallet-relief получил timeout (62 passed);
  полный последовательный прогон зелёный. Это Chromium DEMO/mocked LIVE,
  настоящий API и Telegram WebView здесь не проверялись.
- Зависимости: pnpm 11.19.0, locked frontend, Playwright Chromium, встроенный
  ImageGen и Pillow для WebP (новых runtime-зависимостей нет).
- Осталось: CI опубликованного head, review Claude/владельца и ручная Telegram
  iOS/Android приёмка; merge меняет Pages. Merge/server deploy не выполнялись.
