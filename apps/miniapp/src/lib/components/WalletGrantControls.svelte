<script lang="ts">
  import { ApiClient, ApiError, type ApiLedgerResult } from '$lib/api/client';

  export let apiClient: ApiClient;
  export let live = false;
  export let balance = 0;
  export let onConfirmed: (result: ApiLedgerResult) => void = () => undefined;

  let dailyPending = false;
  let reliefPending = false;
  let dailyMessage: string | null = null;
  let reliefMessage: string | null = null;
  let dailyFailed = false;
  let reliefFailed = false;

  function cooldownCopy(kind: 'daily' | 'relief'): string {
    return kind === 'daily'
      ? 'Дневной бонус уже получен: следующая выдача через 24 часа.'
      : 'Relief пока недоступен: баланс выше 50 или не прошло 72 часа.';
  }

  async function claim(kind: 'daily' | 'relief') {
    if (!live) return;
    if (kind === 'daily' ? dailyPending : reliefPending) return;
    if (kind === 'daily') {
      dailyPending = true;
      dailyMessage = null;
      dailyFailed = false;
    } else {
      reliefPending = true;
      reliefMessage = null;
      reliefFailed = false;
    }
    try {
      const confirmed =
        kind === 'daily'
          ? await apiClient.claimDailyBonus(crypto.randomUUID())
          : await apiClient.claimReliefGrant(crypto.randomUUID());
      if (kind === 'daily') {
        dailyMessage = `Начислено +${confirmed.delta} JG · баланс ${confirmed.balance_after} JG.`;
      } else {
        reliefMessage = `Начислено +${confirmed.delta} JG · баланс ${confirmed.balance_after} JG.`;
      }
      onConfirmed(confirmed);
    } catch (error) {
      const status = error instanceof ApiError ? error.status : null;
      if (status === 409) {
        if (kind === 'daily') dailyMessage = cooldownCopy('daily');
        else reliefMessage = cooldownCopy('relief');
      } else {
        const copy = error instanceof Error ? error.message : 'Сервер не подтвердил выдачу';
        if (kind === 'daily') {
          dailyMessage = `Не удалось получить бонус: ${copy}. Повторите позже.`;
          dailyFailed = true;
        } else {
          reliefMessage = `Не удалось получить помощь: ${copy}. Повторите позже.`;
          reliefFailed = true;
        }
      }
    } finally {
      if (kind === 'daily') dailyPending = false;
      else reliefPending = false;
    }
  }
</script>

{#if live}
  <section class="grant-panel" data-testid="wallet-grants" aria-label="Выдачи Jokergem">
    <div class="grant-row">
      <div class="grant-copy">
        <strong>Daily +250 JG</strong>
        <small>Раз в 24 часа · баланс только из ответа сервера</small>
      </div>
      <button
        type="button"
        data-testid="wallet-daily-claim"
        disabled={dailyPending}
        on:click={() => void claim('daily')}
      >
        {dailyPending ? 'Запрашиваем…' : 'Получить daily'}
      </button>
    </div>
    {#if dailyMessage}
      <p class="grant-message" class:error={dailyFailed} data-testid="wallet-daily-message" role={dailyFailed ? 'alert' : 'status'}>
        {dailyMessage}
      </p>
    {/if}
    <div class="grant-row">
      <div class="grant-copy">
        <strong>Relief +300 JG</strong>
        <small>Баланс ниже 50 · раз в 72 часа · текущий {balance} JG</small>
      </div>
      <button
        type="button"
        data-testid="wallet-relief-claim"
        disabled={reliefPending}
        on:click={() => void claim('relief')}
      >
        {reliefPending ? 'Запрашиваем…' : 'Получить relief'}
      </button>
    </div>
    {#if reliefMessage}
      <p class="grant-message" class:error={reliefFailed} data-testid="wallet-relief-message" role={reliefFailed ? 'alert' : 'status'}>
        {reliefMessage}
      </p>
    {/if}
  </section>
{/if}

<style>
  .grant-panel {
    display: grid;
    gap: 12px;
    padding: 13px 14px;
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    background: rgb(255 247 237 / 4%);
  }
  .grant-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .grant-copy {
    display: grid;
    gap: 3px;
  }
  .grant-copy strong {
    color: var(--ivory);
    font-size: 13px;
  }
  .grant-copy small {
    color: var(--muted);
    font-size: 11px;
    line-height: 1.4;
  }
  .grant-row button {
    min-height: 44px;
    min-width: 148px;
    padding: 8px 14px;
    border: 1px solid rgb(231 187 112 / 55%);
    border-radius: 12px;
    background: linear-gradient(120deg, var(--brass-300), #c98f4e);
    color: #2a1820;
    font: inherit;
    font-size: 13px;
    font-weight: 850;
    cursor: pointer;
  }
  .grant-row button:disabled {
    cursor: wait;
    opacity: 0.72;
  }
  .grant-message {
    margin: 0;
    color: var(--success);
    font-size: 11px;
    line-height: 1.45;
  }
  .grant-message.error {
    color: #ff9cae;
  }
  @media (max-width: 390px) {
    .grant-row {
      flex-direction: column;
      align-items: stretch;
    }
    .grant-row button {
      width: 100%;
    }
  }
</style>
