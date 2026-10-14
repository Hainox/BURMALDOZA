<script lang="ts" module>
  export type BetPreset = { value: number; label?: string };
</script>

<script lang="ts">
  // Выбор суммы: пять быстрых вариантов и своя сумма слайдером или вводом.
  // Только интерфейс: допустимость суммы и списание проверяет сервер.
  export let value: number;
  export let min: number;
  export let max: number;
  export let presets: BetPreset[] = [];
  export let disabled = false;
  export let label = 'Ставка';
  export let inputId: string;
  export let inputTestId: string | undefined = undefined;
  export let inputLabel: string | undefined = undefined;
  export let testId: string | undefined = undefined;

  $: options = presets
    .map((preset) => ({ ...preset, value: Math.round(preset.value) }))
    .filter((preset, index, list) => preset.value >= min && preset.value <= max && list.findIndex((other) => other.value === preset.value) === index)
    .slice(0, 5);
  $: rangeValue = Number.isFinite(value) ? Math.min(max, Math.max(min, value)) : min;

  function pick(next: number) {
    if (!disabled) value = next;
  }

  function slide(event: Event) {
    value = Number((event.currentTarget as HTMLInputElement).value);
  }
</script>

<div class="bet-picker" data-testid={testId}>
  <div class="bet-head">
    <label for={inputId}>{label} · {min}–{max} JG</label>
    <input
      id={inputId}
      data-testid={inputTestId}
      type="number"
      {min}
      {max}
      step="1"
      inputmode="numeric"
      aria-label={inputLabel}
      bind:value
      {disabled}
    />
  </div>
  {#if options.length}
    <div class="bet-presets" role="group" aria-label="Быстрый выбор суммы">
      {#each options as preset (preset.value)}
        <button type="button" on:click={() => pick(preset.value)} {disabled} aria-pressed={value === preset.value}>
          {#if preset.label}<small>{preset.label}</small>{/if}
          <b>{preset.value}</b>
        </button>
      {/each}
    </div>
  {/if}
  <input
    class="bet-range"
    type="range"
    {min}
    {max}
    step="1"
    value={rangeValue}
    on:input={slide}
    aria-label={`${label}: своя сумма`}
    aria-valuetext={`${rangeValue} JG`}
    {disabled}
  />
</div>

<style>
  .bet-picker { --bet-accent-resolved: var(--bet-accent, #e7bb70); --bet-line-resolved: var(--bet-line, rgb(255 247 237 / 18%)); --bet-ink-resolved: var(--bet-ink, #f4ece0); display: grid; gap: 10px; color: var(--bet-ink-resolved); }
  .bet-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .bet-head label { font-size: 11px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; opacity: 0.8; }
  .bet-head input { width: 96px; min-height: 44px; padding: 8px 10px; border: 1px solid var(--bet-line-resolved); border-radius: 10px; background: rgb(0 0 0 / 35%); color: inherit; font: inherit; font-size: 15px; font-weight: 800; text-align: center; }
  .bet-presets { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 6px; }
  .bet-presets button { display: grid; place-items: center; gap: 1px; min-height: 44px; padding: 4px 2px; border: 1px solid var(--bet-line-resolved); border-radius: 10px; background: rgb(255 255 255 / 5%); color: var(--bet-ink-resolved); font: inherit; cursor: pointer; }
  .bet-presets b { color: inherit; font-size: 13px; font-weight: 800; }
  .bet-presets small { font-size: 9px; opacity: 0.7; white-space: nowrap; }
  .bet-presets button[aria-pressed='true'] { border-color: var(--bet-accent-resolved); color: var(--bet-accent-resolved); background: rgb(255 255 255 / 9%); }
  .bet-presets button:disabled { cursor: default; opacity: 0.5; }
  .bet-range { width: 100%; min-height: 44px; margin: 0; accent-color: var(--bet-accent-resolved); cursor: pointer; }
  .bet-range:disabled { cursor: default; opacity: 0.5; }
  .bet-picker :focus-visible { outline: 2px solid var(--bet-accent-resolved); outline-offset: 2px; }
</style>
