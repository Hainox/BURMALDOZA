# Server-First Slot Result Design

Date: 2026-09-22
Status: Draft for review
Base: `main` at `fce8cf5`
Follow-up dependency: merge or rebase on the published CCode Slot v2 stop-continuity branch before implementation

## Context

The Mini App already has a server-first room and action flow, but the live slot action currently exposes only a generic accepted-action event. The client still renders a static demo outcome because the confirmed server result does not contain the slot grid, reel stop positions, winning lines, payout, or post-settlement balance.

The CCode Slot v2 stop-continuity work is reported as complete, but its branch is not currently present in GitHub. This design therefore preserves that work as an explicit dependency and does not change reel timing or stop behavior.

## Goals

- Make the server the only authority for slot RNG, reel stops, grid, payout, and balance settlement.
- Deliver one canonical slot result through both the action event and the persisted room snapshot.
- Keep action replay idempotent: repeating the same action ID must return the same result without another ledger mutation.
- Let the Mini App animate the already-confirmed result without generating or changing game data.
- Preserve the demo fallback and existing non-slot room behavior.
- Make reconnect/resync recover the latest confirmed slot result.

## Non-goals

- No real-money payments or withdrawals.
- No client-side RNG or client-side payout calculation.
- No redesign of Slot v2 motion, stop timing, reduced-motion behavior, or final-grid animation.
- No free-spin awards in live mode until the domain ruleset explicitly produces and persists them.
- No changes to blackjack or hold'em rules beyond shared result plumbing needed for type safety.

## Canonical server result

The domain slot outcome becomes the source of truth:

```json
{
  "kind": "slot",
  "grid": [["...", "..."], ["...", "..."], ["...", "..."]],
  "reel_stops": [0, 0, 0],
  "winning_lines": [
    {
      "payline_index": 0,
      "symbols": ["...", "...", "..."],
      "match_symbol": "...",
      "matched_columns": 3,
      "payout": 40
    }
  ],
  "gross_payout": 40,
  "net_delta": 30,
  "balance_after": 1030,
  "ruleset_version": "slot-skeleton-1"
}
```

The actual grid remains three columns by seven visible rows. `reel_stops` contains one server-selected strip index per reel. The domain `SlotOutcome` must retain the selected stops in addition to the existing grid and payout fields so the client can land the visual reels deterministically.

The event payload uses:

```json
{
  "action_id": "<uuid>",
  "public_state": { "...": "updated room state" },
  "result": { "...": "canonical slot result" }
}
```

The same `result` object is stored under `public_state.last_result` so a later snapshot or WebSocket reconnect can restore it without replaying the action.

## Server flow

1. Validate the action, bet limits, room membership, and expected state version.
2. Load the versioned slot fixture and use the production CSPRNG adapter.
3. Spin the configured reels and calculate winning lines on the server.
4. Settle stake and payout through the existing wallet ledger using the action ID as the idempotency key and the room/action as the game-round reference.
5. Update room state, increment state version, and persist the full result.
6. Persist the event record with the same result.
7. Publish the event only after the transaction has succeeded.
8. On replay, return the stored event and do not call RNG or settle the wallet again.

Room and wallet writes must share the same database transaction in production. The memory test store must use injected wallet and RNG dependencies so the same behavior can be tested without PostgreSQL.

## Client integration

The API adapter will parse `event.payload.result` and `public_state.last_result` into the existing Mini App result model.

The server contract uses the unambiguous name `grid`; the existing Slot v2 view model may continue to expose `reels` internally if that avoids touching the motion implementation. The adapter maps:

- `grid` -> visual reel data;
- `winning_lines` -> highlighted payline rows;
- `gross_payout` -> displayed payout amount;
- `balance_after` -> session balance;
- `reel_stops` -> landing metadata/test assertions.

The Mini App must never replace confirmed server symbols with a demo array in live mode. The demo path may keep its current fallback outcome when live API mode is disabled.

The Slot v2 timeline remains the only animation owner. Its duration constants must be imported from one module; `+page.svelte` must not duplicate the total reveal duration. The old dead reel CSS can be removed in the same cleanup, but no stop-continuity behavior may be altered.

## Error handling

- Invalid bet, illegal action, stale state version, or non-member access keeps the current API error contract.
- Insufficient balance must fail before the room is advanced and before an event is published.
- A failed settlement must leave both room state and wallet unchanged.
- A repeated action ID must return the original event, including the same grid, stops, payout, and balance.
- If a client reconnects after settlement, the snapshot's `last_result` is authoritative.

## Tests

### Domain

- `spin()` returns three seven-row reels and three stop indices.
- Stop indices reproduce the returned grid for the configured strips.
- Payout and net delta remain deterministic with a seeded RNG.
- Existing payline, wild, invalid-bet, and invalid-payline tests remain green.

### API/service

- A slot action includes the full result in the event and room snapshot.
- Memory and PostgreSQL paths use the same result shape.
- Replaying an action does not increase wallet operation or ledger-entry counts.
- Insufficient balance leaves state version, room state, and wallet balance unchanged.
- Reconnect returns the confirmed result from the latest snapshot.

### Mini App

- Event mapping produces a SlotOutcome from the canonical server result.
- Snapshot mapping restores the result after reconnect.
- Live mode never falls back to the static demo grid.
- Reduced-motion and existing Slot v2 phase tests remain green.

### Verification

Run the existing Python suite, Mini App check/test/build, Playwright E2E, Docker verification, and the slot/RNG/ledger integration tests before opening a PR.

## Rollout order

1. Publish and verify `ccode/slot-stop-continuity` or its PR.
2. Rebase this design and implementation branch on that exact commit.
3. Implement domain result metadata and transactional room/wallet plumbing.
4. Implement the client adapter and reconnect mapping.
5. Run the complete verification matrix.
6. Open a PR; do not update `main` directly.
