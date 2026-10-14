# Change Log

## Unreleased

- Replace temporary Slot and Hold'em hub portal collages with integrated Tachanka and Infinite Wealth Kiryu illustrations.

- Siege slot cells and the machine are larger (about 58 px tall on a 390 px phone, up to 72 px), and operator portraits fill each cell so most of the operator is visible.

- Rooms now share the hub's look: a full-screen animated scene per room (Blackjack: the approved abandoned building behind the police perimeter with flashing police lights; Slot: tactical smoke and searchlights; Hold'em: the Kamurocho gate with neon flicker), a hub-style header with back button and balance pill, glass panels, and the same pause and reduced-motion behaviour. Technical labels are gone, the result band waits with animated dots and pops the payout, and ranking and history now live only in the hub. Blackjack gets a glowing table with a light sheen and a single row of actions. The Slot portal now features Tachanka and the Hold'em portal Kazuma Kiryu (Like a Dragon: Infinite Wealth).

- Bets now go up to the whole balance: five standard amounts (slot 10/25/50/100/250, Blackjack 25/50/100/250/500) plus a separate custom slider and field from the minimum to the current balance; the server cap rose from 100 JG to a technical 1,000,000 JG with the wallet still rejecting stakes above the balance. Blackjack shows the dealer T-Doll portrait, drops the deck and card-back captions, and replays the deal animation on every new hand instead of swapping card images. The hub headline now reads «Где сегодня сливаем хату?» with the subtitle «Три комнаты. Везде дилер мудак.»

- New Siege slot rooms use ruleset `slot-siege-2` with 9 paylines (all 7 rows plus two diagonals) at the same 10-100 JG stake per spin and the same paytable; reel strips were rebalanced to keep RTP at about 96.3% (exact 0.9627, Monte Carlo 0.959), with winning spins rising from 31% to 44%. Rooms already on `slot-siege-1` keep their three lines. The spin button now stays disabled until the previous result has fully settled, so a quick tap can no longer start reels without a server request.

- Added bet selection with five quick amounts and a custom slider: slot spins now use the chosen 10-100 JG stake (previously fixed at 10 JG), Blackjack offers 25/40/50/75/100 and any amount in 25-100, and Hold'em raises offer min, half pot, three-quarter pot, pot and all-in. The server still validates every amount.

- Redesigned the hub as a night atrium with three welcoming project mascots, illustrated activity portals including SOPPO for Blackjack, room entry transitions, animated backgrounds and buttons, accessible motion pause, and Play/Ranking/History navigation. Game rooms and rules are unchanged.

- Blackjack cards now show the approved Deck A T-Doll portraits and the S09 card back, with MICA Team / SUNBORN image attribution. Card mapping, rules and payouts are unchanged.

- Fixed live Hold'em hands failing to start: the client now accepts server card suits written as words.

- Fixed the Mini App staying in DEMO inside Telegram: the official Telegram WebApp script is now loaded.

- Hold'em PvP shows the opponent's verified Telegram username and an authenticated avatar, with a neutral fallback when no photo is available; avatar loading does not delay gameplay.

- Added the Siege slot visual theme with operation-specific operator portraits, immutable spin appearance, post-stop winning beams, next-operation announcements and image attribution. Legacy skeleton rooms remain supported; Siege Free Spins stay deferred. Reconnect snapshots can no longer reveal winning effects before the reels stop.

- Added cosmetic seven-day Siege operation rotation starting October 19, 2026 at 00:00 Moscow time, with optional dated arena overrides and immutable operation metadata on spin replays. Invalid or incomplete event configuration now fails at startup. Slot payouts and reel strips are unchanged.

- Added the Kamurocho Hold'em lobby and seat-specific table, hero intros, confirmed actions, PvP deadlines, reconnect/retry recovery, reduced motion and image attribution. Waiting search cancellation requires the server fix from PR #79. Demo hands never update the wallet.

- Allow players to cancel a waiting Hold'em opponent search with an idempotent action, without charging the buy-in.

