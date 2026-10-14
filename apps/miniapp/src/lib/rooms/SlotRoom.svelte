<script lang="ts">
  import { onDestroy } from 'svelte';
  import { base } from '$app/paths';
  import OperationBanner from '$lib/components/slot/OperationBanner.svelte';
  import { displayOperation, operatorForSymbol, knownOperation } from '$lib/components/slot/operations';

  import BetPicker from '$lib/components/BetPicker.svelte';
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
  export let onAction: (action: string, fields?: Record<string, unknown>) => void = () => undefined;
  // Сервер принимает целую ставку 10–100 JG за спин (room_service, slot bet).
  const BET_MIN = 10;
  const BET_MAX = 100;
  const BET_PRESETS = [10, 20, 30, 50, 100].map((value) => ({ value }));
  let bet = BET_MIN;
  $: betValid = Number.isInteger(bet) && bet >= BET_MIN && bet <= BET_MAX;
  export let resultSource: 'demo' | 'live' = 'demo';
  export let rulesetVersion = 'slot-skeleton-1';
  export let publicState:Record<string,unknown> = {};

  const legacyBases = [
    ['♣', '◆', '7', '✦', '♠', 'A', '♦'],
    ['7', '♠', '✦', 'K', '◆', 'Q', '♣'],
    ['◆', '7', '♣', '✦', 'A', '♠', '♦']
  ];
  const siegeBases = [
    ['D1','D2','D3','D4','A1','A2','A3'],
    ['D2','A1','D1','D4','W','A3','D3'],
    ['D3','W','A1','D4','D1','A2','D2']
  ];
  let frozenOperation = 'op1';
  let frozenMetadata:Record<string,unknown> = {};
  $: isSiege = rulesetVersion === 'slot-siege-1' || rulesetVersion === 'slot-siege-demo-1';
  $: reelBases = isSiege ? siegeBases : legacyBases;
  $: operationId = displayOperation(publicState,Boolean(result?.slotOutcome),isSpinning,frozenOperation);

  let slotPhase: SlotPhase = 'idle';
  let elapsedMs = 0;
  let startedAt = 0;
  let spinSeq = 0;
  let reducedMotion = false;
  let reelOffsets = [0, 0, 0];
  let ticker: number | null = null;

  $: slotOutcome = result?.slotOutcome ?? null;
  $: lastResult = publicState.last_result;
  $: bannerState = slotOutcome && typeof lastResult === 'object' && lastResult !== null ? lastResult as Record<string,unknown> : isSpinning ? frozenMetadata : publicState;
  $: confirmedReels = slotOutcome?.reels?.length === 3 ? slotOutcome.reels : reelBases;
  $: reelTracks = reelBases.map((base, reelIndex) =>
    buildReelTrack(base, confirmedReels[reelIndex] ?? base)
  );
  $: reelPhases = reelBases.map((_, reelIndex): SlotReelPhase =>
    slotPhase === 'idle' ? 'idle' : getSlotReelPhase(reelIndex, elapsedMs, reducedMotion)
  );
  $: stoppedReels = reelPhases.filter((phase) => phase === 'landed').length;
  $: winningRows = slotOutcome?.winningRows ?? [];
  // A reconnect snapshot may restore parent motion while the local reels still travel.
  $: showConfirmedGrid = Boolean(slotOutcome) && (slotPhase === 'settled' || (spinSeq === 0 && (motion === 'outcome' || motion === 'settle')));
  $: if (spinSeq === 0 && slotOutcome && (motion === 'outcome' || motion === 'settle')) renderFrame(SLOT_SPIN_DURATION);
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
    frozenOperation = knownOperation(publicState.operation_id) ? publicState.operation_id : 'op1';
    frozenMetadata = {...publicState};
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
    if (action === 'spin' && !betValid) return;
    startSpin();
    onAction(action, action === 'spin' ? { bet } : {});
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

  $: isLive = resultSource === 'live';

  function phaseLabel(phase: SlotPhase) {
    if (phase === 'spinning') return 'TRAVEL · 60 FPS';
    if (phase === 'stopping-left') return 'LANDING · LEFT REEL';
    if (phase === 'stopping-center') return 'LANDING · CENTER REEL';
    if (phase === 'stopping-right') return 'LANDING · RIGHT REEL';
    if (phase === 'settled') return isLive ? 'SETTLED · SERVER GRID' : 'SETTLED · DEMO GRID';
    return isLive ? 'READY · SERVER-FIRST' : 'READY · DEMO';
  }

  onDestroy(cancelTicker);
