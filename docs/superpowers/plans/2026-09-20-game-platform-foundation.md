# Game Platform Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Build a tested server-authoritative foundation for the Jokergem virtual economy and three animated Telegram Mini App rooms: 3×7 slot, Blackjack GFL, and heads-up Texas Hold’em / RGG Poker.

**Architecture:** Keep the existing repository as a modular monolith: aiogram owns Telegram commands, FastAPI owns authentication/API/room orchestration, packages/domain owns pure game rules, PostgreSQL owns durable state and the append-only ledger, Redis owns locks/presence/pub-sub, and SvelteKit owns presentation plus motion. The Pages demo remains a deterministic presentation pilot and is not connected to production state.

**Tech Stack:** Python 3.12, aiogram 3, FastAPI, Pydantic Settings, SQLAlchemy 2 async, asyncpg, Alembic, PostgreSQL 16, Redis 7, SvelteKit 2, Svelte 5, TypeScript, Vite, adapter-static, CSS/SVG/Web Animations API, pytest, pytest-asyncio, httpx, Hypothesis, Ruff, Vitest, Playwright, uv, pnpm and Docker Compose.

**Spec:** docs/superpowers/specs/2026-09-20-game-platform-design.md

## Global Constraints

- Python runtime remains >=3.12 and the production database is PostgreSQL 16.
- Jokergem is the provisional display name; code stores integer balances and a configurable currency_code, so a rename does not require a balance migration.
- v1 has no real-money payments, Stars purchases, withdrawals, prizes, exchange or direct wallet transfers.
- The client sends intents and renders confirmed server state; it never generates an outcome or decides a payout.
- Production game randomness uses an OS-backed CSPRNG; seeded pseudo-randomness is limited to offline simulation and deterministic tests.
- Every balance mutation has an idempotency key and is committed with its related round in one database transaction.
- initDataUnsafe is never a trust boundary; raw Telegram.WebApp.initData is verified by the API.
- The first skeleton has no final character art or thematic asset pack; visual assets are added only after domain and room tests pass.
- The existing Pages pilot remains explicitly local, deterministic and non-production.
- All changes land on codex/platform-foundation-spec or a descendant feature branch; main is never force-pushed.
- Bot tokens, passwords, raw Telegram init data and full personal identifiers never enter source, tests, fixtures, logs or commits.

## Review Focus

- A repeated tap, retry or two-tab race must produce one settlement and one ledger effect; covered by tests/integration/test_idempotency.py and tests/integration/test_concurrent_wallet.py in Task 6.
- An expired or tampered Telegram payload must be rejected before a user or wallet context is created; covered by tests/unit/test_telegram_auth.py in Task 7.
- Integer payout rounding and a tied poker pot must never create or destroy Jokergem; covered by tests/unit/domain/test_holdem.py and tests/unit/test_wallet_service.py in Tasks 5 and 6.
- A WebSocket disconnect during a room animation must recover through a snapshot without duplicating a game action; covered by tests/integration/test_room_resync.py and apps/miniapp/tests/e2e/reconnect.spec.ts in Tasks 7 and 9.
- Reduced-motion and narrow safe-area layouts must preserve legal actions, result explanation and readable static states; covered by apps/miniapp/src/lib/game/motion.test.ts and apps/miniapp/tests/e2e/accessibility.spec.ts in Task 9.

---

### Task 1: Lock the dependency and quality baseline

**Files:**

- Modify: pyproject.toml
- Modify: apps/miniapp/package.json
- Modify: package.json
- Modify: pnpm-lock.yaml
- Modify: uv.lock
- Create: apps/miniapp/vitest.config.ts
- Create: apps/miniapp/playwright.config.ts
- Create: tests/unit/test_dependency_surface.py

**Interfaces:**

- Produces the commands uv run --locked pytest -q, uv run --locked ruff check ., pnpm miniapp:check, pnpm miniapp:test, pnpm miniapp:build and pnpm miniapp:e2e for every later task.
- Keeps the existing tests/unit/test_api_health.py green before application behavior changes.

- [ ] **Step 1: Add the smallest required dependency set**

Add alembic>=1.16,<2 to runtime dependencies. Add aiosqlite>=0.21,<1, hypothesis>=6.140,<7 and pytest-cov>=6.2,<7 to the Python development group. Add vitest and @playwright/test as Mini App development dependencies. Do not add a Telegram SDK or animation framework; the implementation uses the official WebApp bridge and browser APIs.

- [ ] **Step 2: Add the shared verification scripts**

Extend the root package.json with these scripts:

    "test:py": "uv run --locked pytest -q",
    "lint:py": "uv run --locked ruff check .",
    "miniapp:test": "pnpm --dir apps/miniapp exec vitest run",
    "miniapp:e2e": "pnpm --dir apps/miniapp exec playwright test",
    "verify": "pnpm miniapp:check && pnpm miniapp:test && pnpm miniapp:build"

Add matching scripts to apps/miniapp/package.json, keeping check and build unchanged.

- [ ] **Step 3: Write the import-surface smoke test**

Create tests/unit/test_dependency_surface.py:

    def test_required_runtime_imports_are_available() -> None:
        import alembic
        import fastapi
        import hypothesis
        import sqlalchemy

        assert alembic.__version__
        assert fastapi.__version__
        assert hypothesis.__version__
        assert sqlalchemy.__version__

