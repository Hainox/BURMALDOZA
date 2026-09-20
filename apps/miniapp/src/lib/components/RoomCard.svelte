<script lang="ts">
  import type { GameType } from '$lib/state/room.svelte';

  export let gameType: GameType;
  export let eyebrow: string;
  export let title: string;
  export let description: string;
  export let accent: string;
  export let icon: string;
  export let onSelect: () => void = () => undefined;
</script>

<button class="room-card" style={`--accent: ${accent}`} on:click={onSelect} data-testid={`room-card-${gameType}`}>
  <span class="room-card-glow" aria-hidden="true"></span>
  <span class="room-icon" aria-hidden="true">{icon}</span>
  <span class="room-card-copy">
    <span class="room-eyebrow">{eyebrow}</span>
    <strong>{title}</strong>
    <span>{description}</span>
  </span>
  <span class="room-arrow" aria-hidden="true">↗</span>
</button>

<style>
  .room-card {
    position: relative;
    display: grid;
    grid-template-columns: 54px 1fr 24px;
    align-items: center;
    gap: 14px;
    width: 100%;
    min-height: 118px;
    overflow: hidden;
    padding: 18px 18px 18px 16px;
    border: 1px solid rgb(255 247 237 / 12%);
    border-radius: var(--radius-lg);
    background: linear-gradient(135deg, rgb(255 255 255 / 8%), rgb(255 255 255 / 3%));
    color: var(--ivory);
    text-align: left;
    cursor: pointer;
    isolation: isolate;
    transition: transform 180ms ease, border-color 180ms ease, background 180ms ease;
  }

  .room-card:hover {
    border-color: color-mix(in srgb, var(--accent) 70%, white 12%);
    background: linear-gradient(135deg, rgb(255 255 255 / 11%), rgb(255 255 255 / 4%));
    transform: translateY(-2px);
  }

  .room-card:active { transform: translateY(1px) scale(0.995); }
  .room-card-glow { position: absolute; z-index: -1; width: 150px; height: 150px; right: -38px; bottom: -72px; border-radius: 50%; background: var(--accent); filter: blur(28px); opacity: 0.28; transition: transform 420ms ease, opacity 420ms ease; }
  .room-card:hover .room-card-glow { transform: scale(1.35); opacity: 0.48; }
  .room-icon { display: grid; place-items: center; width: 54px; height: 54px; border: 1px solid color-mix(in srgb, var(--accent) 55%, white 8%); border-radius: 17px; background: color-mix(in srgb, var(--accent) 22%, var(--ink-850)); box-shadow: inset 0 1px 0 rgb(255 255 255 / 12%); color: var(--accent); font-size: 26px; }
  .room-card-copy { display: grid; gap: 4px; min-width: 0; }
  .room-eyebrow { color: var(--accent); font-size: 9px; font-weight: 800; letter-spacing: 0.16em; text-transform: uppercase; }
  .room-card-copy strong { font-size: 18px; letter-spacing: -0.03em; }
  .room-card-copy > span:last-child { overflow: hidden; color: var(--muted); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
  .room-arrow { color: var(--muted-strong); font-size: 21px; transition: transform 180ms ease, color 180ms ease; }
  .room-card:hover .room-arrow { color: var(--accent); transform: translate(2px, -2px); }
</style>
