<script lang="ts">
  import { onDestroy } from 'svelte';
  import { browser } from '$app/environment';
  import {
    SLOT_LAUNCH_OFFSETS_MS,
    planSlotReelStops,
    slotReelMovingAt,
    slotReelTrackShiftPx,
    stoppedReelCountAt,
    type SlotReelPhase,
    type SlotReelStopPlan
  } from '$lib/game/slot';
  import type { MotionState } from '$lib/game/motion';
  import ResultBand from '$lib/components/ResultBand.svelte';
  import type { RoomResult } from '$lib/state/room.svelte';

  export let motion: MotionState = 'idle';
  export let result: RoomResult | null = null;
  export let onAction: (action: string) => void = () => undefined;
  export let reducedMotion = false;

  const reels = [
    ['♣', '◆', '7', '✦', '♠', 'A', '♦'],
    ['7', '♠', '✦', 'K', '◆', 'Q', '♣'],
    ['◆', '7', '♣', '✦', 'A', '♠', '♦']
  ];

  const STOPPED_LABEL: Record<SlotReelPhase, string> = {
    spinning: 'Барабаны вращаются',
    'stopping-left': 'Левый барабан останавливается',
    'stopping-center': 'Центральный барабан останавливается',
    'stopping-right': 'Правый барабан останавливается',
    settled: 'Сетка подтверждена'
  };

  let stopPlan: SlotReelStopPlan = planSlotReelStops({ reducedMotion: true });
  let stoppedReels = 3;
  let stopPhase: SlotReelPhase = 'settled';
  let prefersReducedMotion = reducedMotion;
  let motionQuery: MediaQueryList | null = null;
  let rafId = 0;
  let spinStart = 0;
  let spinStatus = STOPPED_LABEL.settled;
  let previousMotion: MotionState = motion;
  let stopArmed = false;
  let trackNodes: HTMLElement[] = [];
  let symbolNodes: HTMLElement[] = [];
  let trackOffset = [0, 0, 0];
  let symbolPx = 0;
  let gapPx = 5;

  $: if (browser && symbolPx <= 0 && symbolNodes.some(Boolean)) {
    measureSymbol();
  }

  function measureSymbol() {
    const node = symbolNodes.find((entry) => entry);
    symbolPx = node?.offsetHeight ?? 0;
    const track = trackNodes.find((entry) => entry);
    if (track) {
      const style = browser ? getComputedStyle(track) : null;
      const parsed = style ? Number.parseFloat(style.rowGap || style.gap || '5') : 5;
      gapPx = Number.isFinite(parsed) ? parsed : 5;
    }
  }

  function paintTrackOffsets(elapsedMs: number) {
    measureSymbol();
    trackOffset = [0, 1, 2].map((index) => {
      const reel = index as 0 | 1 | 2;
      const node = trackNodes[reel];
      const offset = slotReelTrackShiftPx(elapsedMs, reel, stopPlan, symbolPx, gapPx);
      if (node) node.style.transform = `translate3d(0, ${offset.toFixed(2)}px, 0)`;
      return offset;
    });
  }

  function settleTrackOffsets() {
    paintTrackOffsets(stopPlan.totalMs);
  }

  function cancelTicker() {
    if (browser && rafId !== 0) cancelAnimationFrame(rafId);
    rafId = 0;
  }

  function updateSpinStatus() {
    spinStatus = motion === 'resolving' ? STOPPED_LABEL[stopPhase] : STOPPED_LABEL.settled;
  }

  function markStopped(count: number, phase: SlotReelPhase) {
    stoppedReels = count;
    stopPhase = phase;
    updateSpinStatus();
  }

  function renderFrozenGrid() {
    cancelTicker();
    settleTrackOffsets();
    markStopped(3, 'settled');
  }

  function runStopTicker() {
    cancelTicker();
    if (!browser) return;
    if (!stopArmed) {
      stopPlan = planSlotReelStops({ reducedMotion: prefersReducedMotion });
    }
    spinStart = performance.now();
    paintTrackOffsets(0);
    markStopped(0, 'spinning');
    const tick = (now: number) => {
      const elapsed = now - spinStart;
      const landed = stoppedReelCountAt(elapsed, stopPlan);
      paintTrackOffsets(elapsed);
      if (elapsed >= stopPlan.reelStopsMs[2]) {
        markStopped(landed, 'stopping-right');
      } else if (elapsed >= stopPlan.reelStopsMs[1]) {
        markStopped(landed, 'stopping-center');
      } else if (elapsed >= stopPlan.reelStopsMs[0]) {
        markStopped(landed, 'stopping-left');
      } else {
        markStopped(landed, 'spinning');
      }
      if (elapsed < stopPlan.totalMs) {
        rafId = requestAnimationFrame(tick);
        return;
      }
      settleTrackOffsets();
      markStopped(3, 'settled');
      rafId = 0;
    };
    rafId = requestAnimationFrame(tick);
  }

  function syncStopTimeline(activeMotion: MotionState) {
    if (activeMotion === 'resolving') {
      if (prefersReducedMotion) {
        renderFrozenGrid();
        return;
      }
      runStopTicker();
      return;
    }
    stopArmed = false;
    if (activeMotion === 'outcome' || activeMotion === 'settle' || activeMotion === 'idle') {
      renderFrozenGrid();
    }
  }

  function handleSpin() {
    stopPlan = planSlotReelStops({ reducedMotion: prefersReducedMotion });
    if (prefersReducedMotion) {
      renderFrozenGrid();
    } else {
      stopArmed = true;
      runStopTicker();
    }
    onAction('spin');
  }

  function updateReducedMotion(matches: boolean) {
    prefersReducedMotion = reducedMotion || matches;
    if (motion === 'resolving') syncStopTimeline(motion);
    if (prefersReducedMotion && motion !== 'idle') renderFrozenGrid();
  }

  $: if (motion !== previousMotion) {
    previousMotion = motion;
    syncStopTimeline(motion);
    updateSpinStatus();
  }
  $: reelPhase = (index: number) =>
    stoppedReels > index || motion === 'outcome' || motion === 'settle' ? 'landed' : motion === 'resolving' ? 'travel' : 'ready';
  $: reelMoving = (index: number) => {
    void trackOffset;
    if (motion !== 'resolving') return false;
    return slotReelMovingAt(performance.now() - spinStart, index as 0 | 1 | 2, stopPlan);
  };

  if (browser) {
    motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    updateReducedMotion(motionQuery.matches);
    const onChange = (event: MediaQueryListEvent) => updateReducedMotion(event.matches);
    motionQuery.addEventListener('change', onChange);
    onDestroy(() => {
      cancelTicker();
      motionQuery?.removeEventListener('change', onChange);
    });
  }
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
    <div class="reel-grid" data-slot-phase={motion === 'resolving' ? stopPhase : motion} data-stopped-reels={stoppedReels} data-motion={motion}>
      {#each reels as reel, reelIndex}
        <div
          class="reel"
          class:moving={motion === 'resolving' && stoppedReels <= reelIndex}
          class:landed={motion !== 'resolving' || stoppedReels > reelIndex}
          data-testid={`slot-reel-${reelIndex}`}
          data-reel-phase={reelPhase(reelIndex)}
          style={`--reel-launch: ${SLOT_LAUNCH_OFFSETS_MS[reelIndex]}ms; --reel-index: ${reelIndex}`}
        >
          <div class="reel-window" class:blurred={reelMoving(reelIndex)}>
            <div class="reel-track" bind:this={trackNodes[reelIndex]}>
              {#each reel as symbol, rowIndex}
                <div
                  class:winning={motion === 'outcome' && rowIndex === 3}
                  class="symbol"
                  aria-label={`Символ ${symbol}`}
                  bind:this={symbolNodes[reelIndex * 7 + rowIndex]}>{symbol}</div
                >
              {/each}
              {#each reel as symbol}
                <div class="symbol symbol-ghost" aria-hidden="true">{symbol}</div>
              {/each}
            </div>
          </div>
        </div>
      {/each}
    </div>
    <p class="slot-status" role="status" data-testid="slot-status">{spinStatus}</p>
    <div class="payline" class:visible={motion === 'outcome'} aria-hidden="true"></div>
    <div class="machine-lights" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div>
  </section>
  <div class="slot-meta"><span><b>RTP</b> skeleton-1</span><span><b>LINES</b> 3 active</span><span><b>LIMIT</b> 10–100 JG</span></div>
  <button class="primary-action" on:click={handleSpin} disabled={motion === 'resolving'} data-testid="slot-spin">
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
  .reel { display: grid; padding: 7px 5px; border: 1px solid rgb(255 247 237 / 11%); border-radius: 14px; background: rgb(255 247 237 / 5%); container-type: inline-size; }
  /* Exactly 7 square rows: symbol side = reel content width (100cqi), 6 gaps of 5px. */
  .reel-window { overflow: hidden; border-radius: 10px; height: calc(700cqi + 30px); }
  .reel-window.blurred { filter: blur(0.45px); }
  .reel-track { display: grid; gap: 5px; will-change: transform; }
  .reel.landed .reel-track { filter: none; }
  .symbol { display: grid; place-items: center; aspect-ratio: 1 / 1; border-radius: 10px; background: rgb(11 11 17 / 66%); color: var(--ivory); font-size: clamp(20px, 7vw, 32px); font-weight: 800; line-height: 1; text-shadow: 0 2px 12px rgb(231 187 112 / 22%); }
  .symbol:nth-child(2n) { color: var(--brass-300); }
  .symbol:nth-child(3n) { color: #ed9aaf; }
  .symbol.winning { border: 1px solid var(--brass-300); background: rgb(231 187 112 / 18%); box-shadow: 0 0 22px rgb(231 187 112 / 38%); animation: winningPulse 620ms ease-in-out infinite alternate; }
  .payline { position: absolute; left: 12%; right: 12%; top: 50%; height: 2px; border-radius: 999px; background: var(--brass-300); box-shadow: 0 0 12px var(--brass-300); opacity: 0; transform: scaleX(0); transition: opacity 180ms ease, transform 420ms cubic-bezier(.16, 1, .3, 1); }
  .payline.visible { opacity: 0.86; transform: scaleX(1); }
  .machine-lights { position: absolute; right: 28px; bottom: 22px; left: 28px; display: flex; justify-content: space-between; }
  .machine-lights i { width: 5px; height: 5px; border-radius: 50%; background: var(--brass-400); box-shadow: 0 0 10px var(--brass-400); animation: lightBlink 1.3s ease-in-out infinite; }
  .machine-lights i:nth-child(2) { animation-delay: 150ms; } .machine-lights i:nth-child(3) { animation-delay: 300ms; } .machine-lights i:nth-child(4) { animation-delay: 450ms; } .machine-lights i:nth-child(5) { animation-delay: 600ms; }
  .slot-meta { display: flex; justify-content: space-between; gap: 8px; color: var(--muted); font-size: 9px; letter-spacing: 0.05em; text-transform: uppercase; }
  .slot-meta b { display: block; margin-bottom: 3px; color: var(--muted-strong); font-size: 8px; }
  .primary-action { display: flex; align-items: center; justify-content: center; gap: 10px; min-height: 52px; border: 0; border-radius: 15px; background: linear-gradient(120deg, var(--brass-300), #c98f4e); color: #2a1820; font: inherit; font-size: 14px; font-weight: 850; cursor: pointer; box-shadow: 0 10px 24px rgb(231 187 112 / 18%); transition: transform 160ms ease, filter 160ms ease; }
  .primary-action:hover { filter: brightness(1.06); transform: translateY(-2px); } .primary-action:active { transform: translateY(1px); } .primary-action:disabled { cursor: wait; filter: saturate(0.7); } .action-icon { font-size: 21px; }
  .slot-status { margin: 12px 0 0; color: var(--muted-strong); font-size: 10px; font-weight: 800; letter-spacing: 0.1em; text-transform: uppercase; }
  @keyframes winningPulse { from { transform: scale(1); } to { transform: scale(1.04); } } @keyframes lightBlink { 0%, 100% { opacity: 0.35; } 50% { opacity: 1; } }
  @media (prefers-reduced-motion: reduce) {
    .reel-window.blurred { filter: none; }
  }
</style>