- [ ] **Step 4: Install and lock dependencies**

Run:

    uv sync --dev
    pnpm install --frozen-lockfile=false
    uv run --locked pytest tests/unit/test_dependency_surface.py -q

Expected: the smoke test passes and both lockfiles contain the selected dependency graph.

- [ ] **Step 5: Run the pre-feature baseline**

Run:

    uv run --locked pytest -q
    uv run --locked ruff check .
    pnpm miniapp:check
    pnpm miniapp:test
    pnpm miniapp:build

Expected: the existing health test and the new smoke test pass, Ruff is clean, and the static Mini App builds.

- [ ] **Step 6: Commit the baseline**

    git add pyproject.toml uv.lock package.json pnpm-lock.yaml apps/miniapp/package.json apps/miniapp/vitest.config.ts apps/miniapp/playwright.config.ts tests/unit/test_dependency_surface.py
    git commit -m "build: lock game platform test dependencies"

### Task 2: Create pure contracts, RNG and economy primitives

**Files:**

- Create: packages/domain/src/burmaldoza_domain/core.py
- Create: packages/domain/src/burmaldoza_domain/rng.py
- Create: packages/domain/src/burmaldoza_domain/economy.py
- Modify: packages/domain/src/burmaldoza_domain/__init__.py
- Create: packages/contracts/src/burmaldoza_contracts/common.py
- Create: packages/contracts/src/burmaldoza_contracts/rooms.py
- Create: packages/contracts/src/burmaldoza_contracts/wallet.py
- Create: packages/contracts/src/burmaldoza_contracts/events.py
- Create: tests/unit/domain/test_rng.py
- Create: tests/unit/domain/test_economy.py
- Create: tests/unit/test_contracts.py

**Interfaces:**

- burmaldoza_domain.rng.RandomSource exposes randbelow(upper: int) -> int, choice(sequence: Sequence[T]) -> T and shuffle(values: MutableSequence[T]) -> None.
- burmaldoza_domain.rng.SystemRandomSource is the production implementation; SeededRandomSource(seed: int) is the deterministic test implementation.
- burmaldoza_domain.economy.CURRENCY_CODE is "JOKERGEM"; EconomyConfig contains welcome_grant=1000, daily_bonus=250, relief_grant=300, relief_threshold=50, daily_cooldown_seconds=86400 and relief_cooldown_seconds=259200.
- burmaldoza_domain.economy.LedgerReason contains WELCOME, DAILY_BONUS, RELIEF, GAME_STAKE, GAME_PAYOUT and ADMIN_ADJUSTMENT.
- burmaldoza_contracts.common.GameType contains SLOT, BLACKJACK and HOLDEM; RoomStatus contains WAITING, ACTIVE, SETTLED and CLOSED.
- burmaldoza_contracts.rooms.ActionRequest contains action_id: UUID, expected_state_version: int and payload: dict[str, Any].
- burmaldoza_contracts.events.EventEnvelope contains event_id, room_id, state_version, type, ruleset_version, server_time, payload and animation_hint.

- [ ] **Step 1: Write RNG contract tests**

Create tests that assert a seeded source produces the same sequence for the same seed, rejects randbelow(0), and never returns a value outside [0, upper).

    def test_seeded_source_is_reproducible() -> None:
        first = SeededRandomSource(42)
        second = SeededRandomSource(42)

        assert [first.randbelow(100) for _ in range(8)] == [
            second.randbelow(100) for _ in range(8)
        ]

- [ ] **Step 2: Run the RNG tests and confirm the expected failure**

Run uv run --locked pytest tests/unit/domain/test_rng.py -q. Expected: collection fails because burmaldoza_domain.rng does not exist yet.

- [ ] **Step 3: Implement the RNG adapters**

Use secrets.SystemRandom for SystemRandomSource and random.Random(seed) only inside SeededRandomSource. Keep the domain dependent on the RandomSource protocol rather than either concrete generator.

- [ ] **Step 4: Write economy and contract tests**

Cover non-negative balance validation, exact integer deltas, starter grant values, cooldown values, invalid enum values and serialization of an action request/event envelope.

    def test_jokergem_config_is_provisional_but_stable() -> None:
        assert CURRENCY_CODE == "JOKERGEM"
        assert EconomyConfig().welcome_grant == 1000
        assert EconomyConfig().daily_bonus == 250

- [ ] **Step 5: Implement the pure economy and Pydantic contracts**

Implement validate_wallet_delta(balance: int, delta: int) -> int, validate_bet(balance: int, amount: int, minimum: int, maximum: int) -> int and immutable config objects. Pydantic contracts reject a negative expected_state_version, an empty action_id and an unknown GameType.

- [ ] **Step 6: Run focused and full checks**

    uv run --locked pytest tests/unit/domain tests/unit/test_contracts.py -q
    uv run --locked ruff check packages tests

Expected: all focused tests pass without importing FastAPI, SQLAlchemy or Telegram from the domain package.

- [ ] **Step 7: Commit the pure foundation**

    git add packages/domain packages/contracts tests/unit/domain tests/unit/test_contracts.py
    git commit -m "feat: add domain contracts rng and jokergem economy"

### Task 3: Implement the 3×7 slot domain and Monte Carlo runner

**Files:**

