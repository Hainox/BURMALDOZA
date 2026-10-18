# Blackjack Shared Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Отдельный Blackjack GFL стол для 1–3 игроков против общего дилера с сохранением выбора игры с ботом.

**Architecture:** Новый чистый blackjack_table domain и отдельный BlackjackTableService. RoomService направляет только mode=table в новый сервис; существующий solo path не переписывается. PostgreSQL хранит общий private state и deadline; WS и HTTP используют одну проекцию.

**Tech Stack:** Существующие Python 3.12+, FastAPI/Pydantic/SQLAlchemy, PostgreSQL 16/Redis 7, SvelteKit, Vitest и Playwright; новых runtime dependencies нет.

**Spec:** [2026-10-18-blackjack-shared-table-design.md](../specs/2026-10-18-blackjack-shared-table-design.md)

## Global Constraints

- Общий стол — 1–3 реальных игрока против одного серверного дилера, с отдельными руками, ставками и расчётом каждого игрока.
- Исходная ставка 25–1 000 000 JG; Blackjack 3:2 с существующим целочисленным округлением; дилер стоит на soft 17.
- Ходы по порядку мест: Hit / Stand / Double. На каждое решение 20 секунд; истечение срока означает Stand.
- Сервер — источник исхода, CSPRNG только на сервере; средства меняются только через WalletService.
- Сохраняются существующие solo-комнаты и игра с ботом, GFL оформление, DEMO solo и reduced motion.
- API один worker; новые runtime dependencies, миграции и production config не входят в план.
- Это проект технического плана для review. Продуктовые правила #116 согласованы; код до review плана не меняется.

## Review Focus

1. Ставка готового игрока потрачена в другой комнате: start откатывается целиком (задача 2).
2. Вышедший участник с активной ставкой: его слот не переиспользуется до расчёта (задачи 2–3).
3. Старый timeout и новый Hit приходят вместе: только один переход версии (задача 3).
4. WS событие дошло после выхода: оно не раскрывает состояние бывшему участнику (задача 3).
5. В браузере 320px, старый API или DEMO: solo остаётся доступным, онлайн не подменяется демо (задача 4).

## Совместная работа

Покер на шестерых — отдельная задача и ветка. Общие файлы `rooms.py`, `routers/rooms.py`,
`room_service.py`, `main.py`, `+page.svelte`, `lib/api/client.ts` правит один implementer
в согласованном порядке. Новые domain-модули и тесты независимы. Интегратор перед
каждым общим файлом сверяет открытые PR и текущий main; чужую ветку не изменяет.

### Task 1: Общая колода и руки — чистый domain

**Files:** Create `packages/domain/src/burmaldoza_domain/games/blackjack_table.py`; Test `tests/unit/domain/test_blackjack_table.py`.

**Interfaces:**
- Consumes: существующие Card, BlackjackRules, hand_value, RandomSource; solo engine без изменения.
- Produces: frozen `TableHand(seat, bet, cards, doubled, finished)`, `BlackjackTableState(hands, dealer_cards, deck, active_seat, settled, ruleset_version)` и `TableOutcome(seat, result, payout, net_delta)`.
- `deal_table(bets: dict[int, int], rng: RandomSource, rules: BlackjackRules) -> BlackjackTableState`.
- `apply_table_action(state: BlackjackTableState, seat: int, action: BlackjackAction, rng: RandomSource, rules: BlackjackRules) -> BlackjackTableState`.
- `settle_table(state: BlackjackTableState, rules: BlackjackRules) -> tuple[TableOutcome, ...]`.
- Сериализация приватного state и проекция — задача 2, domain не знает user ID/кошельков/времени.

- [ ] Написать красные тесты с фиксированным RNG: 1/2/3 игрока получают по 2 карты и ровно один общий dealer; объединение рук+dealer+deck — 52 уникальные карты; 0/4 игрока и чужой seat дают InvalidActionError/ValueError.
- [ ] Запустить `uv run --locked pytest -q tests/unit/domain/test_blackjack_table.py`; убедиться, что падение из-за отсутствующей реализации.
- [ ] Реализовать frozen state и deal_table; initial natural Blackjack пропускает ход, dealer natural завершает начальную раздачу по текущим правилам.
- [ ] Добавить красные проверки: dealer не добирает после первого Stand, пока осталось активное место; Double даёт одну карту и завершает ход; Hit после перебора запрещён.
- [ ] Реализовать apply_table_action: очередь по seat, переход к единственному dealer resolution после последней руки, без reshuffle в середине. Чужой turn запрещён.
- [ ] Добавить payout-тесты: natural при bet=25 даёт gross=62, push возвращает ставку, проигрыш=0; удвоенная ставка 50 учитывается только у удвоившего; dealer soft17 стоит.
- [ ] Реализовать settle_table и запустить domain Blackjack/Monte Carlo regressions плюс новые тесты.
- [ ] Commit `feat(blackjack): add shared dealer table domain`.

