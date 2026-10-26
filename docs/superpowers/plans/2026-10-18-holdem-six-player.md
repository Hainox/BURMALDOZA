# Hold’em Six Player Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить серверный Hold’em PvP на 2–6 реальных игроков, сохранив бот и старые комнаты.

**Architecture:** Новый чистый engine `holdem_multiway` и `holdem_pots`, versioned service `holdem_table_service`, отдельные TS parser/renderer. Создание явно opt-in через capacity6; дальнейший dispatch только по сохранённому ruleset, старый путь не переинтерпретируется.

**Tech Stack:** Python>=3.12, dataclasses, Pydantic, FastAPI, SQLAlchemy/PostgreSQL, pytest/Hypothesis; SvelteKit/TypeScript, Vitest/Playwright; существующие RNG/WalletService/EventBus.

**Spec:** `docs/superpowers/specs/2026-10-18-holdem-six-player-design.md`.

Статус: подготовлен по поручению владельца, **не выполняется**. Шесть мест и сохранение бота уже поручены; правила ожидания/рейзов/раскрытия в spec — предложения для review. Issue #118. База исследования `5075426`; перед реализацией актуализировать base и принятое дополнение BuildSpec. Исполнение, commits и публикация кода в текущую документационную задачу не входят.

## Global Constraints

- Новый ruleset: `holdem-six-1`, только `mode=pvp`, capacity=6.
- Сохраняются входы 100 / 500 / 1 000 JG и блайнды 5/10, 25/50, 50/100 JG.
- Поиск длится максимум 60 секунд с первого участника.
- За ход даётся 20 секунд. Сервер делает чек, если возможно, иначе пас.
- Одна комната по-прежнему содержит одну раздачу; повторная игра — новый вход.
- Полная колода/hole cards/entry balances/tombstones — только private JSON.
- Domain state_version приватен, wire optimistic lock использует только GameRoom.state_version.
- Никаких новых runtime dependencies; ledger только через WalletService; боевой RNG только SystemRandomSource; API один worker/replica.
- Один implementer на общий файл с Blackjack; merge/Pages/server deploy не входят в план реализации.

## Review Focus

- Несколько коротких all-in: повторный рейз открывается только при достижении полного прироста — тест Task1.
- Пустые физические места после cancel: seat не индекс массива, порядок и avatar target сохраняются — Tasks1/2/4.
- Позднее событие после showdown: folded/ранние карты остаются закрыты — Task3.
- Отмена одного участника против одновременного старта: ни частичного списания, ни отмены чужой игры — Task2.
- Старый pending intent/creation без capacity после обновления: v1/bot replay и восстановление работают — Tasks3/4.

---

### Task 1: Чистый multiway engine и расчёт банков

**Files:** Create `packages/domain/src/burmaldoza_domain/games/holdem_multiway.py`, `packages/domain/src/burmaldoza_domain/games/holdem_pots.py`, `tests/unit/domain/test_holdem_multiway.py`, `tests/unit/domain/test_holdem_pots.py`. Read-only reuse `holdem.py` evaluator/Card/RNG.

**Interfaces:** `MultiwayRules(small_blind:int,big_blind:int,ruleset_version:str="holdem-six-1")`; frozen `MultiwayPlayer(seat,stack,committed,street_committed,folded,acted_to_bet:int|None,acted_on_full_bet:bool)`; `MultiwayState(players:tuple[MultiwayPlayer,...], hole_cards:tuple[tuple[int,tuple[Card,Card]],...], button_seat,small_blind_seat,big_blind_seat,current_seat:int|None,phase:HoldemPhase,current_bet,last_full_raise_size,pending_seats:tuple[int,...],community_cards,deck,state_version,ruleset_version)`; pot computed from committed. All seat lookups by ID.

Produces `create_multiway_hand(stacks:tuple[tuple[int,int],...],button_seat:int,rng:RandomSource,rules:MultiwayRules)->MultiwayState`; `legal_multiway_actions(state,seat:int,rules)->tuple[str,...]`; `multiway_raise_bounds(state,seat:int,rules)->tuple[int|None,int]` (minimum legal full raise, stack maximum; short-all-in availability represented by legal raise and max<min); `apply_multiway_action(state,seat:int,action:HoldemAction,rules)->MultiwayTransition`; `settle_multiway(state)->MultiwaySettlement(pots:tuple[PotAward,...],refunds:tuple[tuple[int,int],...],awards:tuple[tuple[int,int],...])`, `PotAward(amount:int,eligible_seats:tuple[int,...],winner_seats:tuple[int,...],shares:tuple[tuple[int,int],...])`. Rules immutable; action RNG not needed after initial shuffle. Transition carries state+optional settlement.

