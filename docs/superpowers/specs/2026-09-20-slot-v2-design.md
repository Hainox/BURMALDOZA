# Slot v2: reel motion, win presentation, and Free Spins

Date: 2026-09-20  
Status: Design review after user approval of the direction; implementation follows after spec review.

## Intent

Turn the current slot room from a static 3×7 symbol grid with a small shake into a convincing casino-game sequence. The client must animate toward a server-confirmed result rather than inventing a result locally. The first feature extension is Free Spins. The separate bonus game is explicitly deferred and marked for a later design pass.

The audience is adult Telegram community users, but the game remains virtual-only: Jokergem has no cash value and there are no payments or withdrawals in this work.

## Evidence and current failure

The supplied screen recording is 45.6 seconds at 1920×1080/60 fps. In the slot section, the visible symbols remain fixed while the reel columns receive a small periodic translation and blur. The implementation confirms this: `SlotRoom.svelte` renders one fixed seven-symbol array per column and applies `reelRoll`, a 520 ms loop that moves the entire column by roughly four pixels. `motion.ts` has no reel-specific phases, stop positions, feature states, or payout choreography. The API currently emits the generic `slot.reels.stop.staggered` hint but does not include a slot outcome payload in the demo flow.

## Scope

### Included

- Preserve the existing 3-column × 7-visible-row slot format and server-first principle.
- Add real vertical reel tracks with repeated symbols, a clipped viewport, acceleration, sustained travel, velocity blur, and eased stopping at confirmed stops.
- Stop reels independently from left to right with deliberate timing and a final snap-free settle.
- Add a clear win sequence: payline draw, winning-symbol emphasis, payout count-up, and Jokergem particle burst.
- Add Free Spins as the first feature: three scatter symbols anywhere award five free spins in the demo ruleset, with a feature-intro transition, visible counter, automatic spins, accumulated payout, and feature summary.
- Extend the event/result shape so the UI can animate to confirmed stops, grid, winning lines, payout, and Free Spins state.
- Keep reduced-motion behavior functional and accessible.
- Add deterministic fixtures and unit/E2E coverage for normal spin, win, Free Spins, reconnect, and reduced motion.

### Deferred

The `Jokergem Vault` pick-a-gem bonus game is recorded as the next feature design. This pass reserves a feature boundary but does not implement the bonus screen, bonus payout rules, or bonus-specific animation.

### Not included

- Real-money wagering, payments, cash-out, or monetization.
- Client-side random outcome selection.
- Fake near-miss manipulation or changing a server-confirmed result to improve the animation.
- A visual asset-generation pass for the other game rooms.

## User-visible choreography

The standard spin sequence is:

1. `idle`: machine is breathing, button is available.
2. `primed`: button press gives immediate mechanical feedback and locks a second press.
3. `spinning`: all three tracks accelerate into a full continuous rotation. The track itself moves; a static grid is never passed off as a spin.
4. `stopping-1`, `stopping-2`, `stopping-3`: reels decelerate and land from left to right. Each stop uses the server-provided stop index and a different easing tail.
5. `outcome`: the confirmed grid is readable; winning lines draw one at a time if present.
6. `payout`: the amount counts up once, then the machine returns to `settle`.

Target timing for the normal sequence is approximately 2.8–3.4 seconds: 260 ms acceleration, at least 1.6 seconds of full travel, 320/480/640 ms stop offsets, and 220–360 ms settle/payout handoff. These values are implementation constants, not a reason to block the server response; if the server responds early, the client holds the reveal until the minimum readable motion has completed.

Free Spins branches after the confirmed outcome:

`outcome → feature-intro → free-spins-active → free-spins-spin → free-spins-summary → settle`

The intro displays the awarded count, each free spin uses the same full reel choreography with a shorter safe minimum, the counter decrements only after the confirmed result, and the summary counts the accumulated Jokergem payout. The player can see which result is confirmed at every stage.

## Outcome contract

The server-confirmed slot payload should carry the data needed to render without client RNG:

```text
grid: columns × visible rows
reel_stops: one stop index per reel
winning_lines: payline index, row path, symbols, payout
gross_payout: integer
net_delta: integer
feature: none | free-spins
free_spins_awarded: integer
free_spins_remaining: integer
ruleset_version: string
```

For the current demo shell, deterministic fixtures will emit the same shape so the motion can be reviewed reliably. The domain rules remain authoritative; animation timing and visual state do not alter the outcome.

## Motion implementation

- Each reel uses a clipped viewport and a track whose `transform: translate3d(...)` is the primary animated property.
- The track contains enough repeated symbols to cover the full travel distance without a visible seam. The final stop is normalized modulo the reel strip length.
- CSS custom properties expose phase, stop delay, and velocity to keep the Svelte markup readable.
- Blur is applied to a reel-level velocity treatment only while the track is moving; symbols do not individually smear or jump.
- Winning effects use opacity, transform, box-shadow, and compositor-friendly pseudo-elements. Layout-affecting properties are not animated.
- `prefers-reduced-motion` skips travel and reveals the confirmed grid and payout immediately while preserving state labels and result text.
- A stale or reconnecting room cancels the local timeline and renders the latest confirmed snapshot; no orphaned timers may restart an old spin.

## Accessibility and responsive behavior

- The spin control exposes its busy state and remains disabled while a round or feature sequence is active.
- The current phase is exposed through a compact status/live region without announcing every reel frame.
- All important result information remains text-readable: feature name, spins remaining, payout, and final result.
- The layout must remain usable at 320 px width and at desktop widths; animation geometry scales with the reel viewport rather than relying on fixed screen coordinates.
- Reduced motion removes travel and particle bursts, not information or controls.

## Test plan

### Unit tests

- A slot timeline produces the ordered phases and monotonically increasing reel stop times.
- A confirmed stop index maps to the expected visible grid without client-side randomness.
- A three-scatter result enters Free Spins with five awarded spins.
- Free Spins decrements only after a confirmed result and ends at the summary phase.
- Reconnect cancels an active local timeline and returns to a stable confirmed state.
- Reduced motion skips animation durations while preserving the same outcome.

### End-to-end tests

- A normal spin visibly exposes `data-slot-phase="spinning"` and then three stop phases before the final result.
- A win exposes the payline/payout presentation.
- A deterministic Free Spins fixture exposes the feature intro, remaining-spin counter, and summary.
- The existing accessibility and reconnect tests continue to pass.

### Manual review criteria

- At normal motion, a reviewer can clearly see multiple complete reel passes, acceleration, and distinct left-to-right stops.
- No symbol grid appears frozen while a generic glow claims that a spin is happening.
- The final frame is sharp and stable; no blurry symbols or duplicated/tearing tracks remain.
- The sequence feels intentional at both mobile and desktop widths.

## Acceptance criteria

The slot is ready for review only when the full spin choreography is present in the running Mini App, Free Spins can be entered through a deterministic test scenario, the deferred bonus boundary is documented, unit/E2E tests pass, and reduced-motion behavior still exposes the confirmed result.

