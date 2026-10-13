<script lang="ts">
  import { onDestroy } from 'svelte';
  import type { ApiClient, ApiLedgerEntry } from '$lib/api/client';

  export let apiClient: ApiClient | null = null;
  export let live = false;
  export let revision = 0;

  let entries: ApiLedgerEntry[] = [];
  let loading = false;
  let failed = false;
  let requestVersion = 0;

  const reasons: Record<string, string> = {
    welcome: 'Стартовая выдача', daily_bonus: 'Ежедневный бонус', relief: 'Помощь при низком балансе',
    game_stake: 'Ставка', game_payout: 'Выплата', admin_adjustment: 'Корректировка администратора'
  };
  const dateFormat = new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'short', timeStyle: 'short', timeZone: 'Europe/Moscow'
  });

  async function load(client: ApiClient | null, enabled: boolean, _revision: number) {
    const version = ++requestVersion;
    failed = false;
    if (!enabled) {
      entries = [];
      loading = false;
      return;
    }
    // Keep the last confirmed list on screen while a refresh is in flight.
    loading = entries.length === 0;
    if (!client) return;
    try {
      const result = await client.getWalletLedger();
      if (version === requestVersion) entries = result;
    } catch {
      if (version === requestVersion) failed = true;
    } finally {
      if (version === requestVersion) loading = false;
    }
  }

  $: void load(apiClient, live, revision);
  onDestroy(() => { requestVersion += 1; });
</script>

<section class="history" data-testid="ledger-history" aria-labelledby="ledger-title" aria-busy={loading}>
  <header><h2 id="ledger-title">История операций</h2><span>Последние 100 · МСК</span></header>
  {#if !live}
    <p data-testid="ledger-demo">ДЕМО · История появится после входа через Telegram. Настоящих операций здесь нет.</p>
  {:else if loading}
    <p role="status">Загружаем историю…</p>
  {:else if failed}
    <p role="alert">Не удалось загрузить историю операций.</p>
    <button type="button" on:click={() => void load(apiClient, live, revision)}>Повторить загрузку истории</button>
  {:else if entries.length === 0}
    <p data-testid="ledger-empty">Операций пока нет.</p>
  {:else}
    <ol aria-label="Операции кошелька">
      {#each entries as entry}
        <li data-testid="ledger-entry">
          <div><strong>{reasons[entry.reason] ?? 'Операция кошелька'}</strong>
            <time datetime={entry.created_at}>{dateFormat.format(new Date(entry.created_at))} МСК</time></div>
          <div class="amounts"><strong>{entry.amount_delta > 0 ? '+' : ''}{entry.amount_delta} JG</strong>
            <span>Баланс после: {entry.balance_after} JG</span></div>
        </li>
      {/each}
    </ol>
  {/if}
</section>

<style>
  .history { margin-top: 24px; padding: 18px; border: 1px solid var(--line); border-radius: var(--radius-md); background: rgb(255 247 237 / 4%); color: var(--ivory); }
  header { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px; }
  h2 { font-size: 18px; margin: 0; }
  header span, time, .amounts span, p { color: var(--muted-strong); font-size: 13px; }
  ol { list-style: none; padding: 0; margin: 12px 0 0; }
  li { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 12px; padding: 12px 0; border-top: 1px solid var(--line); overflow-wrap: anywhere; }
  li div { display: grid; gap: 6px; }
  .amounts { text-align: right; }
  button { padding: 10px 14px; border: 1px solid var(--brass-300); border-radius: 10px; color: var(--ivory); background: transparent; cursor: pointer; }
  button:focus-visible { outline: 2px solid var(--brass-300); outline-offset: 3px; }
  @media (max-width: 420px) { li { grid-template-columns: 1fr; } .amounts { text-align: left; } }
</style>
