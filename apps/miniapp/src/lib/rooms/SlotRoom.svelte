<script lang="ts">
  import { onDestroy } from 'svelte';

  import ResultBand from '$lib/components/ResultBand.svelte';
  import {
    SLOT_LAUNCH_DURATION,
    SLOT_ROW_COUNT,
    SLOT_SPIN_DURATION,
    buildReelTrack,
    getSlotLaunchDelay,
    getSlotPhase,
    getSlotReelOffsetRows,
    getSlotReelPhase,
    getSlotStopDelay,
    getSlotStopStart,
    hasFreeSpins,
    type SlotOutcome,
    type SlotPhase,
    type SlotReelPhase
  } from '$lib/game/slot';
  import type { MotionState } from '$lib/game/motion';
  import type { RoomResult } from '$lib/state/room.svelte';

  export let motion: MotionState = 'idle';
  export let result: RoomResult | null = null;
  export let onAction: (action: string) => void = () => undefined;
  export let resultSource: 'demo' | 'live' = 'demo';

  const reelBases = [
    ['♣', '◆', '7', '✦', '♠', 'A', '♦'],
    ['7', '♠', '✦', 'K', '◆', 'Q', '♣'],
    ['◆', '7', '♣', '✦', 'A', '♠', '♦']
  ];

  let slotPhase: SlotPhase = 'idle';
  let elapsedMs = 0;
  let startedAt = 0;
  let spinSeq = 0;
  let reducedMotion = false;
  let reelOffsets = [0, 0, 0];
  let ticker: number | null = null;

  $: slotOutcome = result?.slotOutcome ?? null;
  $: confirmedReels = slotOutcome?.reels?.length === 3 ? slotOutcome.reels : reelBases;
  $: reelTracks = reelBases.map((base, reelIndex) =>
    buildReelTrack(base, confirmedReels[reelIndex] ?? base)
  );
  $: reelPhases = reelBases.map((_, reelIndex): SlotReelPhase =>
    slotPhase === 'idle' ? 'idle' : getSlotReelPhase(reelIndex, elapsedMs, reducedMotion)
  );
  $: stoppedReels = reelPhases.filter((phase) => phase === 'landed').length;
  $: winningRows = slotOutcome?.winningRows ?? [];
  $: showConfirmedGrid = Boolean(slotOutcome) && (slotPhase === 'settled' || motion === 'outcome' || motion === 'settle');
  $: sectionReelPhase = slotPhase === 'settled' ? 'outcome' : slotPhase;
  $: isSpinning = slotPhase !== 'idle' && slotPhase !== 'settled';

  function cancelTicker() {
    if (ticker !== null) {
      window.cancelAnimationFrame(ticker);
      ticker = null;
    }
  }

  function renderFrame(nextElapsedMs: number) {
    elapsedMs = nextElapsedMs;
    slotPhase = getSlotPhase(nextElapsedMs, reducedMotion);
    reelOffsets = reelBases.map((_, reelIndex) =>
      getSlotReelOffsetRows(reelIndex, nextElapsedMs, reducedMotion)
    );
  }

  function tick(now: number) {
    const nextElapsedMs = Math.max(0, now - startedAt);
    renderFrame(nextElapsedMs);
    if (slotPhase === 'settled') {
      ticker = null;
      return;
    }
    ticker = window.requestAnimationFrame(tick);
  }

  function startSpin() {
    cancelTicker();
    spinSeq += 1;
    reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    startedAt = performance.now();
    elapsedMs = 0;

    if (reducedMotion) {
      renderFrame(SLOT_SPIN_DURATION);
      return;
    }

    slotPhase = 'spinning';
    reelOffsets = [0, 0, 0];
    ticker = window.requestAnimationFrame(tick);
  }

  function handleAction(action: string) {
    if (motion === 'resolving' || ticker !== null) return;
    startSpin();
    onAction(action);
  }

  function isWinningSymbol(reelIndex: number, symbolIndex: number) {
    const finalStart = reelTracks[reelIndex].length - SLOT_ROW_COUNT;
    const row = symbolIndex - finalStart;
    const lineHit = slotOutcome?.winningLines?.some((line) => line.rows[reelIndex] === row) ?? false;
    return showConfirmedGrid && (lineHit || (!slotOutcome?.winningLines && winningRows.includes(row)));
  }

  function getSymbolToneIndex(reelIndex: number, symbolIndex: number) {
    return symbolIndex % reelBases[reelIndex].length;
  }

  function phaseLabel(phase: SlotPhase) {
    if (phase === 'spinning') return 'TRAVEL · 60 FPS';
    if (phase === 'stopping-left') return 'LANDING · LEFT REEL';
    if (phase === 'stopping-center') return 'LANDING · CENTER REEL';
    if (phase === 'stopping-right') return 'LANDING · RIGHT REEL';
    if (phase === 'settled') return 'SETTLED · SERVER GRID';
    return 'READY · SERVER-FIRST';
  }

  onDestroy(cancelTicker);
