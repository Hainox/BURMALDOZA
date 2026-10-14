<script lang="ts">
  import { getContext, onDestroy } from 'svelte';
  import type { MotionState } from '$lib/game/motion';
  import type { RoomResult } from '$lib/state/room.svelte';

  export let result: RoomResult | null = null;
  export let motion: MotionState = 'idle';
  export let source: 'demo' | 'live' = 'demo';
  export let compact = false;
  const quiet = getContext<() => boolean>('room-motion-quiet') ?? (() => false);
  let displayedAmount = 0;
  let amountKey: RoomResult | null = null;
  let counterFrame: number | null = null;
  function countAmount(confirmed: boolean, next: RoomResult | null) {
    if (!confirmed || next?.amount === undefined) {
      if (counterFrame !== null) cancelAnimationFrame(counterFrame);
      counterFrame = null;
      amountKey = null;
      displayedAmount = 0;
      return;
    }
    if (next === amountKey) return;
    amountKey = next;
    if (counterFrame !== null) cancelAnimationFrame(counterFrame);
    const target = next.amount;
    if (!next.slotOutcome || typeof window === 'undefined' || quiet() || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      displayedAmount = target;
      counterFrame = null;
      return;
    }
    const start = performance.now();
    displayedAmount = 0;
    const tick = (now: number) => {
      const progress = quiet() ? 1 : Math.min(1, (now - start) / 650);
      displayedAmount = Math.round(target * (1 - (1 - progress) ** 3));
      counterFrame = progress < 1 ? requestAnimationFrame(tick) : null;
    };
    counterFrame = requestAnimationFrame(tick);
  }

  $: hasSettledResult = result !== null && (motion === 'outcome' || motion === 'settle');
  $: isServerConfirmed = hasSettledResult && source === 'live';
  $: countAmount(hasSettledResult, result);
  onDestroy(() => { if (counterFrame !== null) cancelAnimationFrame(counterFrame); });
  $: resultKicker = isServerConfirmed
    ? 'SERVER CONFIRMED · LIVE'
    : hasSettledResult
      ? 'DEMO ROUND · БЕЗ СЕРВЕРНОГО ПОДТВЕРЖДЕНИЯ'
      : result
        ? `RESOLVING · ${source === 'live' ? 'SERVER' : 'DEMO'} RESULT`
        : 'ИТОГ РАУНДА';
  $: resultHeadline = hasSettledResult
    ? result?.headline
    : result
      ? source === 'live'
        ? 'Ожидаем подтверждённую остановку'
        : 'Завершаем демо-движение'
      : 'Готово к следующему раунду';
  $: resultDetail = hasSettledResult
    ? result?.detail
    : result
      ? source === 'live'
        ? 'Исход получен, но выплата появится после завершения движения.'
        : 'Демо-исход появится после завершения движения.'
      : 'Исход появится после следующего раунда.';
</script>

<section class="result-band" class:compact class:settled={hasSettledResult} data-testid="result-band" aria-live="polite">
  <span class="result-kicker">{resultKicker}</span>
  <div class="result-row">
    <div>
      <strong>{resultHeadline}</strong>
      <p>{resultDetail}</p>
    </div>
    {#if hasSettledResult && result?.amount !== undefined}
      <span class="result-amount" data-testid="result-amount" aria-label={`${result.amount} JG`}>{displayedAmount > 0 ? '+' : ''}{displayedAmount} <small>JG</small></span>
    {:else if result}
      <span class="result-state" aria-hidden="true"><i></i><i></i><i></i></span>
    {/if}
  </div>
  {#if isServerConfirmed && result?.slotOutcome}
    <span class="confirmed-balance" data-testid="confirmed-balance">BALANCE {result.slotOutcome.balance} JG</span>
  {/if}
</section>

<style>
  .result-band.compact { padding: 7px 10px; }
  .compact .result-row { display: none; }
  .result-band { display: grid; gap: 5px; padding: 10px 12px; border: 1px solid rgb(255 247 237 / 14%); border-radius: 16px; background: rgb(10 12 16 / 90%); box-shadow: 0 14px 40px rgb(0 0 0 / 40%); }
  .result-band.settled { border-color: rgb(231 187 112 / 60%); background: linear-gradient(105deg, rgb(231 187 112 / 16%), rgb(10 12 16 / 78%) 60%); box-shadow: 0 0 34px rgb(213 144 59 / 26%), 0 14px 40px rgb(0 0 0 / 40%); animation: resultConfirmIn 460ms var(--ease-enter) both; }
  .result-kicker { color: var(--brass-300); font-size: 9px; font-weight: 800; letter-spacing: 0.15em; }
  .result-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  strong { font-size: 15px; }
  p { margin: 3px 0 0; color: #c9c3bb; font-size: 11px; }
  .result-amount { color: #ffd98f; font-size: 22px; font-weight: 800; white-space: nowrap; text-shadow: 0 0 16px rgb(239 192 107 / 55%); animation: amountPop 520ms var(--ease-spring) both; }
  .result-amount small { font-size: 10px; letter-spacing: 0.12em; }
  .confirmed-balance { color: var(--success); font-size: 9px; font-weight: 800; letter-spacing: 0.1em; }
  /* Ожидание исхода: три бегущие точки вместо служебного RESOLVING. */
  .result-state { display: inline-flex; gap: 5px; }
  .result-state i { width: 6px; height: 6px; border-radius: 50%; background: var(--brass-300); animation: waitDot 1s ease-in-out infinite; }
  .result-state i:nth-child(2) { animation-delay: .15s; }
  .result-state i:nth-child(3) { animation-delay: .3s; }
  @keyframes resultConfirmIn { from { opacity: .6; transform: translate3d(0, 8px, 0) scale(.985); } to { opacity: 1; transform: none; } }
  @keyframes amountPop { 0% { opacity: 0; transform: scale(.6); } 70% { opacity: 1; transform: scale(1.12); } 100% { transform: scale(1); } }
  @keyframes waitDot { 0%, 100% { opacity: .25; transform: translateY(0); } 50% { opacity: 1; transform: translateY(-3px); } }
  @media (prefers-reduced-motion: reduce) { .result-band, .result-amount, .result-state i { animation: none; } }
</style>
