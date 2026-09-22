# Implementation Plan: Server-First Slot Result

> **For Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` (or `superpowers:subagent-driven-development`) to implement this plan task-by-task.

**Goal:** подключить серверный Slot v2 к live API так, чтобы RNG, reel stops, grid, payout и баланс подтверждались сервером, а Mini App только проигрывал уже подтверждённый результат, сохраняя текущую stop-continuity анимацию.

**Architecture:** один canonical slot-result payload проходит через domain → RoomService → EventEnvelope и `public_state.last_result` → Mini App adapter. `action_id` остаётся idempotency key; replay возвращает сохранённый event без нового RNG spin и wallet settlement.

**Branch/dependency:** сначала проверить и опубликовать `ccode/slot-stop-continuity` из issue #2. Реализацию начинать от ветки с этими изменениями; motion-файлы CCode не переписывать.

## Acceptance criteria

- Live `spin` использует только серверный RNG и skeleton fixture.
- Event и reconnect snapshot содержат один и тот же canonical result.
- Для одного `action_id` нет второго spin, wallet operation или ledger entry.
- Недостаточный баланс отклоняет действие до изменения room state и ledger.
- Client не вычисляет payout и не генерирует финальную сетку; он отображает `grid`, `winning_lines`, `gross_payout`, `balance_after` и `reel_stops` из API.
- Demo mode и текущая stop-continuity анимация остаются рабочими.

## Task 1: Publish and verify the Slot v2 motion dependency

**Files:** `apps/miniapp/src/lib/game/slot.ts`, `apps/miniapp/src/lib/rooms/SlotRoom.svelte`, `apps/miniapp/src/routes/+page.svelte`, `apps/miniapp/tests/e2e/slot-stop.spec.ts`.

1. Confirm that `ccode/slot-stop-continuity` exists remotely and is based on current `main`; if it is still only a local handoff, publish it before starting server changes.
2. Create the implementation branch from the published CCode branch and retain the approved spec plus this plan.
3. Run the motion-focused checks on that branch. Verify the data attributes and timing contract used by the existing accessibility tests.
4. Do not alter travel duration, staged stop order, reduced-motion behavior, or the reel CSS except for compile fixes required by the API adapter.

**Gate:** if the CCode branch cannot be published or its tests fail, stop implementation at this task and report the exact blocker.

## Task 2: Extend the domain outcome with authoritative stops and payline rows

**Tests first:** `tests/unit/domain/test_slot.py`.

1. Add failing deterministic tests proving that a seeded spin returns the chosen stop index for every reel, preserves the existing grid orientation, and exposes each winning payline's row path.
2. Extend `WinningLine` in `packages/domain/src/burmaldoza_domain/games/slot.py` with `rows` matching the configured payline.
3. Extend `SlotOutcome` with `reel_stops` and keep all existing payout fields intact.
4. Make `spin()` collect the exact `randbelow()` result before building each visible column. Make `calculate_payout()` attach the configured row path without changing left-to-right matching or wild behavior.
5. Keep `SlotConfig`, skeleton paylines, integer payout rules, and `ruleset_version` compatible with existing Monte Carlo tests.
6. Add serialization helpers only where the API boundary needs them; the pure domain result stays immutable and tuple-based.

**Verify:** `pytest tests/unit/domain/test_slot.py tests/unit/domain/test_rng.py` and the existing slot simulation tests.

## Task 3: Add one server-side slot execution path with atomic settlement

**Tests first:** `tests/unit/test_wallet_service.py`, `tests/unit/test_room_service.py`, and `tests/unit/test_api_routes.py`.

1. Load the skeleton ruleset through the existing fixture/config loader and use `SystemRandomSource` in production. Inject `SeededRandomSource` or an equivalent test RNG in unit tests so results are reproducible.
2. Add a small room-service slot execution seam rather than putting payout logic in the router. The seam must accept room, user, action request, bet, and active paylines, then return the domain outcome plus settlement result.
3. Reuse `WalletService.settle_game_round()` with `round_id = slot:<room_id>:<action_id>` and the action UUID as the idempotency key. Use the existing bet validation (integer, 10–100) and preserve virtual-currency-only behavior.
4. For memory mode, run spin, balance validation, settlement, room mutation, and action replay registration under the existing room lock. For PostgreSQL, keep room row lock, wallet lock, settlement, `GameAction`, and room state update in the same transaction.
5. Store the canonical result in the action record so replay can reconstruct the original event without calling RNG or wallet settlement again.
6. On insufficient funds or invalid bet/paylines, return the existing API error shape and leave `state_version`, `public_state`, wallet balance, and ledger counters unchanged.
7. Add a result serializer with stable keys: `grid`, `reel_stops`, `winning_lines` with `payline_index`, `rows`, `symbols`, `match_symbol`, `matched_columns`, `payout`, plus `gross_payout`, `net_delta`, `balance_after`, and `ruleset_version`.
8. Include the serialized result in `EventEnvelope.payload.result` and in `public_state.last_result`; keep `action_id`, `public_state`, `animation_hint`, and state-version semantics intact.
9. Make both memory and PostgreSQL action replay return the identical event payload and balance snapshot.

**Verify:** add assertions for one wallet operation and exactly two ledger entries when both stake and payout are non-zero; cover zero payout, insufficient funds, stale state version, wrong-room action replay, and repeated same-action replay.

## Task 4: Wire dependencies and API route behavior

**Files:** `apps/api/app/dependencies.py`, `apps/api/app/routers/rooms.py`, `apps/api/app/services/room_service.py`, `packages/contracts/src/burmaldoza_contracts/events.py` only if validation needs a typed result model.

1. Construct `WalletService` with the same session or memory store as `RoomService`; do not create a second independent wallet store in the request path.
2. Keep the router thin: it should validate auth/request shape and delegate the slot spin to `RoomService`.
3. Preserve generic action behavior for blackjack and holdem; their existing state transitions and event payloads must not acquire slot-only fields.
4. Ensure the response body and WebSocket event use the same `EventEnvelope` representation.
5. Add route tests that create a funded user/room, submit a spin, inspect `payload.result`, fetch a snapshot, and verify `snapshot.public_state.last_result` matches the event.
6. Add a reconnect/resync test that subscribes after the spin and confirms the last result is available without replaying the action.

## Task 5: Adapt the Mini App to server-confirmed results

**Tests first:** `apps/miniapp/src/lib/api/runtime.test.ts`, `apps/miniapp/src/lib/game/slot.test.ts`, and `apps/miniapp/tests/e2e/reconnect.spec.ts`.

1. Extend the client-side `SlotOutcome` type only as needed to carry server metadata; retain the current fields used by demo mode and highlights.
2. In `apps/miniapp/src/lib/api/runtime.ts`, map `event.payload.result` to the internal outcome: convert canonical column-major `grid` to the existing reel shape, map `winning_lines.rows` to highlight rows, use `gross_payout` for amount, `balance_after` for balance, and preserve `reel_stops` for diagnostics/test attributes.
3. Treat malformed or missing slot result as an API error state rather than fabricating a local grid or payout.
4. Update live action handling in `apps/miniapp/src/routes/+page.svelte` so the existing Slot v2 timeline starts from the server result and remains resolving until the already-defined stop-continuity duration completes.
5. Keep demo fallback behavior and non-slot generic event mapping unchanged.
6. Add an e2e live-mock or fixture test proving the UI renders the server grid and payout, ignores a contradictory client-side placeholder, and keeps reconnect state.
7. Do not change the CCode reel track, ticker, staged stop order, or reduced-motion contract.

## Task 6: Full verification and handoff

1. Run focused Python tests for domain, RNG, wallet, room service, API routes, and resync.
2. Run `pnpm check`, `pnpm test`, `pnpm build`, and the Playwright suite including `slot-stop.spec.ts`, accessibility, and reconnect.
3. Run the existing slot/RNG pytest and integration tests when `TEST_DATABASE_URL` is available; report explicit skips when it is not.
4. Inspect the final diff for accidental token/config changes, client-side RNG/payout, motion regressions, or duplicated timing constants.
5. Remove only the now-dead pre-CCode reel CSS if the final diff proves it is unused; do not combine unrelated visual cleanup.
6. Update `docs/Slot-V2-Status.md` or the project log with the canonical payload, idempotency behavior, and any remaining limitation.
7. Open a PR from the implementation branch, link issue #2 and the approved design spec, and include test evidence plus the explicit note that no real-money payment flow was added.

## Review focus

- Transaction boundary: room state, action record, wallet operation, and ledger must commit or roll back together.
- Replay: same `action_id` must return byte-equivalent result data and must not consume RNG.
- Contract shape: event and reconnect snapshot must agree.
- Orientation: server grid, client reels, visible rows, and payline rows must use one documented convention.
- Scope: CCode motion remains intact; no bot token or secret is committed.