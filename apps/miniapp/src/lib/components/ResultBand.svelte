<script lang="ts">
  import type { MotionState } from '$lib/game/motion';
  import type { RoomResult } from '$lib/state/room.svelte';

  export let result: RoomResult | null = null;
  export let motion: MotionState = 'idle';

  $: isConfirmed = result !== null && (motion === 'outcome' || motion === 'settle');
</script>

<section class="result-band" class:confirmed={isConfirmed} data-testid="result-band" aria-live="polite">
  <span class="result-kicker">{isConfirmed ? 'SERVER CONFIRMED · DEMO' : result ? 'RESOLVING · SERVER RESULT' : 'RESULT BAND'}</span>
  <div class="result-row">
    <div>
      <strong>{isConfirmed ? result?.headline : result ? 'Ожидаем подтверждённую остановку' : 'Готово к следующему раунду'}</strong>
      <p>{isConfirmed ? result?.detail : 'Исход получен, но выплата появится после завершения движения.'}</p>
    </div>
    {#if isConfirmed && result?.amount !== undefined}
      <span class="result-amount">{result.amount > 0 ? '+' : ''}{result.amount} <small>JG</small></span>
    {:else}
      <span class="result-state">{isConfirmed ? motion.toUpperCase() : 'RESOLVING'}</span>
    {/if}
  </div>
</section>

<style>
  .result-band { display: grid; gap: 8px; padding: 13px 15px; border: 1px solid var(--line); border-radius: var(--radius-md); background: rgb(255 247 237 / 4%); transition: border-color 240ms ease, background 240ms ease, transform 240ms ease; }
  .result-band.confirmed { border-color: rgb(231 187 112 / 48%); background: linear-gradient(105deg, rgb(231 187 112 / 13%), rgb(143 53 89 / 10%)); transform: translateY(-1px); }
  .result-kicker { color: var(--brass-300); font-size: 9px; font-weight: 800; letter-spacing: 0.15em; }
  .result-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  strong { font-size: 14px; }
  p { margin: 3px 0 0; color: var(--muted); font-size: 11px; }
  .result-amount { color: var(--brass-300); font-size: 19px; font-weight: 800; white-space: nowrap; }
  .result-amount small { font-size: 10px; letter-spacing: 0.12em; }
  .result-state { color: var(--muted); font-size: 10px; font-weight: 800; letter-spacing: 0.1em; }
</style>