- Create: packages/domain/src/burmaldoza_domain/games/__init__.py
- Create: packages/domain/src/burmaldoza_domain/games/slot.py
- Create: packages/domain/src/burmaldoza_domain/games/slot_ruleset.py
- Create: devtools/__init__.py
- Create: devtools/monte_carlo/__init__.py
- Create: devtools/monte_carlo/slot.py
- Create: tests/unit/domain/test_slot.py
- Create: tests/unit/domain/test_slot_monte_carlo.py
- Create: tests/fixtures/slot_skeleton.json

**Interfaces:**

- SlotConfig(columns: int, rows: int, reel_strips: tuple[tuple[str, ...], ...], paylines: tuple[tuple[int, ...], ...], paytable: Mapping[tuple[str, int], int], wild_symbol: str | None).
- SlotOutcome(grid: tuple[tuple[str, ...], ...], winning_lines: tuple[WinningLine, ...], gross_payout: int, net_delta: int, ruleset_version: str).
- spin(config: SlotConfig, bet: int, active_paylines: tuple[int, ...], rng: RandomSource) -> SlotOutcome.
- calculate_payout(config: SlotConfig, grid: tuple[tuple[str, ...], ...], bet: int, active_paylines: tuple[int, ...]) -> tuple[WinningLine, ...].
- run_slot_simulation(config: SlotConfig, trials: int, bet: int, seed: int) -> SlotSimulationReport.

- [ ] **Step 1: Add a deterministic skeleton fixture**

Create tests/fixtures/slot_skeleton.json with exactly three reel strips, seven visible rows, three legal sample paylines and integer payouts. The fixture uses neutral symbols A, B, C and W and ruleset_version slot-skeleton-1; it contains no final theme or character art.

- [ ] **Step 2: Write failing geometry and payout tests**

Add tests for a 3 × 7 returned grid, invalid bet/line rejection, left-to-right line matching, wild substitution, no payout for a non-consecutive line and exact gross_payout/net_delta values.

    def test_spin_returns_three_reels_with_seven_visible_rows() -> None:
        outcome = spin(load_skeleton_config(), 10, (0, 1, 2), SeededRandomSource(7))

        assert len(outcome.grid) == 3
        assert all(len(reel) == 7 for reel in outcome.grid)
        assert outcome.ruleset_version == "slot-skeleton-1"

- [ ] **Step 3: Run the focused slot tests and confirm failure**

Run uv run --locked pytest tests/unit/domain/test_slot.py -q. Expected: collection fails because the slot module and load_skeleton_config do not exist.

- [ ] **Step 4: Implement the immutable slot ruleset and outcome calculator**

Select one stop per reel with the injected RNG, produce a full seven-row view, evaluate only active paylines, apply wild rules from config, and return integer gross payout plus net delta. Do not use random, current time or client-provided symbols.

- [ ] **Step 5: Add deterministic Monte Carlo reporting**

Implement python -m devtools.monte_carlo.slot --trials 100000 --bet 10 --seed 42 --json. The JSON report includes trials, seed, ruleset_version, rtp, hit_rate, variance, p5_ending_bankroll, p50_ending_bankroll, p95_ending_bankroll and max_drawdown.

- [ ] **Step 6: Write and run statistical tests**

Use a fixed seed and 100,000 trials to assert the report is reproducible. Add an exact fixture for the expected mean payout and a confidence-bound test that fails if RTP leaves the configured skeleton interval. The test states the interval and sample size instead of relying on a vague “reasonable” result.

Run:

    uv run --locked pytest tests/unit/domain/test_slot.py tests/unit/domain/test_slot_monte_carlo.py -q
    python -m devtools.monte_carlo.slot --trials 100000 --bet 10 --seed 42 --json

- [ ] **Step 7: Commit the slot domain**

    git add packages/domain/src/burmaldoza_domain/games devtools tests/unit/domain/test_slot.py tests/unit/domain/test_slot_monte_carlo.py tests/fixtures/slot_skeleton.json
    git commit -m "feat: add 3x7 slot domain and simulation"

### Task 4: Implement the Blackjack GFL domain

**Files:**

- Create: packages/domain/src/burmaldoza_domain/games/blackjack.py
- Create: devtools/monte_carlo/blackjack.py
- Create: tests/unit/domain/test_blackjack.py
- Create: tests/unit/domain/test_blackjack_monte_carlo.py

**Interfaces:**

- BlackjackAction is Literal["hit", "stand", "double"].
- BlackjackRules(blackjack_numerator=3, blackjack_denominator=2, dealer_stands_soft_17=True, allow_double=True).
- BlackjackState contains phase, bet, player_cards, dealer_cards, dealer_hole_hidden, player_total, dealer_total, state_version and ruleset_version.
- deal_initial(bet: int, rng: RandomSource, rules: BlackjackRules) -> BlackjackState.
- apply_action(state: BlackjackState, action: BlackjackAction, rng: RandomSource, rules: BlackjackRules) -> BlackjackTransition.
- settle_blackjack(state: BlackjackState, rules: BlackjackRules) -> BlackjackSettlement.

- [ ] **Step 1: Write card and hand-value fixtures**

Add fixtures for ace-low totals, blackjack, hard 21, bust, push, dealer soft 17 and a double-down hand.

- [ ] **Step 2: Write failing transition tests**

Assert that HIT adds exactly one card, STAND enters dealer resolution, DOUBLE doubles the stake and permits exactly one additional player card, and actions after settlement are rejected.