- [ ] **Red:** Parametrize n=2..6: button0; HU SB0/BB1/pre0/post1; n>=3 SB1/BB2/pre next after2/post1. Sparse seats(0,2,5): SB2/BB5/pre0/post2. After first of six folds, phase still preflop. Assert BB option after all limps; skip folded/all-in; lone debtor must respond, lone matched actor triggers runout.
- [ ] **Red:** Tests `test_full_raise_tracks_increment` (10→30, min50), `test_short_all_in_does_not_reopen` (acted50,last_increment40,current60: no raise), `test_cumulative_short_all_ins_reopen` (current90: raise allowed,min130), `test_short_open_can_complete_to_big_blind` (all-in4,BB10: min10). Include never-acted seat, checked-before-opening seat, short-call min(stack,to_call), insufficient/noninteger/negative amount, wrong turn/version, terminal action refusal.
- [ ] **Red:** Pot fixture committed(100,60,20), ranked2>1>0: refunds={0:40}, awards={1:80,2:60}; folded1 makes side80 go0. Tie pot15 among seats0/2,button0: shares0=7,2=8; repeat odd chips independently per bank. Add six-way tie, board-playing tie, all-fold-to-one, unmatched raise refund. Hypothesis legal action sequences preserve sum(stack+committed), unique cards, and terminate within a bounded generated scenario or still expose a legal actor.
- [ ] Run `uv run --locked pytest -q tests/unit/domain/test_holdem_multiway.py tests/unit/domain/test_holdem_pots.py` — expected red missing interfaces/assertions before implementation.
- [ ] Implement exact interfaces and spec algorithms; validate2–6 unique seats0..5, starting stack>=2BB, positive blinds, per-seat tracking. Unequal-stack fixtures are domain-only; LIVE remains equal entry stacks. Reuse existing hand evaluator without modifying HU rules.
- [ ] Run same tests plus `uv run --locked pytest -q tests/unit/domain/test_holdem.py tests/unit/domain/test_holdem_bot.py tests/unit/domain/test_holdem_monte_carlo.py` — all pass; targeted Ruff clean. Commit domain-only slice after passing.

### Task 2: Новый lifecycle/очередь/ledger с PostgreSQL гонками

**Files:** Create `apps/api/app/services/holdem_table_service.py`, `tests/unit/test_holdem_table_service.py`, `tests/integration/test_holdem_table_concurrency.py`. Shared edits to legacy `apps/api/app/services/holdem_service.py` only for cross-version active/search guard and timeout partition; coordinate before writing. Existing models require no migration.

**Interfaces:** `HoldemTableService(rooms:RoomService)`; `create(user_id:int,buy_in:int,action_id:UUID)->RoomSnapshot`; `apply(room_id:UUID,user_id:int,request:ActionRequest)->EventEnvelope`; `expire_due()->int`; `project_snapshot(room:GameRoom,user_id:int)->RoomSnapshot`; `project_event(room:GameRoom,event:EventEnvelope,user_id:int)->EventEnvelope`; `history(user_id:int,limit:int,offset:int)->list[dict[str,Any]]`. `encode_multiway_state(state)->dict[str,Any]`, `decode_multiway_state(raw)->MultiwayState`, schema_version1. This task creates minimal projections; Task3 hardens/routes them.

- [ ] **Red:** `test_lobby_starts_at_six_or_deadline`: six arrivals same buy-in join one room;6th starts; deadline2..5 starts; lone cancels, no stake; new join never extends60s. Different buy-in/version never mix;7th joins a new room. Same user rejected from second waiting/active PvP across v1/v2.
- [ ] **Red:** `test_cancel_only_self_and_replay_after_membership_removal`: cancel frees seat; others remain waiting; retry same ID returns same owner-bound cancelled receipt; original create retry returns cancelled receipt; new ID can search; former member GET403/history empty, WS ends. Last cancel closes room. Sparse seats restart/decode intact.
- [ ] **Red:** `test_start_rechecks_all_balances_atomically`: remove insolvent waiting member; start remaining>=2 only at full/deadline, otherwise wait unchanged deadline; zero partial stakes. `test_multiway_payout_conserves_entries_and_replays`: six stakes and<=6 payouts, sum payouts=6*buy_in; result cashout=stack+award+refund; history stores maps per seat, only actual participants.
- [ ] **Red PostgreSQL:** Disable process gate as existing concurrency suite does; independent sessions race six joins+7th, duplicate create, cancel vs6th join, exact-deadline start vs join, action vs timeout, duplicate final settlement. Assert unique room-seat/user, one GameRound, one accepted action per action_id/version, one stake/payout per user; collision on sixth derived wallet key rolls back preceding five. Restart timer/service preserves deadline and replay.
- [ ] Run unit file and integration file with `TEST_DATABASE_URL` — expected red; no integration skip counts as evidence for concurrency.
- [ ] Implement FIFO matching, original deadline, start/revalidate, sparse membership, owner-bound cancel tombstones/replay, immutable start roster, room→sorted wallets lock order under existing queue gates. Stake/payout UUIDs derived room/purpose/user; verify replay operation identity. Transactions persist round/state/action/ledger together, publish after commit. v1 `expire_due` filters out six ruleset; v2 handles only six.
- [ ] Run new tests plus `tests/unit/test_holdem_server.py`, `tests/integration/test_holdem_concurrency.py` and Ruff — pass, inspect ledger invariants. Commit server slice after passing.

