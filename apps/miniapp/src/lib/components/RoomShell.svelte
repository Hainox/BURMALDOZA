<script lang="ts" module>
  export type RoomTheme = 'slot' | 'blackjack' | 'holdem';
</script>

<script lang="ts">
  import { setContext } from 'svelte';
  import { base } from '$app/paths';
  import type { MotionState } from '$lib/game/motion';
  import type { ConnectionStatus } from '$lib/state/session.svelte';
  import type { RoomSnapshot } from '$lib/state/room.svelte';

  export let room: RoomSnapshot;
  export let theme: RoomTheme = 'slot';
  export let connection: ConnectionStatus = 'demo';
  export let motion: MotionState = 'idle';
  export let balance = 0;
  // Пауза из хаба или системное «уменьшить движение»: фон и эффекты замирают.
  export let quiet = false;
  export let onBack: () => void = () => undefined;
  export let onResync: () => void = () => undefined;
  setContext('room-motion-quiet', () => quiet);

  const connectionLabel = {
    demo: 'DEMO',
    connecting: 'CONNECT',
    connected: 'LIVE',
    syncing: 'SYNC',
    offline: 'OFFLINE'
  } as const;

  // Сцена каждой комнаты: фон из утверждённых концептов, концепция комнат не меняется.
  const scenes: Record<RoomTheme, { kicker: string; title: string; backdrop: string | null }> = {
    slot: { kicker: 'RAINBOW SIX · SIEGE', title: 'Slot Siege', backdrop: 'slot/scene/room.webp' },
    blackjack: { kicker: 'GFL · SECTOR 09', title: 'Blackjack', backdrop: 'blackjack/room.webp' },
    holdem: { kicker: '神室町 · HEADS-UP', title: 'Hold’em', backdrop: 'holdem/scene/room.webp' }
  };
  $: scene = scenes[theme];
</script>

