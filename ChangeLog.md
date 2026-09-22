# Change Log

## Unreleased

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
