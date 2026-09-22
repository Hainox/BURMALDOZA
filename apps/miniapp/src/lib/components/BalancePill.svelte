<script lang="ts">
  export let balance = 1250;
  export let currencyCode = 'JOKERGEM';
  export let connection: 'demo' | 'connecting' | 'connected' | 'syncing' | 'offline' = 'demo';

  const connectionLabel = {
    demo: 'DEMO',
    connecting: 'CONNECTING',
    connected: 'LIVE',
    syncing: 'SYNCING',
    offline: 'OFFLINE'
  } as const;
</script>

<div class="balance-pill" data-testid="balance-pill" aria-label={`Баланс ${balance} ${currencyCode}`}>
  <span class="connection-dot" class:live={connection === 'connected'}></span>
  <span class="balance-copy">
    <span class="balance-label">Баланс · {connectionLabel[connection]}</span>
    <strong>{balance.toLocaleString('ru-RU')} <span>{currencyCode}</span></strong>
  </span>
  <span class="gem-mark" aria-hidden="true">✦</span>
</div>

<style>
  .balance-pill {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    min-width: 158px;
    padding: 9px 12px;
    border: 1px solid var(--line);
    border-radius: 999px;
    background: rgb(255 247 237 / 7%);
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 8%);
  }

  .connection-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--brass-400);
    box-shadow: 0 0 0 4px rgb(231 187 112 / 12%);
  }

  .connection-dot.live {
    background: var(--success);
    box-shadow: 0 0 0 4px rgb(142 228 182 / 12%);
  }

  .balance-copy {
    display: grid;
    gap: 2px;
  }

  .balance-label {
    color: var(--muted);
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  strong {
    color: var(--ivory);
    font-size: 14px;
    letter-spacing: -0.02em;
  }

  strong span {
    color: var(--brass-300);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
  }

  .gem-mark {
    margin-left: auto;
    color: var(--brass-300);
    font-size: 18px;
    animation: gemPulse 2.8s ease-in-out infinite;
    will-change: transform, opacity;
  }

  @keyframes gemPulse {
    0%,
    100% { transform: scale(0.9) rotate(0deg); opacity: 0.68; }
    50% { transform: scale(1.08) rotate(18deg); opacity: 1; }
  }
</style>