### Task 2: Durable lobby, ставки и атомарный расчёт

**Files:** Create `apps/api/app/services/blackjack_table_service.py`; Modify `packages/contracts/src/burmaldoza_contracts/rooms.py`, `apps/api/app/services/room_service.py`, `apps/api/app/routers/rooms.py`; Test `tests/unit/test_blackjack_table_server.py`, `tests/integration/test_blackjack_table_concurrency.py`.

**Interfaces:**
- Consumes domain Task 1, существующий RoomService/WalletService и GameRoom/GamePlayer/GameRound.
- Produces `BlackjackTableService(rooms: RoomService)` с `create(user_id: int, action_id: UUID) -> RoomSnapshot`, `join(room_id: UUID, user_id: int, action_id: UUID) -> RoomSnapshot`, `apply(room_id: UUID, user_id: int, request: ActionRequest) -> EventEnvelope`, `project_snapshot(room: GameRoom, user_id: int) -> RoomSnapshot`.
- Strict `RoomJoinRequest(action_id: UUID)`; RoomCreateRequest разрешает blackjack/table+action_id без buy_in. Старые solo и Hold’em валидаторы сохраняются.
- Public state и verbs соответствуют спецификации; round state сериализуется отдельным codec в новом service, не в domain.

- [ ] Написать API/service tests: auth, create replay, same actor/payload validation, join replay, 3 места/4-й отказ; solo create/deal по старым контрактам проходит.
- [ ] Запустить новые тесты, увидеть красный результат, реализовать lobby/create/join и минимальный dispatch без переписывания Hold’em.
- [ ] Добавить PostgreSQL красные тесты: два join на последнее место → только один; ready/start с другим stale version → конфликт; недостаток средств последнего игрока → ни одной ставки/карты/новой версии.
- [ ] Реализовать ready/unready/start под lock комнаты и lock кошельков в порядке user_id. Готовность денег не списывает, ставки списываются на start; deterministic operation UUID на игрока/раунд/этап.
- [ ] Добавить тесты replay start/double/settlement из новой DB session: RNG не вызывается повторно, одна ставка/доплата/выплата; чужой ключ возвращает конфликт.
- [ ] Реализовать actions и атомарные payouts: использовать текущий `apply_delta_in_transaction` с game_stake/game_payout, не повторять debit в settle_game_round. В ledger каждого игрока единый round reference.
- [ ] Добавить тест принудительной ошибки на последней выплате: весь расчёт и state откатываются; повтор без ошибки рассчитывает всех один раз. Добавить расход доступного баланса в другой комнате после ready.
- [ ] Проверить `uv run --locked pytest -q tests/unit/test_blackjack_table_server.py tests/integration/test_blackjack_table_concurrency.py` с TEST_DATABASE_URL и existing room/wallet tests.
- [ ] Commit `feat(api): persist blackjack shared table actions and settlement`.

### Task 3: Очередь, deadline, выход и закрытые данные

**Files:** Modify новый service, `apps/api/app/services/room_service.py`, `apps/api/app/main.py`; Test `tests/unit/test_blackjack_table_timer.py`, `tests/unit/test_blackjack_table_server.py`, `tests/integration/test_blackjack_table_concurrency.py`.

**Interfaces:**
- Consumes apply/project_snapshot Task 2; `RoomService.now()` для тестируемого UTC clock.
- Produces `BlackjackTableService.expire_due() -> int`; отдельный lifecycle task с отменой при shutdown, не заменяет Hold’em tick.
- Каждый переход сохраняет absolute deadline и state_version, каждое событие персонализируется и проверяет membership перед выдачей.

