<script lang="ts">
  import type { MotionState } from '$lib/game/motion';
  import type { RoomResult } from '$lib/state/room.svelte';

  export let result: RoomResult | null = null;
  export let motion: MotionState = 'idle';
  export let source: 'demo' | 'live' = 'demo';

  $: hasSettledResult = result !== null && (motion === 'outcome' || motion === 'settle');
  $: isServerConfirmed = hasSettledResult && source === 'live';
  $: resultKicker = isServerConfirmed
    ? 'SERVER CONFIRMED · LIVE'
    : hasSettledResult
      ? 'DEMO ROUND · БЕЗ СЕРВЕРНОГО ПОДТВЕРЖДЕНИЯ'
      : result
        ? `RESOLVING · ${source === 'live' ? 'SERVER' : 'DEMO'} RESULT`
        : 'RESULT BAND';
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

<section class="result-band" class:settled={hasSettledResult} data-testid="result-band" aria-live="polite">
  <span class="result-kicker">{resultKicker}</span>
  <div class="result-row">
    <div>
      <strong>{resultHeadline}</strong>
      <p>{resultDetail}</p>
    </div>
    {#if hasSettledResult && result?.amount !== undefined}
      <span class="result-amount">{result.amount > 0 ? '+' : ''}{result.amount} <small>JG</small></span>
    {:else}
      <span class="result-state">{hasSettledResult ? motion.toUpperCase() : 'RESOLVING'}</span>
    {/if}
  </div>
  {#if isServerConfirmed && result?.slotOutcome}
    <span class="confirmed-balance" data-testid="confirmed-balance">BALANCE {result.slotOutcome.balance} JG</span>
  {/if}
</section>

<style>
  .result-band { display: grid; gap: 8px; padding: 13px 15px; border: 1px solid var(--line); border-radius: var(--radius-md); background: rgb(255 247 237 / 4%); transition: border-color 240ms var(--ease-smooth), background 240ms var(--ease-smooth), transform 240ms var(--ease-smooth); will-change: transform; }
  .result-band.settled { border-color: rgb(231 187 112 / 48%); background: linear-gradient(105deg, rgb(231 187 112 / 13%), rgb(143 53 89 / 10%)); transform: translateY(-1px); }
  .result-band.settled { animation: resultConfirmIn 420ms var(--ease-enter) both; }
  .result-kicker { color: var(--brass-300); font-size: 9px; font-weight: 800; letter-spacing: 0.15em; }
  .result-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  strong { font-size: 14px; }
  p { margin: 3px 0 0; color: var(--muted); font-size: 11px; }
  .result-amount { color: var(--brass-300); font-size: 19px; font-weight: 800; white-space: nowrap; }
  .result-amount small { font-size: 10px; letter-spacing: 0.12em; }
  .confirmed-balance { color: var(--success); font-size: 9px; font-weight: 800; letter-spacing: 0.1em; }
  .result-state { color: var(--muted); font-size: 10px; font-weight: 800; letter-spacing: 0.1em; }
  @keyframes resultConfirmIn { from { opacity: .68; transform: translate3d(0, 7px, 0); } to { opacity: 1; transform: translate3d(0, -1px, 0); } }
</style>
