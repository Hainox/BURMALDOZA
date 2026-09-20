<script lang="ts">
  import type { MotionState } from '$lib/game/motion';
  import type { ConnectionStatus } from '$lib/state/session.svelte';
  import type { RoomSnapshot } from '$lib/state/room.svelte';

  export let room: RoomSnapshot;
  export let connection: ConnectionStatus = 'demo';
  export let motion: MotionState = 'idle';
  export let onBack: () => void = () => undefined;
  export let onResync: () => void = () => undefined;
</script>

<main class="room-shell" data-motion={motion} data-testid="room-shell">
  <header class="room-topbar">
    <button class="icon-button" on:click={onBack} aria-label="Назад к комнатам">←</button>
    <div class="room-heading">
      <span>ROOM · {room.rulesetVersion}</span>
      <h1>{room.title}</h1>
    </div>
    <button class="connection-button" on:click={onResync} data-testid="resync-button">
      <span class:active={connection === 'connected'}></span>
      {connection === 'syncing' ? 'SYNC' : 'DEMO'}
    </button>
  </header>

  <section class="room-stage">
    <div class="stage-glow" aria-hidden="true"></div>
    <slot></slot>
  </section>
</main>

<style>
  .room-shell { display: grid; gap: 14px; min-height: 100dvh; }
  .room-topbar { display: grid; grid-template-columns: 40px 1fr auto; align-items: center; gap: 10px; }
  .icon-button, .connection-button { border: 1px solid var(--line); border-radius: 12px; background: rgb(255 247 237 / 6%); color: var(--ivory); cursor: pointer; }
  .icon-button { width: 40px; height: 40px; font-size: 20px; }
  .room-heading { min-width: 0; }
  .room-heading span { color: var(--muted); font-size: 9px; letter-spacing: 0.13em; }
  h1 { margin: 3px 0 0; font-size: 20px; letter-spacing: -0.04em; }
  .connection-button { display: inline-flex; align-items: center; gap: 7px; padding: 8px 10px; color: var(--muted-strong); font-size: 9px; font-weight: 800; letter-spacing: 0.09em; }
  .connection-button span { width: 6px; height: 6px; border-radius: 50%; background: var(--brass-400); }
  .connection-button span.active { background: var(--success); }
  .room-stage { position: relative; display: grid; align-content: start; min-height: 580px; overflow: hidden; padding: 20px 15px 15px; border: 1px solid var(--line); border-radius: var(--radius-xl); background: linear-gradient(145deg, rgb(255 255 255 / 5%), rgb(255 255 255 / 1%)); box-shadow: var(--shadow-deep); }
  .stage-glow { position: absolute; top: -100px; right: -70px; width: 240px; height: 240px; border-radius: 50%; background: rgb(143 53 89 / 23%); filter: blur(45px); pointer-events: none; animation: breathe 5s ease-in-out infinite; }
  @keyframes breathe { 0%, 100% { transform: scale(0.88); opacity: 0.6; } 50% { transform: scale(1.12); opacity: 1; } }
  @media (min-width: 720px) { .room-stage { padding: 30px; } }
</style>
