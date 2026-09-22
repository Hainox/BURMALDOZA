# Blackjack server room contract

## Scope

Connect the existing `blackjack-gfl-skeleton-1` domain engine to room actions and the virtual wallet. Preserve the approved rules: bets from 25 through 100 JOKERGEM, dealer stands on soft 17, natural blackjack pays 3:2, and available player actions are hit, stand, and double. Split remains unavailable.

## Action contract

- A newly created Blackjack room exposes `deal` as its first legal action.
- `deal` accepts `{"action":"deal","bet":25}` through the existing `ActionRequest` envelope. The amount must be an integer in the published ruleset range.
- A successful `deal` debits the stake and persists the initial server-dealt hand in the same room/action/ledger transaction.
- The solo room's public state carries the authoritative wallet balance after each action so the Mini App reflects the debit before the hand settles. An in-progress action has no settlement result; the client must not fabricate one.
- `hit`, `stand`, and `double` use the existing rules engine. `double` is legal only on the initial hand and debits the additional stake in the same action transaction.
- A completed hand credits the rules engine's gross payout. The result includes the outcome, final totals, gross payout, net delta, and authoritative balance after payout.
- Replaying an `action_id` returns its stored event without another shuffle, wallet mutation, or ledger entry. A stale `expected_state_version` returns the current snapshot through the existing 409 response.

## State privacy and recovery

- The full deck and dealer hole card live in server-only room state, separate from the public state JSON.
- While the player hand is active, public state exposes the player's cards and only the dealer up-card; it never includes the hole card or a total computed from that hidden card.
- After settlement, the public result may reveal the dealer's complete hand and totals.
- The confirmed public state and result are stored with the action so reconnect restores the same state without re-running the game.

## Acceptance checks

- Insufficient funds and illegal actions leave the wallet, room version, private state, and action log unchanged.
- Initial deal, double, natural blackjack, ordinary win, loss, and push use integer ledger entries and authoritative post-action balances.
- Two natural blackjacks push and return the original stake; integer 3:2 natural payouts follow the domain engine's whole-token rounding rule.
- Action retry does not shuffle or settle twice; stale state is rejected.
- API snapshot and action event never expose the dealer hole card before settlement.
- Unit tests cover memory mode; PostgreSQL integration verifies durable replay and recovery.