- [ ] **Step 3: Run the focused tests and confirm failure**

Run uv run --locked pytest tests/unit/domain/test_blackjack.py -q. Expected: collection fails because the Blackjack module is absent.

- [ ] **Step 4: Implement deck, hand evaluation and server-side transitions**

Use a 52-card deck per skeleton round, shuffle through the injected RandomSource, keep the dealer hole card only in private state, draw the dealer to the configured threshold, and calculate integer-safe payouts. The domain knows nothing about the bot, Mini App or database.

- [ ] **Step 5: Add strategy/outcome simulation**

Implement run_blackjack_simulation(trials: int, bet: int, seed: int, strategy: str) -> BlackjackSimulationReport with a fixed basic-hit-stand strategy for test reproducibility. Report win/push/loss rates, average net delta, variance and confidence interval.

- [ ] **Step 6: Run focused tests and simulation**

    uv run --locked pytest tests/unit/domain/test_blackjack.py tests/unit/domain/test_blackjack_monte_carlo.py -q
    python -m devtools.monte_carlo.blackjack --trials 100000 --bet 25 --seed 42 --json

Expected: all state transitions are deterministic under a seeded source and the simulation report is reproducible.

- [ ] **Step 7: Commit Blackjack**

    git add packages/domain/src/burmaldoza_domain/games/blackjack.py devtools/monte_carlo/blackjack.py tests/unit/domain/test_blackjack.py tests/unit/domain/test_blackjack_monte_carlo.py
    git commit -m "feat: add blackjack domain transitions"

### Task 5: Implement heads-up Texas Hold’em / RGG Poker domain

**Files:**

- Create: packages/domain/src/burmaldoza_domain/games/holdem.py
- Create: devtools/monte_carlo/holdem.py
- Create: tests/unit/domain/test_holdem.py
- Create: tests/unit/domain/test_holdem_monte_carlo.py

**Interfaces:**

- HoldemActionType contains FOLD, CHECK, CALL and RAISE.
- HoldemAction(kind: HoldemActionType, amount: int | None = None).
- HoldemRules(small_blind=10, big_blind=20, turn_timeout_seconds=30, max_players=2).
- create_heads_up_room(buy_in: int, rng: RandomSource, rules: HoldemRules) -> HoldemState.
- apply_holdem_action(state: HoldemState, seat: int, action: HoldemAction, rng: RandomSource, rules: HoldemRules) -> HoldemTransition.
- evaluate_best_hand(cards: Sequence[Card]) -> HandRank.
- settle_holdem(state: HoldemState) -> HoldemSettlement.

- [ ] **Step 1: Write evaluator fixtures**

Cover high card, pair, two pair, three of a kind, straight, flush, full house, four of a kind, straight flush, tie-breakers and equal-hand ties.

- [ ] **Step 2: Write failing room/action tests**

Assert button/blind rotation, legal action order, CHECK rejection when facing a bet, CALL amount, minimum RAISE, FOLD settlement, street transitions and no third seat.

- [ ] **Step 3: Run evaluator tests and confirm failure**

Run uv run --locked pytest tests/unit/domain/test_holdem.py -q. Expected: collection fails because the Hold’em module is absent.

- [ ] **Step 4: Implement deck, evaluator and two-seat state machine**

Shuffle one 52-card deck through the injected RNG, deal private/community cards only from server state, enforce one main pot and integer chip amounts, and return a new immutable state for every accepted action. Reject an action with an old state_version before changing the state.

- [ ] **Step 5: Implement deterministic equity simulation**

Implement run_holdem_simulation(hero_cards: tuple[Card, Card], villain_range: tuple[tuple[Card, Card], ...], board: tuple[Card, ...], trials: int, seed: int) -> HoldemSimulationReport. It samples unknown cards for analysis only and never runs in a production request path.

- [ ] **Step 6: Test tie splitting and simulation reproducibility**

Assert the sum of winner shares equals the pot, remainder chips follow the documented seat order, and the same seed produces the same report.

    uv run --locked pytest tests/unit/domain/test_holdem.py tests/unit/domain/test_holdem_monte_carlo.py -q
    python -m devtools.monte_carlo.holdem --trials 100000 --seed 42 --json

- [ ] **Step 7: Commit Hold’em**

    git add packages/domain/src/burmaldoza_domain/games/holdem.py devtools/monte_carlo/holdem.py tests/unit/domain/test_holdem.py tests/unit/domain/test_holdem_monte_carlo.py
    git commit -m "feat: add heads-up holdem domain"

### Task 6: Add PostgreSQL models, migrations and atomic Jokergem ledger

**Files:**

- Create: alembic.ini
- Create: migrations/env.py
- Create: migrations/script.py.mako
- Create: migrations/versions/20260920_0001_game_foundation.py
- Create: apps/api/app/core/config.py
- Create: apps/api/app/db/__init__.py
- Create: apps/api/app/db/session.py
- Create: apps/api/app/db/models/__init__.py
- Create: apps/api/app/db/models/identity.py
- Create: apps/api/app/db/models/economy.py
- Create: apps/api/app/db/models/games.py
- Create: apps/api/app/services/wallet_service.py
- Create: tests/unit/test_wallet_service.py
- Create: tests/integration/conftest.py
- Create: tests/integration/test_idempotency.py
- Create: tests/integration/test_concurrent_wallet.py

**Interfaces:**