</script>

<div class="game-room slot-room">
  <div class="room-intro">
    <div>
      <span class="room-kicker">THREE REELS · SEVEN ROWS</span>
      <h2>Однорукий бандит</h2>
      <p>Полная прокрутка барабанов. Сервер подтверждает сетку, клиент показывает движение.</p>
    </div>
    <span class="bet-chip">10 JG</span>
  </div>

  <section
    class="slot-machine"
    class:resolving={motion === 'resolving'}
    data-slot-phase={slotPhase}
    data-reel-phase={sectionReelPhase}
    data-stopped-reels={stoppedReels}
    data-spin-duration={SLOT_SPIN_DURATION}
    data-spin-seq={spinSeq}
    data-testid="slot-machine"
    aria-label="Слот 3 на 7"
  >
    <div class="machine-rim" aria-hidden="true"></div>
    <div class="reel-grid">
      {#each reelTracks as track, reelIndex}
        <div
          class="reel"
          class:travel={reelPhases[reelIndex] === 'travel'}
          class:landing={reelPhases[reelIndex] === 'landing'}
          class:landed={reelPhases[reelIndex] === 'landed'}
          data-testid={`slot-reel-${reelIndex}`}
          data-launch-delay={getSlotLaunchDelay(reelIndex)}
          data-stop-delay={getSlotStopDelay(reelIndex)}
          data-stop-start={getSlotStopStart(reelIndex)}
          data-reel-phase={reelPhases[reelIndex]}
          aria-label={`Барабан ${reelIndex + 1}`}
          style={`--reel-launch-delay: ${getSlotLaunchDelay(reelIndex)}ms; --reel-launch-duration: ${SLOT_LAUNCH_DURATION}ms;`}
        >
          <div class="reel-window">
            <div
              class="reel-track"
              class:travel={reelPhases[reelIndex] === 'travel'}
              class:landing={reelPhases[reelIndex] === 'landing'}
              class:landed={reelPhases[reelIndex] === 'landed'}
              data-testid={`slot-reel-track-${reelIndex}`}
              data-track-length={track.length}
              style={`--reel-offset-rows: ${reelOffsets[reelIndex] ?? 0};`}
              aria-hidden="true"
            >
              {#each track as symbol, symbolIndex}
                <div
                  class="symbol"
                  class:tone-brass={getSymbolToneIndex(reelIndex, symbolIndex) % 2 === 1}
                  class:tone-pink={getSymbolToneIndex(reelIndex, symbolIndex) % 3 === 2}
                  class:winning={isWinningSymbol(reelIndex, symbolIndex)}
                >{symbol}</div>
              {/each}
            </div>
          </div>
        </div>
      {/each}
    </div>

    <div class="payline" class:visible={showConfirmedGrid} data-testid="slot-payline" aria-hidden="true"></div>
    {#if showConfirmedGrid}
      <div class="confirmed-grid" data-testid="slot-confirmed-grid" aria-live="polite">
        <span>SERVER GRID CONFIRMED</span>
        <strong>{slotOutcome?.winningLines?.length ?? slotOutcome?.winningRows.length ?? 0} PAYLINE{(slotOutcome?.winningLines?.length ?? slotOutcome?.winningRows.length ?? 0) === 1 ? '' : 'S'}</strong>
      </div>
    {/if}
    <div class="machine-lights" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div>
  </section>

  <div class="slot-status" data-testid="slot-status" aria-live="polite">
    <span>{phaseLabel(slotPhase)}</span>
    <strong>{stoppedReels}/{reelBases.length} REELS LANDED</strong>
  </div>

  <div class="slot-meta">
    <span><b>RTP</b> skeleton-1</span>
    <span><b>LINES</b> 3 active</span>
    <span><b>MOTION</b> wave · 60 fps</span>
  </div>

  {#if slotOutcome && hasFreeSpins(slotOutcome) && showConfirmedGrid}
    <section class="free-spins-panel" data-testid="slot-free-spins" aria-label="Доступны бесплатные вращения">
      <div>
        <span class="free-spins-kicker">BONUS STATE · SERVER CONFIRMED</span>
        <strong>{slotOutcome.freeSpinsRemaining} FREE SPINS</strong>
      </div>
      <button class="free-spin-action" on:click={() => handleAction('free-spin')}>
        Запустить Free Spin <span aria-hidden="true">↻</span>
      </button>
    </section>
  {/if}

  <button class="primary-action" on:click={() => handleAction('spin')} disabled={motion === 'resolving' || isSpinning} data-testid="slot-spin">
    <span class="action-icon" aria-hidden="true">↻</span>
    {isSpinning ? 'Барабаны останавливаются…' : motion === 'resolving' ? 'Ждём сервер…' : 'Крутить за 10 JG'}
  </button>
  <ResultBand {result} {motion} source={resultSource} />
</div>

<style>
  .game-room { position: relative; z-index: 1; display: grid; gap: 18px; }
  .room-intro { display: flex; justify-content: space-between; gap: 18px; }
  .room-kicker { color: var(--brass-300); font-size: 9px; font-weight: 800; letter-spacing: 0.14em; }
  h2 { margin: 6px 0 5px; font-size: clamp(25px, 7vw, 36px); letter-spacing: -0.06em; }
  p { max-width: 280px; margin: 0; color: var(--muted); font-size: 12px; line-height: 1.45; }
  .bet-chip { height: fit-content; padding: 7px 9px; border: 1px solid rgb(231 187 112 / 30%); border-radius: 999px; color: var(--brass-300); font-size: 10px; font-weight: 800; white-space: nowrap; }
  .slot-machine { position: relative; display: grid; place-items: center; min-height: 430px; padding: 54px 10px 30px; overflow: hidden; border: 1px solid rgb(231 187 112 / 36%); border-radius: 24px; background: radial-gradient(circle at 50% 25%, rgb(143 53 89 / 32%), transparent 56%), #12121b; box-shadow: inset 0 0 0 8px rgb(0 0 0 / 14%), inset 0 0 35px rgb(0 0 0 / 52%), 0 18px 40px rgb(0 0 0 / 28%); }
  .machine-rim { position: absolute; inset: 11px; border: 1px solid rgb(231 187 112 / 18%); border-radius: 18px; pointer-events: none; }
  .reel-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 7px; width: min(100%, 390px); }
  .reel { min-width: 0; padding: 8px 5px; border: 1px solid rgb(255 247 237 / 11%); border-radius: 14px; background: rgb(255 247 237 / 5%); transform: translate3d(0, 0, 0); backface-visibility: hidden; will-change: transform, opacity; }
  .reel.travel { animation: reelLaunchWave var(--reel-launch-duration) var(--ease-spring) var(--reel-launch-delay) both; }
  .reel.landing { animation: reelLandingWave 320ms var(--ease-smooth) both; }
  .reel.landed { animation: reelLanded 300ms var(--ease-smooth) both; }
  .reel-window { --symbol-size: clamp(34px, 8vw, 52px); --reel-gap: 6px; position: relative; height: calc(7 * (var(--symbol-size) + var(--reel-gap)) - var(--reel-gap)); overflow: hidden; mask-image: linear-gradient(to bottom, transparent 0, #000 8%, #000 92%, transparent 100%); contain: paint; }
  .reel-track { display: grid; gap: var(--reel-gap); transform: translate3d(0, calc(var(--reel-offset-rows) * (var(--symbol-size) + var(--reel-gap))), 0); will-change: transform; backface-visibility: hidden; contain: layout paint; }
  .symbol { display: grid; place-items: center; width: 100%; height: var(--symbol-size); border-radius: 10px; background: rgb(11 11 17 / 66%); color: var(--ivory); font-size: clamp(20px, 7vw, 32px); font-weight: 800; line-height: 1; text-shadow: 0 2px 12px rgb(231 187 112 / 22%); }
  .symbol.tone-brass { color: var(--brass-300); }
  .symbol.tone-pink { color: #ed9aaf; }
  .symbol.winning { border: 1px solid var(--brass-300); background: rgb(231 187 112 / 18%); box-shadow: 0 0 22px rgb(231 187 112 / 38%); animation: winningPulse 620ms ease-in-out 180ms infinite alternate; }
  .payline { position: absolute; right: 12%; left: 12%; top: 50%; height: 2px; border-radius: 999px; background: var(--brass-300); box-shadow: 0 0 12px var(--brass-300); opacity: 0; transform: scaleX(0); transition: opacity 180ms ease, transform 420ms cubic-bezier(.16, 1, .3, 1); }
  .payline.visible { opacity: 0.86; transform: scaleX(1); }
  .confirmed-grid { position: absolute; top: 17px; display: flex; align-items: center; gap: 8px; padding: 6px 10px; border: 1px solid rgb(142 228 182 / 38%); border-radius: 999px; background: rgb(17 40 33 / 82%); color: var(--success); font-size: 8px; font-weight: 800; letter-spacing: 0.1em; animation: confirmedGridIn 420ms var(--ease-enter) 80ms both; will-change: opacity, transform; }
  .confirmed-grid strong { color: var(--ivory); font-size: 8px; }
  .machine-lights { position: absolute; right: 28px; bottom: 22px; left: 28px; display: flex; justify-content: space-between; }
  .machine-lights i { width: 5px; height: 5px; border-radius: 50%; background: var(--brass-400); box-shadow: 0 0 10px var(--brass-400); animation: lightBlink 1.3s ease-in-out infinite; }
  .machine-lights i:nth-child(2) { animation-delay: 150ms; } .machine-lights i:nth-child(3) { animation-delay: 300ms; } .machine-lights i:nth-child(4) { animation-delay: 450ms; } .machine-lights i:nth-child(5) { animation-delay: 600ms; }
  .slot-status { display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 18px; color: var(--muted); font-size: 9px; letter-spacing: 0.08em; text-transform: uppercase; }
  .slot-status strong { color: var(--brass-300); font-size: 8px; }
  .slot-meta { display: flex; justify-content: space-between; gap: 8px; color: var(--muted); font-size: 9px; letter-spacing: 0.05em; text-transform: uppercase; }
  .slot-meta b { display: block; margin-bottom: 3px; color: var(--muted-strong); font-size: 8px; }
  .free-spins-panel { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 14px; border: 1px solid rgb(142 228 182 / 35%); border-radius: var(--radius-md); background: linear-gradient(105deg, rgb(142 228 182 / 12%), rgb(231 187 112 / 8%)); }
  .free-spins-panel > div { display: grid; gap: 4px; }
  .free-spins-kicker { color: var(--success); font-size: 8px; font-weight: 800; letter-spacing: 0.12em; }
  .free-spins-panel strong { color: var(--ivory); font-size: 16px; }
  .free-spin-action { min-height: 38px; padding: 0 12px; border: 1px solid rgb(142 228 182 / 42%); border-radius: 11px; background: rgb(142 228 182 / 12%); color: var(--success); font: inherit; font-size: 11px; font-weight: 800; cursor: pointer; transition: transform 160ms ease, background 160ms ease; }
  .free-spin-action:hover { transform: translateY(-1px); background: rgb(142 228 182 / 19%); }
  .primary-action { display: flex; align-items: center; justify-content: center; gap: 10px; min-height: 52px; border: 0; border-radius: 15px; background: linear-gradient(120deg, var(--brass-300), #c98f4e); color: #2a1820; font: inherit; font-size: 14px; font-weight: 850; cursor: pointer; box-shadow: 0 10px 24px rgb(231 187 112 / 18%); transition: transform 160ms ease, filter 160ms ease; }
  .primary-action:hover { filter: brightness(1.06); transform: translateY(-2px); } .primary-action:active { transform: translateY(1px); } .primary-action:disabled { cursor: wait; filter: saturate(0.7); } .action-icon { font-size: 21px; }
  @keyframes reelLaunchWave { 0% { transform: translate3d(0, 5px, 0) scale(.98); opacity: .72; } 55% { transform: translate3d(0, -2px, 0) scale(1.01); opacity: 1; } 100% { transform: translate3d(0, 0, 0) scale(1); opacity: 1; } }
  @keyframes reelLandingWave { 0% { transform: translate3d(0, 0, 0) scale(1); } 55% { transform: translate3d(0, -1px, 0) scale(1.012); } 100% { transform: translate3d(0, 0, 0) scale(1); } }
  @keyframes reelLanded { from { filter: brightness(1.1); } to { filter: brightness(1); } }
  @keyframes confirmedGridIn { from { opacity: 0; transform: translate3d(0, -7px, 0) scale(.97); } to { opacity: 1; transform: translate3d(0, 0, 0) scale(1); } }
  @keyframes winningPulse { from { transform: scale(1); } to { transform: scale(1.04); } } @keyframes lightBlink { 0%, 100% { opacity: 0.35; } 50% { opacity: 1; } }
  @media (max-width: 390px) { .free-spins-panel { align-items: stretch; flex-direction: column; } .free-spin-action { width: 100%; } }
  @media (prefers-reduced-motion: reduce) { .reel.travel, .reel.landing, .reel.landed, .symbol.winning, .machine-lights i { animation: none; } .reel-track { transition: none; } }
</style>