<main class="room-shell theme-{theme}" class:quiet data-motion={motion} data-testid="room-shell" data-theme={theme} aria-label={room.title}>
  <div class="scene" aria-hidden="true">
    {#if scene.backdrop}<img class="backdrop" src={`${base}/${scene.backdrop}`} alt="" decoding="async" />{/if}
    <div class="fx fx-a"></div>
    <div class="fx fx-b"></div>
    <div class="shade"></div>
  </div>

  <header class="room-topbar">
    <button class="back" on:click={onBack} aria-label="Назад к комнатам">
      <img src={`${base}/hub/icons/arrow-right.svg`} width="22" height="22" alt="" />
    </button>
    <div class="room-heading">
      <span>{scene.kicker}</span>
      <h1>{scene.title}</h1>
    </div>
    <button class="balance" on:click={onResync} data-testid="resync-button" aria-label={`Баланс ${balance} JG, ${connectionLabel[connection]}. Синхронизировать комнату`}>
      <img src={`${base}/hub/icons/diamond.svg`} width="20" height="20" alt="" />
      <span>
        <small><i class:active={connection === 'connected'}></i>{connectionLabel[connection]}</small>
        <strong>{balance.toLocaleString('ru-RU')} <em>JG</em></strong>
      </span>
    </button>
  </header>

  <section class="room-stage">
    <slot></slot>
  </section>
</main>

<style>
  .room-shell { position: relative; isolation: isolate; display: grid; align-content: start; gap: 14px; min-height: 100dvh; }

  /* Сцена: фон во весь экран с медленным «дыханием», как в хабе. */
  .scene, .scene > * { position: fixed; inset: 0; pointer-events: none; }
  .scene { z-index: -1; overflow: hidden; background: #07090c; }
  .backdrop { width: 100%; height: 100%; object-fit: cover; animation: scene-drift 28s ease-in-out infinite; }
  .shade { background: linear-gradient(180deg, rgb(5 6 9 / 50%) 0%, rgb(5 6 9 / 12%) 28%, rgb(5 6 9 / 55%) 62%, rgb(5 6 9 / 90%) 100%); }

  /* Blackjack: заброшенное здание за оцеплением, отсветы мигалок. */
  .theme-blackjack .backdrop { object-position: 60% 50%; opacity: .95; filter: saturate(.95) brightness(1.08); }
  .theme-blackjack .fx-a { background: radial-gradient(46% 20% at 30% 50%, rgb(255 40 60 / 34%), transparent 70%); animation: police-red 1.8s steps(1) infinite; }
  .theme-blackjack .fx-b { background: radial-gradient(46% 20% at 72% 48%, rgb(50 110 255 / 34%), transparent 70%); animation: police-blue 1.8s steps(1) infinite; }

  /* Slot Siege: тактический холод, дым и медленные лучи прожекторов. */
  .theme-slot .scene { background: radial-gradient(120% 70% at 50% 0%, #1d2a33 0%, #0b1116 55%, #06090c 100%); }
  .theme-slot .fx-a { inset: -30% -60%; background: conic-gradient(from 180deg at 50% 0%, transparent 0deg, rgb(205 228 240 / 10%) 8deg, transparent 18deg, transparent 340deg, rgb(205 228 240 / 8%) 350deg, transparent 360deg); animation: searchlight 14s ease-in-out infinite alternate; transform-origin: 50% 0%; }
  .theme-slot .fx-b { background: radial-gradient(60% 30% at 20% 85%, rgb(170 190 200 / 12%), transparent 70%), radial-gradient(55% 28% at 80% 75%, rgb(170 190 200 / 10%), transparent 70%); animation: smoke 22s ease-in-out infinite alternate; }

  /* Hold'em: ворота Камуро-тё, мерцающий неон. */
  .theme-holdem .backdrop { object-position: 50% 40%; opacity: .62; filter: blur(2px) saturate(1.1); transform: scale(1.06); }
  .theme-holdem .fx-a { background: radial-gradient(70% 34% at 50% 18%, rgb(255 46 96 / 22%), transparent 70%); animation: neon 6s linear infinite; }
  .theme-holdem .fx-b { background: radial-gradient(60% 30% at 50% 95%, rgb(201 162 74 / 16%), transparent 70%); }

  .quiet .scene *, .quiet :global(.game-room *), .quiet :global(.game-room *::after), .quiet :global(.poker-room *), .quiet :global(.poker-room *::after) { animation: none !important; transition: none !important; }
  .quiet .room-stage :global(.game-room) { animation: none; }
  .quiet :global(.win-light), .quiet :global(.prize-chips), .quiet :global(.pot-chips), .quiet :global(.big-win) { display: none; }
  .theme-holdem .backdrop { opacity: .9; filter: none; }
  .theme-blackjack .backdrop { object-position: 50% 0; }
  .theme-blackjack .backdrop { top: -60px; bottom: auto; }
  .room-shell { min-height: calc(100dvh - 42px); gap: 10px; }

  /* Шапка в стиле хаба. */
  .room-topbar { display: grid; grid-template-columns: 44px minmax(0, 1fr) auto; align-items: center; gap: 10px; padding-top: env(safe-area-inset-top); }
  .back { display: grid; place-items: center; width: 44px; height: 44px; border: 1px solid #b8955d; border-radius: 50%; background: #0a0e14c9; cursor: pointer; transition: transform .2s ease, background .2s ease; }
  .back img { transform: rotate(180deg); }
  .back:hover { background: #241b13; transform: translateX(-2px); }
  .back:active { transform: scale(.94); }
  .room-heading { min-width: 0; }
  .room-heading span { display: block; color: #f8d38b; font-size: 9px; font-weight: 700; letter-spacing: .2em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  h1 { margin: 3px 0 0; color: #fff1ca; font: 500 clamp(22px, 6.6vw, 30px)/1.05 Georgia, 'Times New Roman', serif; letter-spacing: -.03em; }
  .balance { display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 6px 12px 6px 10px; border: 1px solid #b8955d; border-radius: 22px; background: #0c0f16e6; color: #fff4d9; cursor: pointer; transition: transform .2s ease, box-shadow .2s ease; }
  .balance:hover { box-shadow: 0 0 18px #d5903b44; }
  .balance:active { transform: scale(.97); }
  .balance > span { display: grid; gap: 3px; text-align: left; }
  .balance small { display: flex; align-items: center; gap: 5px; color: #d8d1da; font-size: 8px; letter-spacing: .08em; }
  .balance i { width: 6px; height: 6px; border-radius: 50%; background: #e7bb70; }
  .balance i.active { background: #8ee4b6; box-shadow: 0 0 6px #8ee4b6; }
  .balance strong { font-size: 15px; line-height: 1; white-space: nowrap; }
  .balance em { color: #f8d38b; font-size: 11px; font-style: normal; }

  /* Сцена игры — без глухой карточки: комната «висит» на фоне. */
  .room-stage { position: relative; display: grid; align-content: start; }
  .room-stage :global(.game-room) { animation: roomContentIn 460ms cubic-bezier(.2, .8, .2, 1) both; }

  @keyframes scene-drift { 0%, 100% { transform: scale(1.04) translate3d(0, 0, 0); } 50% { transform: scale(1.08) translate3d(-1.5%, -1%, 0); } }
  @keyframes police-red { 0%, 49% { opacity: 1; } 50%, 100% { opacity: .15; } }
  @keyframes police-blue { 0%, 49% { opacity: .15; } 50%, 100% { opacity: 1; } }
  @keyframes searchlight { from { transform: rotate(-14deg); } to { transform: rotate(14deg); } }
  @keyframes smoke { from { transform: translate3d(-4%, 0, 0) scale(1); } to { transform: translate3d(4%, -3%, 0) scale(1.12); } }
  @keyframes neon { 0%, 100% { opacity: .85; } 46% { opacity: .85; } 47% { opacity: .35; } 48% { opacity: .9; } 72% { opacity: .7; } }
  @keyframes roomContentIn { from { opacity: 0; transform: translate3d(0, 14px, 0) scale(.985); } to { opacity: 1; transform: none; } }

  @media (prefers-reduced-motion: reduce) {
    .scene *, .room-stage :global(.game-room) { animation: none !important; }
    .back, .balance { transition: none; }
  }
</style>