- create_async_engine_from_settings(settings: Settings) -> AsyncEngine.
- get_session() -> AsyncIterator[AsyncSession].
- async WalletService.get_or_create(user_id: int) -> WalletSnapshot.
- async WalletService.apply_delta(user_id: int, delta: int, reason: LedgerReason, reference_id: UUID, idempotency_key: UUID) -> LedgerResult.
- async WalletService.claim_welcome_grant(user_id: int, idempotency_key: UUID) -> LedgerResult.
- async WalletService.claim_daily_bonus(user_id: int, now: datetime, idempotency_key: UUID) -> LedgerResult.
- async WalletService.claim_relief_grant(user_id: int, now: datetime, idempotency_key: UUID) -> LedgerResult.
- async WalletService.settle_game_round(user_id: int, round_id: UUID, stake: int, payout: int, idempotency_key: UUID) -> SettlementResult.

- [ ] **Step 1: Write wallet arithmetic unit tests**

Cover starter grant, daily cooldown, relief threshold, positive/negative integer deltas, insufficient balance and duplicate idempotency keys. Use a fake repository only for pure service arithmetic; database concurrency belongs to integration tests.

- [ ] **Step 2: Implement settings and SQLAlchemy models**

Create typed settings for DATABASE_URL, REDIS_URL, BOT_TOKEN, MINIAPP_URL, TELEGRAM_INIT_DATA_MAX_AGE_SECONDS and ENVIRONMENT. Define PostgreSQL integer checks for non-negative wallet balance, unique Telegram user ID, unique wallet_operations.idempotency_key, unique game_rounds.idempotency_key, unique room/sequence number and unique room/action ID.

- [ ] **Step 3: Create and inspect the first migration**

The migration creates users, communities, chat_settings, admin_roles, wallets, wallet_operations, ledger_entries, game_rooms, game_players, game_rounds, game_actions and admin_audit_log with UTC timestamps, foreign keys and the constraints above. wallet_operations owns idempotency; ledger_entries references operation_id and can contain both a stake debit and a payout credit for one settlement.

Run:

    uv run alembic upgrade head
    uv run alembic downgrade base
    uv run alembic upgrade head

Expected: upgrade/downgrade/upgrade completes without data-loss warnings in the disposable local database.

- [ ] **Step 4: Implement transaction-scoped wallet settlement**

Lock the wallet row, check or create one wallet_operation by idempotency key, insert its ledger entries, update wallets.balance and commit the round settlement in one AsyncSession.begin() block. A replay returns the previously stored LedgerResult; it never creates a second wallet_operation or second set of ledger entries.

- [ ] **Step 5: Add integration fixtures and concurrency tests**

Use TEST_DATABASE_URL against the Compose PostgreSQL service. The fixture creates an isolated schema per test session and truncates tables in dependency order after each test. Add a two-task concurrent spend test whose final balance equals the one valid settlement and never becomes negative.

- [ ] **Step 6: Run persistence checks**

    docker compose up -d postgres redis
    TEST_DATABASE_URL=postgresql+asyncpg://burmaldoza:local-test@localhost:5432/burmaldoza uv run --locked pytest tests/integration -q
    uv run --locked pytest tests/unit/test_wallet_service.py -q

Expected: duplicate and concurrent mutations pass; a missing Docker binary is reported as an environment blocker rather than hidden as a passing test.

- [ ] **Step 7: Commit persistence**

    git add alembic.ini migrations apps/api/app/core/config.py apps/api/app/db apps/api/app/services/wallet_service.py tests/unit/test_wallet_service.py tests/integration
    git commit -m "feat: add postgres ledger and atomic wallet service"

### Task 7: Implement Telegram auth, room orchestration and API/WebSocket contracts

**Files:**

- Create: apps/api/app/core/telegram_auth.py
- Create: apps/api/app/core/idempotency.py
- Create: apps/api/app/dependencies.py
- Create: apps/api/app/routers/auth.py
- Create: apps/api/app/routers/wallet.py
- Create: apps/api/app/routers/rooms.py
- Create: apps/api/app/services/room_service.py
- Create: apps/api/app/services/event_bus.py
- Modify: apps/api/app/main.py
- Create: tests/unit/test_telegram_auth.py
- Create: tests/unit/test_room_service.py
- Create: tests/integration/test_room_resync.py
- Modify: tests/unit/test_api_health.py

**Interfaces:**

- verify_telegram_init_data(raw: str, bot_token: str, now: datetime, max_age_seconds: int) -> TelegramAuthContext.
- get_current_user(request: Request, session: AsyncSession) -> CurrentUser.
- RoomService.create_room(user_id: int, game_type: GameType, mode: str) -> RoomSnapshot.
- RoomService.apply_action(room_id: UUID, user_id: int, request: ActionRequest) -> EventEnvelope.
- RoomService.snapshot(room_id: UUID, user_id: int) -> RoomSnapshot.
- RoomService.authenticate_websocket(first_message: WebSocketAuthMessage) -> CurrentUser.

- [ ] **Step 1: Write HMAC validation tests**

Create known valid Telegram fixtures without real user data. Test valid signature, altered hash, altered user, missing auth_date, expired auth_date, malformed query encoding and empty payload. Assertions verify no user context is returned on failure.

    def test_expired_init_data_is_rejected() -> None:
        with pytest.raises(TelegramAuthError, match="expired"):
            verify_telegram_init_data(EXPIRED_FIXTURE, "test-bot-token", NOW, 86400)