### Task 3: Общий контракт/dispatch, privacy, timers и avatars

**Files:** Modify `packages/contracts/src/burmaldoza_contracts/rooms.py`, `apps/api/app/services/room_service.py`, `apps/api/app/routers/rooms.py`, `apps/api/app/main.py`, `apps/api/app/services/holdem_table_service.py`, `apps/api/app/services/holdem_service.py` (history version branch), `tests/unit/test_contracts.py`, `tests/unit/test_holdem_timer.py`; create `tests/unit/test_holdem_table_api.py`. Shared-file integration window only, after Blackjack contract slice is rebased.

**Interfaces:** optional `RoomCreateRequest.table_capacity:Literal[6]|None=None`, valid only holdem+pvp; thread keyword `table_capacity` through `RoomService.create_room(...,table_capacity:int|None=None)` default unchanged. Explicit6 calls new create; snapshot/action/event/history dispatch by persisted ruleset; unknown version controlled error. Keep history endpoint pagination global across v1/v2 before mapping, never paginate each version then concatenate. `/rulesets/holdem/holdem-six-1` exposes six/new rules; old version metadata intact. New avatar `GET /rooms/{room_id}/players/{seat}/avatar`, authenticated member, seat0..5 target from room only; reuse AvatarService.

- [ ] **Red:** Contract accepts holdem+pvp+6; rejects bool/3/7, bot+6, blackjack+6 and unexpected fields; old omitted-capacity requests and persisted create receipts replay unchanged. Assert unknown ruleset cannot hit either decoder. Unified history mix v1/v2 returns correctly ordered offset/limit and each viewer's maps.
- [ ] **Red:** Six authenticated clients HTTP+WS receive only own cards/balance/legal actions. Folded cards stay hidden on showdown; fold win reveals none; project stored pre-showdown event after settlement: `revealed_seats=[]`, all other hands hidden. Inspect persisted GameAction and shared bus recursively for deck/hole_cards/wallet_balance/profile/Telegram identifiers; absent. Nonmember/departed API/WS/avatars denied before cache/source. Loop every avatar target, reject seat outside roster/arbitrary user/URL, fallback204 does not block actions.
- [ ] **Red:** Tick dispatch processes due v1/v2 once each; one broken room does not prevent another; action at exact expiry rejected; timeout stale version/deadline rechecked under lock; HTTP409 includes own personalized snapshot. No wrong decoder receives v2. Cancel/start race replay does not grant departed user cards of replacement seat.
- [ ] Run `uv run --locked pytest -q tests/unit/test_contracts.py tests/unit/test_holdem_table_api.py tests/unit/test_holdem_timer.py` — expected red before wiring.
- [ ] Implement spec public player/result shape and per-event revealed seats; transient profiles with allowlisted relative seat-avatar paths. Route new service, ruleset metadata/history, two partitioned timer calls under existing resilient loop. Preserve membership-before-cache and auth/rate-limit behavior of neighboring routes; no generic user lookup endpoint.
- [ ] Run tests above plus legacy `tests/unit/test_holdem_server.py`, full room service/resync suites and actual PostgreSQL concurrency suites — pass. Commit integrated contract/API slice after passing.

### Task 4: Multiway parser/UI, восстановление и legacy regression

**Files:** Create `apps/miniapp/src/lib/api/holdem-table.ts`, `apps/miniapp/src/lib/api/holdem-table.test.ts`, `apps/miniapp/src/lib/components/holdem/MultiplayerTable.svelte`, `apps/miniapp/src/lib/components/holdem/PlayerSeat.svelte`, `apps/miniapp/tests/e2e/holdem-table.spec.ts`; modify `apps/miniapp/src/lib/rooms/PokerRoom.svelte`; legacy `HandTable.svelte`/parser remain unchanged. `+page.svelte` only through integrator if a verified new interface needs it; none planned.