- Telegram haptic feedback now works: the Mini App adapter uses `WebApp.HapticFeedback` instead of a non-existent `WebApp.haptic`.
- Added an index on ledger entries by time and reason for the weekly leaderboard; requires database migration 20261013_0006.
- Wallet history now orders a settlement payout before its stake when timestamps are equal, keeping the newest entries first.
- Added the authenticated Mini App top-15 leaderboard by net game result for the current Moscow calendar week, using verified Telegram usernames with an anonymous fallback; requires database migration 20261013_0004. DEMO shows no invented rankings. Players outside the top see their own place, and the table refreshes at most every 15 seconds.
- New Slot rooms use the approved slot-siege-1 eight-symbol payout rules; existing skeleton rooms retain their original ruleset.

- The Mini App now shows the player's wallet history (last 100 server ledger entries, Moscow time) and rereads it after confirmed grants and game actions; DEMO shows no invented entries.
- Refreshed the local project journal snapshot and QA status; closed assignments no longer appear as pending handoffs, and an empty queue is explained explicitly.
- Demo Slot, Blackjack and Hold’em copy now clearly identifies client-generated demo state; demo grid, bonus state and balance no longer imply server confirmation, while live wording remains unchanged.
- Mini App result labels now distinguish a completed demo outcome from a server-confirmed live result. Demo Slot and Hold’em details no longer claim server confirmation; confirmed balances remain limited to live results.
- Made the Blackjack demo table playable: a deterministic demo hand with HIT/STAND/DOUBLE, the dealer row revealed on stand, and an explicit marker that no server confirmed the round. A rejected live action (409 or a network failure) now re-reads the room automatically, so the next action sends the current `state_version` instead of repeating the stale one.
- Internal bot API routes now return 404 through the public Caddy site. The bot reaches the API through the private `bot_api` Docker network; production configuration permits HTTP only to the fixed `http://api:8000` service address.
- Fixed the slot reel stop: each reel now accelerates with its 0/110/220 ms stagger, holds a steady cruising speed to its own stop start (2000/2160/2320 ms), then brakes from that same speed to the exact server-confirmed grid. The shared slowdown that froze all reels together mid-spin and the visible relaunch jerk of the center and right reels are gone.
- Added live Daily (+250 JG) and Relief (+300 JG) grant controls to the Mini App dashboard: one `getWallet()` bootstrap call, fresh idempotency key per claim, balance only from the confirmed `balance_after`, 409 shown as cooldown, and no grant simulation in demo mode.
- Added the playable Blackjack GFL room UI: server-confirmed Deck A cards (RPK-16 at A♥, AK-12 at K♥), hidden hole-card back, 25–100 integer betting, legal-action buttons, error/retry and reconnect from the server snapshot, and reduced-motion support.
- Hardened production runbook checks against exported shell variables shadowing `.env`; nightly backup scheduling now works on a fresh account and is idempotent. Added explicit recovery steps for a failed database-name switch during rollback.
- Production Compose mounts the tracked slot ruleset read-only into API, preventing room-creation HTTP 500 in the built API image. The runbook preserves rollback images and restores backups into a separate database before switching, retaining the previous database.
- Added the production stack `docker-compose.prod.yml` and the runbook `docs/Deploy-Production.md`. Caddy is the only service with public ports (80/443) and serves `https://burmaldoza.ru` with automatic Let's Encrypt certificates, redirecting `www` and `burmaldoza.online`; `/api/*` (including room WebSockets) and `/health*` go to the API, everything else to the Mini App. The API runs as exactly one process (`--workers 1`, one replica); PostgreSQL and Redis sit on an internal network without outside access. The Mini App is built with `PUBLIC_API_BASE_URL=https://burmaldoza.ru`. `POSTGRES_PASSWORD`, `BOT_TOKEN` and `INTERNAL_API_TOKEN` are required at `compose config` time. Requires Docker Compose 2.23.1+. Nightly `pg_dump` backups are encrypted with the owner's `age` public key.
- First login through HTTP or WebSocket now handles concurrent requests without duplicate welcome grants or server errors; wallet bootstrap no longer creates a placeholder user.
- Bot-to-API requests now require a separate `INTERNAL_API_TOKEN` in both services and use `X-Internal-API-Token`; deploy both services with the same newly provisioned internal token. The bot refuses startup without it, and the API rejects internal requests when it is unset or reused from `BOT_TOKEN`.
- Expanded the Blackjack GFL Pages preview to switch between Deck A and Deck B, assigned RPK-16 to A♥ and AK-12 to K♥, and added 52 sourced Deck B portraits with M82A1 at 6♥ and PTRD at 7♥. Replaced the room concept with an abandoned-building police perimeter scene and updated its ambient sound direction.
- Published an interactive mobile-friendly Blackjack GFL Deck A preview on GitHub Pages with the Sector 09 room, card back, all 52 character cards, suit/rank filters, search, and card dossiers.
- Made `/health/ready` probe PostgreSQL and Redis with bounded timeouts and return HTTP 503 when either dependency is unavailable; `/health/live` remains independent of dependency health.
- New players now receive the 1 000 JOKERGEM welcome grant on first login (HTTP or WebSocket), exactly once. Added `POST /api/v1/wallet/relief/claim` and Mini App client methods for daily/relief claims. CORS now allows the origin of `MINIAPP_URL` even when it contains a path (GitHub Pages). Unauthenticated room WebSockets close after 5 seconds, and a wallet idempotency key owned by another user is rejected instead of replayed.
- Welcome grant keys no longer derive from predictable user IDs; reusing one request ID across different wallet claim types is rejected with HTTP 409. CORS now canonicalizes host case and default ports.
- Added the Blackjack GFL server action contract for explicit bets, deal/hit/stand/double transitions, server-only hole-card state, authoritative in-hand balance updates, idempotent ledger settlement, and result restoration. In-progress actions no longer appear as settled results. Deployments must apply Alembic revision `20260923_0003` before enabling the updated API. The visual Blackjack room handoff remains separate.
- Fixed a motion regression where reel distance variables were scoped above the symbol-size context, making the browser resolve the travel transform as invalid; the regression suite now samples the live transform during travel.
- Rebuilt Slot v2 motion handoff for seamless playback: the reel loop now advances by one repeated seven-row block, the stop phase is derived from the real action timeline, and deceleration uses a compositor-friendly transform transition without a delayed jump. Added soft confirmation/grid/result reveals and deterministic symbol tones so repeated blocks cannot change color at the loop seam.
- Refined Slot v2 motion: wave launch from reel 1 to 3, 2.4-second full travel, a softer 960 ms inertial stop tail, compositor-friendly `translate3d` transforms, and 60-fps target timing contracts.
- Implemented the first Slot v2 motion slice: full reel tracks, staged left-to-right stops, server-confirmed grid/payout reveal, five Free Spins, and reduced-motion handling.
- Replaced the README hero subject with the owner-provided full-body casino composition of the three female characters; the exact project information remains in the SVG/Markdown layer.
- Documented Slot v2 as a full-reel motion requirement with staged stops, server-confirmed payout, five Free Spins, and a deferred bonus mini-game redesign.
- Added the Codex ↔ Command Code workflow with explicit model IDs, effort levels, file boundaries, and handoff acceptance criteria.
- Replaced the Pages demo's initial-letter mark with the Memendoza channel avatar.
- Animated roulette spins, blackjack card dealing/reveal, and staggered slot stops in the local-only Pages demo.
- Expanded the Pages pilot with local-only blackjack and a three-reel slot, a shared virtual balance, scripted outcomes, and keyboard-accessible game controls.
- Removed external-project comparisons from repository copy and added a client-facing, interactive Pages pilot that uses only local virtual demo state.
- Documented the SvelteKit client stack and its boundaries with the FastAPI backend.
- Reworked the README hero: removed the obscured information card, split the Russian description into readable lines, and replaced the ornament with a clean transparent roulette featuring exactly four diagonal brass levers.
- Added a static GitHub Pages demo for the Burmaldoza visual casino concept. It uses simulated local UI state only and does not process payments, Telegram data, or real wagers.
- Redesigned the repository landing page with a project-native hybrid hero, architecture diagram, setup path, and explicit V1 boundaries.
- Clarified implemented versus planned features, separated the standalone Pages demo from the SvelteKit scaffold, and corrected setup commands and the case-sensitive Pages path. Documented verification blockers and the demo's scripted outcomes.
- Locked Python and frontend dependencies and added owner-approved esbuild build-script permission; verified the API unit test, lint checks, and static SvelteKit build.