- [ ] **Step 2: Run auth tests and confirm failure**

Run uv run --locked pytest tests/unit/test_telegram_auth.py -q. Expected: collection fails because apps.api.app.core.telegram_auth does not exist.

- [ ] **Step 3: Implement raw initData verification**

Parse the raw query string without normalizing away duplicate keys, derive the Telegram data-check secret with HMAC-SHA-256, compare hashes with hmac.compare_digest, enforce auth_date freshness and return only the minimal internal user context. Never log the raw payload.

- [ ] **Step 4: Add route and room-service tests**

Test /health/live, /health/ready, /api/v1/auth/telegram, /api/v1/me, /api/v1/wallet, /api/v1/wallet/ledger, /api/v1/games, /api/v1/rooms and /api/v1/rooms/{room_id}/actions. Use httpx.AsyncClient with ASGITransport and dependency overrides; do not call Telegram or PostgreSQL in unit tests.

- [ ] **Step 5: Implement API routes and dependency boundaries**

Require X-Telegram-Init-Data on protected HTTP routes. The WebSocket accepts exactly one first message of the form {"type":"auth","init_data":"..."}, authenticates it, then emits ordered snapshots/events. POST /rooms/{room_id}/actions rejects an old expected_state_version with a current snapshot and does not call a game transition.

- [ ] **Step 6: Implement idempotent room actions and event publication**

Dispatch to the domain module based on GameType, call WalletService.settle_game_round for stake changes, persist game_actions and game_rounds, increment state_version once and publish one EventEnvelope. Redis pub/sub carries notifications only; the durable snapshot is read from PostgreSQL on resync.

- [ ] **Step 7: Test reconnect and duplicate action behavior**

Create an integration test that authenticates a room, applies one action, disconnects before the client receives the event, reconnects and requests a snapshot, then retries the same action_id. Assert one game action, one ledger settlement and the latest state version.

- [ ] **Step 8: Run API checks and commit**

    uv run --locked pytest tests/unit/test_telegram_auth.py tests/unit/test_room_service.py tests/unit/test_api_health.py -q
    uv run --locked ruff check apps/api packages tests
    git add apps/api tests/unit/test_telegram_auth.py tests/unit/test_room_service.py tests/unit/test_api_health.py tests/integration/test_room_resync.py
    git commit -m "feat: add telegram auth and room api"

### Task 8: Implement the aiogram bot entrypoint and safe command surface

**Files:**

- Create: apps/bot/app/bot.py
- Create: apps/bot/app/handlers/__init__.py
- Create: apps/bot/app/handlers/start.py
- Create: apps/bot/app/handlers/casino.py
- Create: apps/bot/app/handlers/help.py
- Modify: apps/bot/app/main.py
- Create: tests/unit/test_bot_config.py
- Create: tests/unit/test_bot_handlers.py

**Interfaces:**

- BotConfig gains token, miniapp_url, api_base_url and environment.
- create_bot(config: BotConfig) -> Bot.
- create_dispatcher(config: BotConfig) -> Dispatcher.
- Handlers expose /start, /help, /casino, /balance and /top with inline buttons; no handler writes to a chat without the triggering command or an explicit admin announcement action.

- [ ] **Step 1: Write configuration tests**

Cover missing BOT_TOKEN, missing MINIAPP_URL, missing API_BASE_URL, valid config and production refusal to start with an empty or placeholder URL.

- [ ] **Step 2: Implement bot factory and routers**

Use aiogram 3 router composition, a Mini App button pointing to MINIAPP_URL, and API calls through a small async client. Do not put a real token in test fixtures; use TEST_BOT_TOKEN only in process memory when testing config parsing.

- [ ] **Step 3: Write handler behavior tests**

Assert command text, button URL and that /casino returns a launch surface rather than pretending to settle a game in chat. /balance reads the API-backed balance; it does not maintain a second balance cache.

- [ ] **Step 4: Add the polling runner**

Implement async def run() -> None with Bot, Dispatcher, startup logging with redacted config and graceful shutdown. Keep webhook configuration outside this first local skeleton.

- [ ] **Step 5: Run bot checks and commit**

    uv run --locked pytest tests/unit/test_bot_config.py tests/unit/test_bot_handlers.py -q
    uv run --locked ruff check apps/bot
    git add apps/bot tests/unit/test_bot_config.py tests/unit/test_bot_handlers.py
    git commit -m "feat: add safe telegram bot command surface"

### Task 9: Build the Mini App shell and state-driven room motion

**Files:**

- Modify: apps/miniapp/src/app.html
- Modify: apps/miniapp/src/routes/+page.svelte
- Create: apps/miniapp/src/lib/telegram/webapp.ts
- Create: apps/miniapp/src/lib/api/client.ts
- Create: apps/miniapp/src/lib/state/session.svelte.ts
- Create: apps/miniapp/src/lib/state/room.svelte.ts
- Create: apps/miniapp/src/lib/game/motion.ts
- Create: apps/miniapp/src/lib/game/motion.test.ts
- Create: apps/miniapp/src/lib/components/BalancePill.svelte
- Create: apps/miniapp/src/lib/components/RoomCard.svelte
- Create: apps/miniapp/src/lib/components/RoomShell.svelte
- Create: apps/miniapp/src/lib/components/ResultBand.svelte
- Create: apps/miniapp/src/lib/rooms/SlotRoom.svelte
- Create: apps/miniapp/src/lib/rooms/BlackjackRoom.svelte
- Create: apps/miniapp/src/lib/rooms/PokerRoom.svelte
- Create: apps/miniapp/src/lib/styles/tokens.css
- Create: apps/miniapp/tests/e2e/accessibility.spec.ts
- Create: apps/miniapp/tests/e2e/reconnect.spec.ts

