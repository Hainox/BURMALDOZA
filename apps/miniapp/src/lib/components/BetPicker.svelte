<script lang="ts" module>
  export type BetPreset = { value: number; label?: string };
</script>

<script lang="ts">
  import { sound } from '$lib/audio/sound';
  // Выбор суммы: пять стандартных вариантов и отдельно своя сумма — слайдер и ввод до max.
  // Только интерфейс: допустимость суммы и списание проверяет сервер.
  export let value: number;
  export let min: number;
  export let max: number;
  export let presets: BetPreset[] = [];
  export let disabled = false;
  export let label = 'Ставка';
  export let customLabel = 'Своя ставка';
  export let inputId: string;
  export let inputTestId: string | undefined = undefined;
  export let inputLabel: string | undefined = undefined;
  export let testId: string | undefined = undefined;

  // Если баланс ниже минимума, диапазон схлопывается в минимум, а кнопку действия выключает комната.
  $: top = Math.max(min, Math.floor(max));
  $: options = presets
    .map((preset) => ({ ...preset, value: Math.round(preset.value) }))
    .filter((preset, index, list) => preset.value >= min && list.findIndex((other) => other.value === preset.value) === index)
    .slice(0, 5);
  $: rangeValue = Number.isFinite(value) ? Math.min(top, Math.max(min, value)) : min;

  function pick(next: number) {
    if (!disabled && next <= top) { value = next; sound.cue('tap'); }
  }

  function slide(event: Event) {
    value = Number((event.currentTarget as HTMLInputElement).value);
  }
</script>

<div class="bet-picker" data-testid={testId}>
  {#if options.length}
    <div class="bet-group">
      <span class="bet-caption">{label}</span>
      <div class="bet-presets" role="group" aria-label={label}>
        {#each options as preset (preset.value)}
          <button type="button" on:click={() => pick(preset.value)} disabled={disabled || preset.value > top} aria-pressed={value === preset.value}>
            {#if preset.label}<small>{preset.label}</small>{/if}
            <b>{preset.value}</b>
          </button>
        {/each}
      </div>
    </div>
  {/if}
  <div class="bet-custom">
    <div class="bet-head">
      <label for={inputId}>{customLabel} · до {top.toLocaleString('ru-RU')} JG</label>
      <input
        id={inputId}
        data-testid={inputTestId}
        type="number"
        {min}
        max={top}
        step="1"
        inputmode="numeric"
        aria-label={inputLabel}
        bind:value
        {disabled}
      />
    </div>
    <input
      class="bet-range"
      type="range"
      {min}
      max={top}
      step="1"
      value={rangeValue}
      on:input={slide}
      aria-label={`${customLabel}: от ${min} до ${top} JG`}
      aria-valuetext={`${rangeValue} JG`}
      {disabled}
    />
  </div>
</div>

<style>
  .bet-picker { --bet-accent-resolved: var(--bet-accent, #e7bb70); --bet-line-resolved: var(--bet-line, rgb(255 247 237 / 18%)); --bet-ink-resolved: var(--bet-ink, #f4ece0); display: grid; gap: 12px; color: var(--bet-ink-resolved); }
  .bet-group { display: grid; gap: 8px; }
  .bet-caption, .bet-head label { font-size: 11px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; opacity: 0.8; }
  .bet-presets { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 6px; }
  .bet-presets button { display: grid; place-items: center; gap: 1px; min-height: 44px; padding: 4px 2px; border: 1px solid var(--bet-line-resolved); border-radius: 10px; background: rgb(255 255 255 / 5%); color: var(--bet-ink-resolved); font: inherit; cursor: pointer; }
  .bet-presets b { color: inherit; font-size: 13px; font-weight: 800; }
  .bet-presets small { font-size: 9px; opacity: 0.7; white-space: nowrap; }
  .bet-presets button[aria-pressed='true'] { border-color: var(--bet-accent-resolved); color: var(--bet-accent-resolved); background: rgb(255 255 255 / 9%); }
  .bet-presets button:disabled { cursor: default; opacity: 0.4; }
  .bet-custom { display: grid; gap: 4px; padding-top: 12px; border-top: 1px solid var(--bet-line-resolved); }
  .bet-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .bet-head input { width: 104px; min-height: 44px; padding: 8px 10px; border: 1px solid var(--bet-line-resolved); border-radius: 10px; background: rgb(0 0 0 / 35%); color: inherit; font: inherit; font-size: 15px; font-weight: 800; text-align: center; }
  .bet-range { width: 100%; min-height: 44px; margin: 0; accent-color: var(--bet-accent-resolved); cursor: pointer; }
  .bet-range:disabled { cursor: default; opacity: 0.5; }
  .bet-picker :focus-visible { outline: 2px solid var(--bet-accent-resolved); outline-offset: 2px; }
</style>
