<script lang="ts">
  import type { MotionState } from '$lib/game/motion';
  import ResultBand from '$lib/components/ResultBand.svelte';
  import type { RoomResult } from '$lib/state/room.svelte';

  export let motion: MotionState = 'idle';
  export let result: RoomResult | null = null;
  export let onAction: (action: string) => void = () => undefined;

  const reels = [
    ['♣', '◆', '7', '✦', '♠', 'A', '♦'],
    ['7', '♠', '✦', 'K', '◆', 'Q', '♣'],
    ['◆', '7', '♣', '✦', 'A', '♠', '♦']
  ];
</script>

<div class="game-room slot-room">
  <div class="room-intro">
    <div>
      <span class="room-kicker">THREE REELS · SEVEN ROWS</span>
      <h2>Однорукий бандит</h2>
      <p>Три барабана. Один подтверждённый исход. Без фальшивых near-miss.</p>
    </div>
    <span class="bet-chip">10 JG</span>
  </div>
  <section class="slot-machine" class:resolving={motion === 'resolving'} aria-label="Слот 3 на 7">
    <div class="machine-rim"></div>
    <div class="reel-grid">
      {#each reels as reel, reelIndex}
        <div class="reel" style={`--reel-delay: ${reelIndex * 110}ms`}>
          {#each reel as symbol, rowIndex}
            <div class:winning={motion === 'outcome' && rowIndex === 3} class="symbol" aria-label={`Символ ${symbol}`}>{symbol}</div>
          {/each}
        </div>
      {/each}
    </div>
    <div class="payline" class:visible={motion === 'outcome'} aria-hidden="true"></div>
    <div class="machine-lights" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div>
  </section>
  <div class="slot-meta"><span><b>RTP</b> skeleton-1</span><span><b>LINES</b> 3 active</span><span><b>LIMIT</b> 10–100 JG</span></div>
  <button class="primary-action" on:click={() => onAction('spin')} disabled={motion === 'resolving'} data-testid="slot-spin">
    <span class="action-icon" aria-hidden="true">↻</span>
    {motion === 'resolving' ? 'Барабаны останавливаются…' : 'Крутить за 10 JG'}
  </button>
  <ResultBand {result} {motion} />
</div>

<style>
  .game-room { position: relative; z-index: 1; display: grid; gap: 18px; }
  .room-intro { display: flex; justify-content: space-between; gap: 18px; }
  .room-kicker { color: var(--brass-300); font-size: 9px; font-weight: 800; letter-spacing: 0.14em; }
  h2 { margin: 6px 0 5px; font-size: clamp(25px, 7vw, 36px); letter-spacing: -0.06em; }
  p { max-width: 250px; margin: 0; color: var(--muted); font-size: 12px; line-height: 1.45; }
  .bet-chip { height: fit-content; padding: 7px 9px; border: 1px solid rgb(231 187 112 / 30%); border-radius: 999px; color: var(--brass-300); font-size: 10px; font-weight: 800; white-space: nowrap; }
  .slot-machine { position: relative; display: grid; place-items: center; min-height: 368px; padding: 22px 10px; overflow: hidden; border: 1px solid rgb(231 187 112 / 36%); border-radius: 24px; background: radial-gradient(circle at 50% 25%, rgb(143 53 89 / 32%), transparent 56%), #12121b; box-shadow: inset 0 0 0 8px rgb(0 0 0 / 14%), inset 0 0 35px rgb(0 0 0 / 52%), 0 18px 40px rgb(0 0 0 / 28%); }
  .machine-rim { position: absolute; inset: 11px; border: 1px solid rgb(231 187 112 / 18%); border-radius: 18px; pointer-events: none; }
  .reel-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 7px; width: min(100%, 330px); }
  .reel { display: grid; gap: 5px; padding: 7px 5px; border: 1px solid rgb(255 247 237 / 11%); border-radius: 14px; background: rgb(255 247 237 / 5%); }
  .symbol { display: grid; place-items: center; aspect-ratio: 1 / 1; border-radius: 10px; background: rgb(11 11 17 / 66%); color: var(--ivory); font-size: clamp(20px, 7vw, 32px); font-weight: 800; line-height: 1; text-shadow: 0 2px 12px rgb(231 187 112 / 22%); }
  .symbol:nth-child(2n) { color: var(--brass-300); }
  .symbol:nth-child(3n) { color: #ed9aaf; }
  .symbol.winning { border: 1px solid var(--brass-300); background: rgb(231 187 112 / 18%); box-shadow: 0 0 22px rgb(231 187 112 / 38%); animation: winningPulse 620ms ease-in-out infinite alternate; }
  .resolving .reel { animation: reelRoll 520ms cubic-bezier(.4, 0, .2, 1) var(--reel-delay) infinite; }
  .payline { position: absolute; left: 12%; right: 12%; top: 50%; height: 2px; border-radius: 999px; background: var(--brass-300); box-shadow: 0 0 12px var(--brass-300); opacity: 0; transform: scaleX(0); transition: opacity 180ms ease, transform 420ms cubic-bezier(.16, 1, .3, 1); }
  .payline.visible { opacity: 0.86; transform: scaleX(1); }
  .machine-lights { position: absolute; right: 28px; bottom: 22px; left: 28px; display: flex; justify-content: space-between; }
  .machine-lights i { width: 5px; height: 5px; border-radius: 50%; background: var(--brass-400); box-shadow: 0 0 10px var(--brass-400); animation: lightBlink 1.3s ease-in-out infinite; }
  .machine-lights i:nth-child(2) { animation-delay: 150ms; } .machine-lights i:nth-child(3) { animation-delay: 300ms; } .machine-lights i:nth-child(4) { animation-delay: 450ms; } .machine-lights i:nth-child(5) { animation-delay: 600ms; }
  .slot-meta { display: flex; justify-content: space-between; gap: 8px; color: var(--muted); font-size: 9px; letter-spacing: 0.05em; text-transform: uppercase; }
  .slot-meta b { display: block; margin-bottom: 3px; color: var(--muted-strong); font-size: 8px; }
  .primary-action { display: flex; align-items: center; justify-content: center; gap: 10px; min-height: 52px; border: 0; border-radius: 15px; background: linear-gradient(120deg, var(--brass-300), #c98f4e); color: #2a1820; font: inherit; font-size: 14px; font-weight: 850; cursor: pointer; box-shadow: 0 10px 24px rgb(231 187 112 / 18%); transition: transform 160ms ease, filter 160ms ease; }
  .primary-action:hover { filter: brightness(1.06); transform: translateY(-2px); } .primary-action:active { transform: translateY(1px); } .primary-action:disabled { cursor: wait; filter: saturate(0.7); } .action-icon { font-size: 21px; }
  @keyframes reelRoll { 0% { transform: translateY(-4px); filter: blur(0); } 40% { transform: translateY(4px); filter: blur(2px); } 100% { transform: translateY(-2px); filter: blur(0); } }
  @keyframes winningPulse { from { transform: scale(1); } to { transform: scale(1.04); } } @keyframes lightBlink { 0%, 100% { opacity: 0.35; } 50% { opacity: 1; } }
</style>
