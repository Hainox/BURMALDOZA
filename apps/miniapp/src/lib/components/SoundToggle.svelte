<script lang="ts">
  // Переключатель звука в шапке: виден всегда (docs/Sound-Design.md, принцип «вежливость в чате»).
  import { base } from '$app/paths';
  import { sound, soundEnabled } from '$lib/audio/sound';
</script>

<button
  class="sound-toggle"
  type="button"
  on:click={() => void sound.toggle()}
  aria-pressed={$soundEnabled}
  aria-label={$soundEnabled ? 'Выключить звук' : 'Включить звук'}
  title={$soundEnabled ? 'Звук включён' : 'Звук выключен'}
  data-testid="sound-toggle"
>
  <img src={`${base}/hub/icons/${$soundEnabled ? 'volume' : 'volume-off'}.svg`} width="22" height="22" alt="" />
</button>

<style>
  .sound-toggle { display: grid; place-items: center; flex-shrink: 0; width: 44px; height: 44px; border: 1px solid #b8955d; border-radius: 50%; background: #0a0e14c9; cursor: pointer; transition: transform .2s ease, opacity .2s ease; }
  .sound-toggle[aria-pressed='true'] { background: #302319; }
  .sound-toggle:active { transform: scale(.94); }
  .sound-toggle:focus-visible { outline: 2px solid #fff0bc; outline-offset: 3px; }
  @media (prefers-reduced-motion: reduce) { .sound-toggle { transition: none; } }
</style>