- [ ] Написать красные clock tests: до 20 секунд auto-Stand нет; ровно на deadline есть; Hit до deadline даёт следующий срок; повтор tick не повторяет state/ledger. Проверить восстановление просроченной комнаты новым service после рестарта.
- [ ] Реализовать deadline tick, stable timeout UUID, повторную проверку под room lock и изоляцию ошибок комнат. Не публиковать event до commit.
- [ ] Добавить PostgreSQL race timeout/Hit: один переход версии; чужой/запоздалый ход отвергнут; payouts остаются ровно один раз.
- [ ] Добавить late join/leave tests: ожидающий без карт/ставки, уходящий участвует в текущем расчёте и занимает слот до него; host transfer минимальному оставшемуся seat, пустой стол закрывается после расчёта.
- [ ] Реализовать leave/host transfer и возврат lobby после settled; WS disconnect не делает leave.
- [ ] Написать HTTP+WS projection tests: до раскрытия отсутствуют hole card/полный total/колода, чужие кошельки/ID; после leave stale queued event не раскрывается, reconnect возвращает только разрешённую проекцию.
- [ ] Запустить все новые server/timer tests и существующие `test_holdem_timer.py`, `test_room_service.py`, `test_api_routes.py`.
- [ ] Commit `feat(blackjack): recover shared table turns and deadlines`.

### Task 4: Выбор режима и стол GFL на трёх игроков

**Files:** Create `apps/miniapp/src/lib/api/blackjack-table.ts`, `.test.ts`, `apps/miniapp/src/lib/rooms/BlackjackTableRoom.svelte`; Modify `apps/miniapp/src/routes/+page.svelte`, `apps/miniapp/src/lib/api/client.ts`; Test `apps/miniapp/tests/e2e/blackjack-table.spec.ts`.

**Interfaces:**
- Consumes snapshot/verbs Task 2–3 и текущие auth, RoomState, WS transport.
- Produces `parseBlackjackTable(snapshot: RoomSnapshot): BlackjackTableView | null` с типизированными players/dealer/phase/viewerSeat/activeSeat/deadline/legalActions; данные только из проверенного snapshot.
- UI «С ботом» / «Общий стол», «Создать стол» / «Войти по коду», ready/start/leave. Не генерирует сетевые outcomes и чужие действия.

- [ ] Написать parser+browser красные тесты: solo сохраняется, table mode создаёт новый режим; DEMO не отправляет table запрос и объясняет требование сервера; старый API даёт понятную ошибку с возвратом к выбору.
- [ ] Реализовать parser и selection, online create/join и отдельную TableRoom с текущими GFL картами/дилером. Существующую BlackjackRoom использовать для solo без изменения правил.
- [ ] Добавить tests: только active viewer получает Hit/Stand/Double; countdown не вызывает игровое действие; waiting участник видит ожидание следующей раздачи; результат персональный; Ready сбрасывается для новой раздачи.
- [ ] Проверить 320/390/1440px, safe area, кнопки 44px, reduced motion, клавиатуру/фокус. Руки всех игроков не перекрывают действия и друг друга.
- [ ] Добавить 3 browser contexts через реальный тестовый API: create/join/ready/start/ходы/итоги; 4-й отказ; потеря WS+resync не повторяет ставку/звук. Mocked UI tests не заменяют этот сценарий.
- [ ] `pnpm miniapp:check`, `pnpm miniapp:test`, `pnpm miniapp:build`, `pnpm miniapp:e2e`; старые solo/sound/holdem regressions должны пройти.
- [ ] Commit `feat(miniapp): add separate blackjack shared table mode`.

### Task 5: Интеграция и передача на приёмку

**Files:** Modify `dev/BuildSpec.md`, `dev/ProjectLog.md`, `ChangeLog.md`, `docs/Manual-QA-Checklist.md`, `README.md`.

- [ ] Сверить spec построчно с реализацией и отметить фактические checks, ограничения и совместимость старых solo-комнат; не писать «проверено» для непройденного Telegram теста.
- [ ] Полный `uv run --locked ruff check .` и `uv run --locked pytest -q` с PostgreSQL/Redis; Docker Compose build и весь CI на текущем head. Ошибки не скрывать skips.
- [ ] Проверить ledger invariant: сумма балансов=сумме проводок; повтор/рестарт не меняют суммы; disconnected seats рассчитаны, чужие данные отсутствуют в HTTP/WS/logs.
- [ ] Независимое review ветки с фокусом на wallet lock order, payouts, expiry и приватность. Закрыть блокирующие замечания.
- [ ] Передать draft PR с evidence и ручным сценарием на три Telegram-аккаунта. Merge/Pages/server deploy только отдельным разрешённым действием.