**Interfaces:** `parseHoldemTable(p:Record<string,unknown>)->HoldemTableView`; view has `players:HoldemTablePlayer[]` keyed seat, viewerSeat, phase/capacity/buyIn, button/SB/BB/currentSeat nullable, board/own, legal, minRaiseTo nullable/maxRaiseTo/toCall, deadlines, own balance, result pots/refunds/cashouts/netDeltas maps. `createHoldemTable(client:ApiClient,buyIn:number,actionId:string)->Promise<RoomSnapshot>` sends capacity6. MultiplayerTable props `{view,roomId,busy,seconds,live,reducedMotion,onAction}`; PlayerSeat consumes one player+viewer/current/blind markers. Public result fields/allowed paths match Task3 exactly; strict validation at boundary.

- [ ] **Red Vitest:** Parse2/3/6 and sparse0/2/5, waiting1; reject duplicate/out-of-range seat, unsafe sums, result keys missing/foreign seats, illegal current seat, malformed cards/paths/bounds. Assert mixed bank winners are not inferred as global tie. Legacy parser still accepts old snapshots; new unknown payload cannot fall through to demo.
- [ ] **Red Playwright:** LIVE mocked six seats all visible with own controls, button/blinds and one timer; partial all-in/call/reopening restrictions use server legal/bounds. Test waiting counter/60s/cancel-self,2-player deadline start, side-pot result/refund, delayed event,409 resync/retry same ID, refresh active/settled, out-of-order events. Avatars load independently and403 stops departed stream.
- [ ] Run `pnpm miniapp:test` and targeted `pnpm --dir apps/miniapp exec playwright test tests/e2e/holdem-table.spec.ts` — expected red before UI implementation.
- [ ] Implement optional six-seat create only for live PvP, version-aware accept/restore/session storage, server-rendered status/actions, array-by-ID seats. Preserve bot/legacy renderer and audio lifecycle. 320px compact opponent list avoids overlap; touch>=44px, safe areas, focus, reduced motion; no autoplay/replayed settled win. DEMO remains clearly preview-only.
- [ ] Run `pnpm miniapp:check`, `pnpm miniapp:test`, `pnpm miniapp:build`, new E2E and existing `holdem-room.spec.ts`, `sound.spec.ts`, `reconnect.spec.ts` at320/390/1440; pass. Commit UI slice after passing; CCode UI handoff follows stable API contract and exact allowlist.

### Task 5: Системная приёмка и последовательная интеграция

**Files:** After owner acceptance only: `dev/BuildSpec.md` (accepted additive rules), `dev/ProjectLog.md`, `ChangeLog.md` (English Unreleased), `docs/Manual-QA-Checklist.md`. Integration fixes stay within Tasks1–4 file lists, single writer per file.

**Interfaces:** No new public API; release evidence must name exact tested commit, environment, skipped checks and six-session manual result. Existing v1 rules and bot Monte Carlo seeded outputs remain untouched unless a reproducible regression requires a separately approved rules change.

- [ ] Before implementation record accepted spec/plan and updated base in #118; coordinate #119 Blackjack: **shared contract → shared RoomService/router/timer integration → game-local backend → frozen API/UI → shared root-route/history integration → combined regression**. Game-local pure engines may proceed independently; shared-file changes are serialized under one integrator, with rebase between slices. Do not auto-merge plans or code.
- [ ] Run `uv run --locked ruff check .`, `uv run --locked pytest -q` with real PostgreSQL/Redis, `pnpm miniapp:check`, `pnpm miniapp:test`, `pnpm miniapp:build`, `pnpm miniapp:e2e`; CI additionally `docker compose build api bot miniapp` and existing seeded Monte Carlo commands from README. All green or report exact unavailable gate without claiming completion.
- [ ] Independent read-only review: full/short raises, pot/refund examples, event-at-version privacy, cancel tombstone seat replacement, locking/idempotency, v1/bot+Blackjack backwards compatibility. Fix findings through failing regression then rerun affected checks.
- [ ] Manual staging:6 authenticated Telegram sessions complete search→blinds→all streets→settlement, plus2/3 actual participants at deadline, disconnect/reconnect, expired turn, folded privacy, new search. Repeat existing bot/heads-up cycle and Blackjack independently; record iOS/Android/Desktop observations and outstanding limits.
- [ ] Commit final accepted docs/evidence; give reviewable branch/diff/check report. Merge, GitHub Pages publication and production deployment remain separate authorized actions.