**Interfaces:**

- getTelegramWebApp(): TelegramWebAppAdapter exposes initData, themeParams, safeAreaInset, contentSafeAreaInset, ready(), expand(), setHeaderColor(), setBackgroundColor() and optional haptic().
- ApiClient.get<T>(path: string) and ApiClient.post<T>(path: string, body: unknown, actionId: string) send X-Telegram-Init-Data and X-Request-ID without logging either value.
- MotionState is "idle" | "primed" | "resolving" | "outcome" | "settle".
- reduceMotionState(current: MotionState, event: MotionEvent, reduced: boolean) -> MotionState is a pure reducer.
- RoomShell.svelte accepts a RoomSnapshot, a connection status and an action callback; game rooms render only public confirmed state.

- [ ] **Step 1: Write motion reducer tests**

Cover valid state transitions, invalid transition rejection, reduced-motion collapse, repeated settlement event and interruption by reconnect/navigation.

    it('collapses resolving to settle under reduced motion', () => {
      expect(reduceMotionState('resolving', { type: 'RESULT_CONFIRMED' }, true)).toBe('settle');
    });

- [ ] **Step 2: Implement the Telegram adapter and API client**

Load the official WebApp object when present, use a safe desktop fallback for Pages/local preview and keep raw init data in memory only. Apply safe-area CSS variables from Telegram values; do not put a token or user identity in local storage.

- [ ] **Step 3: Implement the shared shell and tokens**

Create dark ink/wine/brass base tokens, one room accent at a time, readable body sizes, focus styles and prefers-reduced-motion rules. Jokergem is displayed as a configurable label from the API response, not repeated as hard-coded game logic.

- [ ] **Step 4: Implement room state stores**

Store snapshot, stateVersion, connectionStatus, pendingActionIds and motionState. A reconnect calls the snapshot endpoint before enabling new actions. An action remains pending until the server event or an explicit error arrives.

- [ ] **Step 5: Implement the three skeleton room views**

SlotRoom.svelte renders a crisp 3×7 board, payline highlight from winning_lines and staggered stop choreography. BlackjackRoom.svelte renders actual card states, dealer hole-card state and HIT/STAND/DOUBLE only when legal. PokerRoom.svelte renders two seats, pot, current turn, timer and FOLD/CHECK/CALL/RAISE only when legal. Use authored CSS/SVG primitives, no final character art, random decorative cards or fake outcomes.

- [ ] **Step 6: Add browser tests for accessibility and reconnect**

Use a mocked API/WebSocket fixture to verify a 390×844 viewport, safe-area padding, keyboard/focus labels, reduced motion, result explanation and reconnect snapshot. Assert that the same action ID does not trigger two visual settlements.

- [ ] **Step 7: Run frontend checks and commit**

    pnpm miniapp:check
    pnpm miniapp:test
    pnpm miniapp:build
    pnpm miniapp:e2e -- --project=chromium
    git add apps/miniapp
    git commit -m "feat: add animated mini app game rooms"

### Task 10: Connect Compose, CI, documentation and release evidence

**Files:**

- Create: apps/api/Dockerfile
- Create: apps/bot/Dockerfile
- Create: apps/miniapp/Dockerfile
- Modify: docker-compose.yml
- Modify: .env.example
- Create: .github/workflows/ci.yml
- Modify: README.md
- Modify: dev/BuildSpec.md
- Modify: dev/ProjectLog.md
- Modify: docs/Technical-Architecture.md
- Modify: docs/Development-Roadmap.md
- Modify: docs/Design-Concept.md
- Modify: docs/Local-Setup.md
- Modify: docs/pages-demo/index.html
- Create: reports/monte-carlo/slot-skeleton-1.json
- Create: reports/monte-carlo/blackjack-skeleton-1.json
- Create: reports/monte-carlo/holdem-skeleton-1.json

**Interfaces:**

- Compose services are postgres, redis, api, bot and miniapp; API and bot wait for database/Redis health where required.
- CI exposes one required job verify that runs Python lint/tests, Mini App check/test/build and a Monte Carlo artifact step.
- Documentation states that the Pages demo is local/deterministic and that production requires Telegram auth, PostgreSQL and Redis.

- [ ] **Step 1: Add service Dockerfiles**

Create minimal multi-stage-compatible Dockerfiles: API runs uvicorn app.main:app, bot runs python -m app.main and Mini App builds with pnpm then serves static output from an unprivileged nginx image. No secret is copied into an image layer.

- [ ] **Step 2: Extend Compose with health-checked services**

Add environment-driven API/bot/Mini App services, expose API on API_PORT, keep PostgreSQL and Redis data volumes and add health checks for /health/ready and the bot process. Use .env.example names only.

- [ ] **Step 3: Add CI workflow**