</script>

<div class="game-room slot-room" class:siege={isSiege}>
  <div class="room-intro">
    <div>
      <span class="room-kicker">{isSiege ? 'SIEGE · 3×7' : 'THREE REELS · SEVEN ROWS'}</span>
      <h2>{isSiege ? 'Siege' : 'Однорукий бандит'}</h2>
      <p>{isLive ? 'Полная прокрутка барабанов. Сервер подтверждает сетку, клиент показывает движение.' : 'Демо-прокрутка барабанов. Клиент показывает сетку и движение; сервер не подтверждает исход.'}</p>
    </div>
    <span class="bet-chip" data-testid="slot-bet-chip">{betValid ? bet : BET_MIN} JG</span>
  </div>
  {#if isSiege}<OperationBanner {operationId} publicState={bannerState} />{/if}

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
                  data-symbol={symbol}
                >{#if isSiege && operatorForSymbol(operationId,symbol)}<img class="operator-face" src={`${base}/slot/faces/${operatorForSymbol(operationId,symbol)}.webp`} alt={operatorForSymbol(operationId,symbol) ?? symbol} />{:else}{symbol}{/if}</div>
              {/each}
            </div>
          </div>
        </div>
      {/each}
      {#if isSiege && showConfirmedGrid && slotOutcome?.winningLines?.length}
        <svg class="beams" viewBox="0 0 300 700" preserveAspectRatio="none" aria-hidden="true" data-testid="slot-winning-beams">
          {#each slotOutcome.winningLines as line}<polyline points={line.rows.map((row,i)=>`${50+i*100},${50+row*100}`).join(' ')} />{/each}
        </svg>
      {:else if isSiege && showConfirmedGrid && winningRows.length}
        <svg class="beams" viewBox="0 0 300 700" preserveAspectRatio="none" aria-hidden="true" data-testid="slot-winning-beams">{#each winningRows as row}<polyline points={`50,${50+row*100} 150,${50+row*100} 250,${50+row*100}`} />{/each}</svg>
      {/if}
    </div>

    <div class="payline" class:visible={showConfirmedGrid && !isSiege} data-testid="slot-payline" aria-hidden="true"></div>
    {#if showConfirmedGrid}
      <div class="confirmed-grid" data-testid="slot-confirmed-grid" aria-live="polite">
        <span>{isLive ? 'SERVER GRID CONFIRMED' : 'DEMO GRID · CLIENT RESULT'}</span>
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
    <span><b>RULESET</b> {isSiege ? 'Siege' : 'skeleton-1'}</span>
    <span><b>LINES</b> 3 active</span>
    <span><b>MOTION</b> wave · 60 fps</span>
  </div>

  {#if !isSiege && slotOutcome && hasFreeSpins(slotOutcome) && showConfirmedGrid}
    <section class="free-spins-panel" data-testid="slot-free-spins" aria-label="Доступны бесплатные вращения">
      <div>
        <span class="free-spins-kicker">{isLive ? 'BONUS STATE · SERVER CONFIRMED' : 'DEMO BONUS STATE · CLIENT RESULT'}</span>
        <strong>{slotOutcome.freeSpinsRemaining} FREE SPINS</strong>
      </div>
      <button class="free-spin-action" on:click={() => handleAction('free-spin')}>
        Запустить Free Spin <span aria-hidden="true">↻</span>
      </button>
    </section>
  {/if}

  <div class="slot-bet">
    <BetPicker bind:value={bet} min={BET_MIN} max={BET_MAX} presets={BET_PRESETS} disabled={motion === 'resolving' || isSpinning} inputId="slot-bet" inputTestId="slot-bet" />
  </div>
  <button class="primary-action" on:click={() => handleAction('spin')} disabled={motion === 'resolving' || isSpinning || !betValid} data-testid="slot-spin">
    <span class="action-icon" aria-hidden="true">↻</span>
    {isSpinning ? 'Барабаны останавливаются…' : motion === 'resolving' ? (isLive ? 'Ждём сервер…' : 'Готовим демо…') : betValid ? `Крутить за ${bet} JG` : 'Выберите ставку'}
  </button>
  <ResultBand {result} {motion} source={resultSource} />
  {#if isSiege}<details class="sources"><summary>Источники изображений</summary><p>© Ubisoft Entertainment. Некоммерческий фанатский интерфейс по решению владельца; общая лицензия не заявляется.</p><a href={`${base}/slot/sources.json`} target="_blank" rel="noreferrer">Оперативники и источники портретов</a></details>{/if}
</div>

<style>
  .siege{--siege-ice:#bed0dc;background:#0c1115;padding:12px;color:#e9eff3;border:1px solid #748a97;padding-bottom:max(12px,env(safe-area-inset-bottom))}.siege h2{font-weight:300;letter-spacing:.12em;text-transform:uppercase}.siege .room-kicker,.siege .bet-chip,.siege .slot-status strong{color:var(--siege-ice)}.siege .slot-machine{border-color:#687c87;border-radius:4px;background:radial-gradient(ellipse at 50% 0,#8babb633,transparent 65%),linear-gradient(110deg,#ffffff09,transparent 30%,#ffffff09 65%,transparent),#10171c;box-shadow:inset 0 -80px 60px -60px #c3d5de44}.siege .machine-rim,.siege .reel{border-color:#748794;border-radius:2px}.siege .symbol{border-radius:2px;background:#070d11;overflow:hidden}.operator-face{width:100%;height:100%;object-fit:contain;filter:grayscale(1);transition:filter .2s}.winning .operator-face{filter:none}.siege .symbol.winning{background:#344a56;color:#fff;box-shadow:0 0 12px #d5e8f266}.siege .primary-action{border-radius:3px;background:#d1dce3;color:#10171c;box-shadow:none}.siege .machine-lights i{background:#b9d1de}.beams{position:absolute;top:62px;left:10px;width:calc(100% - 20px);height:calc(7 * (clamp(34px,8vw,52px) + 6px) - 6px);pointer-events:none;filter:drop-shadow(0 0 5px #deefff);z-index:2}.beams polyline{fill:none;stroke:#ecf6fc;stroke-width:2;stroke-dasharray:700;stroke-dashoffset:700;animation:beam .6s ease forwards}.sources{font-size:11px;color:#d1dce3}.sources summary{min-height:44px;display:flex;align-items:center;cursor:pointer}.sources a{color:#c7e5f4}.sources p{margin:8px 0}.siege button:focus-visible,.sources a:focus-visible,.sources summary:focus-visible{outline:3px solid #fff;outline-offset:3px}@keyframes beam{to{stroke-dashoffset:0}}@media(prefers-reduced-motion:reduce){.beams polyline{animation:none;stroke-dashoffset:0}.operator-face{transition:none}}
  .game-room { position: relative; z-index: 1; display: grid; gap: 18px; }
  .siege .reel-grid{position:relative}.siege .symbol.tone-brass,.siege .symbol.tone-pink{background:#070d11;color:#e9eff3}.siege .symbol.winning{background:#344a56}.siege .beams{top:8px;left:0;width:100%}
  .room-intro { display: flex; justify-content: space-between; gap: 18px; }
  .room-kicker { color: var(--brass-300); font-size: 9px; font-weight: 800; letter-spacing: 0.14em; }
  h2 { margin: 6px 0 5px; font-size: clamp(25px, 7vw, 36px); letter-spacing: -0.06em; }
  p { max-width: 280px; margin: 0; color: var(--muted); font-size: 12px; line-height: 1.45; }
  .slot-bet { padding: 12px; border: 1px solid rgb(231 187 112 / 22%); border-radius: 12px; background: rgb(255 247 237 / 3%); --bet-accent: var(--brass-300); }
  .siege .slot-bet { border-color: #687c87; border-radius: 4px; --bet-accent: #d1dce3; --bet-line: #748a97; --bet-ink: #e9eff3; }
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
