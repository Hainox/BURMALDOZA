<script lang="ts">
  import type { MotionState } from '$lib/game/motion';
  import ResultBand from '$lib/components/ResultBand.svelte';
  import type { RoomResult } from '$lib/state/room.svelte';

  export let motion: MotionState = 'idle';
  export let result: RoomResult | null = null;
  export let onAction: (action: string) => void = () => undefined;

  const playerCards = ['A♠', '10♥'];
  const dealerCards = ['K♦', '▣'];
</script>

<div class="game-room blackjack-room">
  <div class="room-intro"><div><span class="room-kicker">GFL SKELETON · DEALER STANDS ON 17</span><h2>Blackjack</h2><p>Чистый стол, понятная рука, серверная раздача.</p></div><span class="bet-chip">25 JG</span></div>
  <section class="felt-table" class:dealing={motion === 'resolving'} aria-label="Blackjack table">
    <div class="table-orbit orbit-one"></div><div class="table-orbit orbit-two"></div>
    <div class="hand dealer-hand"><span class="hand-label">DEALER <b>?</b></span><div class="cards">{#each dealerCards as card, index}<div class:hole-card={index === 1} class="playing-card" style={`--card-delay: ${index * 130}ms`}>{card}</div>{/each}</div><span class="total">{motion === 'outcome' || motion === 'settle' ? '17' : '—'}</span></div>
    <div class="table-mark" aria-hidden="true">♠</div>
    <div class="hand player-hand"><span class="hand-label">YOU <b>21</b></span><div class="cards">{#each playerCards as card, index}<div class="playing-card player-card" style={`--card-delay: ${index * 130}ms`}>{card}</div>{/each}</div><span class="total bright">21</span></div>
  </section>
  <div class="action-grid"><button on:click={() => onAction('hit')} disabled={motion === 'resolving'}>HIT <small>+ card</small></button><button class="action-primary" on:click={() => onAction('stand')} disabled={motion === 'resolving'}>STAND <small>lock hand</small></button><button on:click={() => onAction('double')} disabled={motion === 'resolving'}>DOUBLE <small>×2 stake</small></button></div>
  <ResultBand {result} {motion} />
</div>

<style>
  .game-room { position: relative; z-index: 1; display: grid; gap: 18px; } .room-intro { display: flex; justify-content: space-between; gap: 18px; } .room-kicker { color: #78d3a2; font-size: 9px; font-weight: 800; letter-spacing: 0.13em; } h2 { margin: 6px 0 5px; font-size: clamp(27px, 8vw, 38px); letter-spacing: -0.06em; } p { max-width: 250px; margin: 0; color: var(--muted); font-size: 12px; line-height: 1.45; } .bet-chip { height: fit-content; padding: 7px 9px; border: 1px solid rgb(142 228 182 / 30%); border-radius: 999px; color: #a4f0c4; font-size: 10px; font-weight: 800; white-space: nowrap; }
  .felt-table { position: relative; display: grid; align-content: space-between; min-height: 368px; overflow: hidden; padding: 25px 20px; border: 1px solid rgb(142 228 182 / 32%); border-radius: 42% / 18%; background: radial-gradient(ellipse at center, #174a40, #0a2829 72%); box-shadow: inset 0 0 40px rgb(0 0 0 / 40%), 0 18px 42px rgb(0 0 0 / 25%); } .table-orbit { position: absolute; inset: 16px; border: 1px solid rgb(142 228 182 / 12%); border-radius: 42% / 20%; pointer-events: none; } .orbit-two { inset: 28px; border-color: rgb(231 187 112 / 12%); transform: rotate(180deg); } .hand { position: relative; z-index: 1; display: grid; justify-items: center; gap: 8px; } .hand-label { color: rgb(255 247 237 / 68%); font-size: 9px; font-weight: 800; letter-spacing: 0.16em; } .hand-label b { color: var(--brass-300); } .cards { display: flex; justify-content: center; } .playing-card { display: grid; place-items: center; width: 64px; height: 86px; margin-left: -10px; border: 1px solid rgb(255 247 237 / 55%); border-radius: 8px; background: #fff8ee; color: #3b2430; font-size: 20px; font-weight: 850; box-shadow: 0 7px 14px rgb(0 0 0 / 25%); transform: rotate(-4deg); animation: dealCard 440ms cubic-bezier(.2, .8, .2, 1) var(--card-delay) both; } .playing-card:nth-child(2) { transform: rotate(5deg) translateY(3px); } .hole-card { background: repeating-linear-gradient(45deg, #321a2d 0 5px, #8f3559 5px 8px); color: var(--brass-300); } .player-card { border-color: rgb(231 187 112 / 75%); } .total { color: rgb(255 247 237 / 72%); font-size: 13px; font-weight: 800; } .total.bright { color: var(--brass-300); } .table-mark { position: absolute; top: 50%; left: 50%; color: rgb(231 187 112 / 15%); font-size: 58px; transform: translate(-50%, -50%); } .action-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; } .action-grid button { min-height: 54px; border: 1px solid var(--line); border-radius: 13px; background: rgb(255 247 237 / 6%); color: var(--ivory); font: inherit; font-size: 11px; font-weight: 850; cursor: pointer; transition: border-color 160ms ease, transform 160ms ease; } .action-grid button:hover { border-color: rgb(142 228 182 / 60%); transform: translateY(-2px); } .action-grid button:disabled { opacity: 0.48; cursor: wait; } .action-grid .action-primary { border-color: rgb(142 228 182 / 55%); background: rgb(142 228 182 / 15%); color: #b7f5cf; } .action-grid small { display: block; margin-top: 4px; color: var(--muted); font-size: 9px; font-weight: 500; }
  @keyframes dealCard { from { opacity: 0; transform: translateY(-22px) rotate(-8deg) scale(0.92); } to { opacity: 1; } }
</style>