Create .github/workflows/ci.yml with Python 3.12, Node/pnpm from the repository package manager, a PostgreSQL 16 service, a Redis 7 service and these steps:

    - run: uv sync --locked --dev
    - run: uv run --locked ruff check .
    - run: uv run --locked pytest -q
    - run: pnpm install --frozen-lockfile
    - run: pnpm miniapp:check
    - run: pnpm miniapp:test
    - run: pnpm miniapp:build
    - run: python -m devtools.monte_carlo.slot --trials 100000 --bet 10 --seed 42 --json > reports/monte-carlo/slot-skeleton-1.json
    - run: python -m devtools.monte_carlo.blackjack --trials 100000 --bet 25 --seed 42 --json > reports/monte-carlo/blackjack-skeleton-1.json
    - run: python -m devtools.monte_carlo.holdem --trials 100000 --seed 42 --json > reports/monte-carlo/holdem-skeleton-1.json

Upload the three simulation reports as CI artifacts after the corresponding runners exist. Keep the Pages deployment workflow separate and unchanged except for documentation copy.

- [ ] **Step 4: Update product and technical documentation**

Replace the obsolete roulette-first decisions in dev/BuildSpec.md with the three approved rooms, starter economy, provisional Jokergem name, no-Stars boundary and acceptance criteria. Update roadmap order to foundation → domain tests → ledger/API → Mini App → manual QA → thematic content. Record each completed checkpoint and command output in dev/ProjectLog.md.

- [ ] **Step 5: Make the Pages pilot honest and consistent**

Keep roulette as a demo-only legacy panel if it remains useful, but label it deterministic. Change generic virtual-token copy to Jokergem only where it does not imply production connectivity. Do not claim that the Pages pilot contains the server-authoritative 3×7 slot, production Blackjack or Hold’em.

- [ ] **Step 6: Generate and review Monte Carlo evidence**

Run the slot, Blackjack and Hold’em runners with fixed seeds and store JSON reports containing ruleset version, trial count, confidence interval and git commit. Review the output against exact fixtures and write the decision in dev/ProjectLog.md; a simulation report does not approve monetization or legal compliance.

- [ ] **Step 7: Run the release-candidate verification matrix**

    git diff --check
    uv run --locked ruff check .
    uv run --locked pytest -q
    pnpm miniapp:check
    pnpm miniapp:test
    pnpm miniapp:build
    docker compose config -q
    docker compose up -d postgres redis api bot miniapp
    curl --fail http://localhost:8000/health/live
    curl --fail http://localhost:8000/health/ready

Run the Playwright critical paths against the running Mini App, then stop the disposable stack with docker compose down without removing volumes. Record failures instead of marking unavailable Docker checks as green.

- [ ] **Step 8: Commit the integrated foundation**

    git add apps/api/Dockerfile apps/bot/Dockerfile apps/miniapp/Dockerfile docker-compose.yml .env.example .github/workflows/ci.yml README.md dev/BuildSpec.md dev/ProjectLog.md docs/Technical-Architecture.md docs/Development-Roadmap.md docs/Design-Concept.md docs/Local-Setup.md docs/pages-demo/index.html reports/monte-carlo
    git commit -m "chore: wire game platform services and verification"

## Self-review checklist

### Spec coverage

- Platform and dependency choices: Tasks 1, 6, 7 and 10.
- Telegram auth and secret handling: Tasks 7 and 8.
- Append-only ledger, atomic settlement and idempotency: Task 6, exercised again by Task 7.
- Slot layout, payout rules and Monte Carlo: Task 3.
- Blackjack transitions and simulation: Task 4.
- Hold’em actions, evaluator, tie split and equity simulation: Task 5.
- Jokergem starter economy and configurable naming: Tasks 2 and 6.
- Room UX, motion states, safe areas and reduced motion: Task 9.
- WebSocket resync and stale action rejection: Task 7 and Task 9.
- Compose, CI, Pages/demo boundary and documentation: Task 10.

### Placeholder scan

The plan contains no incomplete markers or unnamed error-handling steps. All later interfaces are named in the producing task before they are consumed.

### Type and interface consistency

- GameType, RoomStatus, ActionRequest and EventEnvelope are created in Task 2 and consumed by Tasks 6–9.
- RandomSource is created in Task 2 and injected into all three game modules in Tasks 3–5.
- WalletService is created in Task 6 and consumed by room settlement in Task 7.
- RoomService is created in Task 7 and consumed by the Mini App stores in Task 9.
- CURRENCY_CODE == "JOKERGEM" is defined once in the domain economy module; display text is supplied by configuration.

### Five review-focus tests

Each failure mode in the Review Focus section has an explicit test owner and command in Tasks 5–9. The plan does not rely on a visual screenshot as proof of server correctness.

## Execution handoff

Plan complete and saved to docs/superpowers/plans/2026-09-20-game-platform-foundation.md. Please review the plan and choose an execution approach before implementation:

- **Subagent-driven** — a fresh worker implements each task and a fresh reviewer checks it before the next task, then the whole branch is reviewed. This gives more independent checking but requires more context and coordination.
- **Native** — I implement every task myself in this session, with one fresh reviewer checking the completed branch. This is faster and better suited to the tightly coupled interfaces in this plan.

I recommend **Native** because the ten tasks share exact domain, ledger, API and UI interfaces, and keeping one implementer across those boundaries reduces contract drift. The plan must be approved before dependencies are installed or product code is changed.
