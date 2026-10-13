<script lang="ts">
  import { onDestroy } from 'svelte';
  import type { ApiClient, ApiLeaderboardSnapshot } from '$lib/api/client';

  export let apiClient: ApiClient | null = null;
  export let live = false;
  export let revision = 0;

  let snapshot: ApiLeaderboardSnapshot | null = null;
  let loading = false;
  let failed = false;
  let requestVersion = 0;
  const dateFormat = new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'Europe/Moscow'
  });

  async function load(client: ApiClient | null, enabled: boolean, _revision: number) {
    const version = ++requestVersion;
    failed = false;
    if (!enabled) {
      snapshot = null;
      loading = false;
      return;
    }
    loading = true;
    if (!client) return;
    try {
      const result = await client.getLeaderboard();
      if (version === requestVersion) snapshot = result;
    } catch {
      if (version === requestVersion) failed = true;
    } finally {
      if (version === requestVersion) loading = false;
    }
  }

  $: void load(apiClient, live, revision);
  onDestroy(() => { requestVersion += 1; });
</script>

<section class="leaderboard" data-testid="leaderboard" aria-labelledby="leaderboard-title" aria-busy={loading}>
  <header><h2 id="leaderboard-title">Рейтинг недели</h2><span>Топ-15 · МСК</span></header>
  <p class="rule">Чистый игровой результат: выплаты минус ставки. Бонусы и выдачи не учитываются.</p>
  {#if !live}
    <p data-testid="leaderboard-demo">ДЕМО · Настоящий рейтинг появится после входа через Telegram.</p>
  {:else if loading}
    <p role="status">Загружаем рейтинг…</p>
  {:else if failed}
    <p role="alert">Не удалось загрузить рейтинг недели.</p>
    <button type="button" on:click={() => void load(apiClient, live, revision)}>Повторить загрузку рейтинга</button>
  {:else if snapshot}
    <p class="period" data-testid="leaderboard-period">
      {dateFormat.format(new Date(snapshot.week_start))} 00:00 — {dateFormat.format(new Date(snapshot.week_end))} 00:00 МСК
    </p>
    {#if snapshot.entries.length === 0}
      <p data-testid="leaderboard-empty">На этой неделе ещё нет игровых операций.</p>
    {:else}
      <ol aria-label="Топ-15 игроков за календарную неделю">
        {#each snapshot.entries as entry}
          <li data-testid="leaderboard-entry">
            <span class="rank" aria-label={`Место ${entry.rank}`}>{entry.rank}</span>
            <strong class="nickname">{entry.nickname}</strong>
            <span class="result">{entry.net_result > 0 ? '+' : ''}{entry.net_result} JG</span>
          </li>
        {/each}
      </ol>
    {/if}
  {/if}
</section>

<style>
  .leaderboard { margin-top: 24px; padding: 18px; border: 1px solid var(--line); border-radius: var(--radius-md); background: rgb(255 247 237 / 4%); color: var(--ivory); }
  header { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px; }
  h2 { font-size: 18px; margin: 0; }
  header span, p { color: var(--muted-strong); font-size: 13px; line-height: 1.5; }
  ol { list-style: none; padding: 0; margin: 12px 0 0; }
  li { display: grid; grid-template-columns: 28px minmax(0, 1fr) auto; gap: 10px; align-items: baseline; padding: 12px 0; border-top: 1px solid var(--line); font-size: 14px; }
  .rank { color: var(--brass-300); }
  .nickname { overflow-wrap: anywhere; }
  .result { font-variant-numeric: tabular-nums; overflow-wrap: anywhere; text-align: right; max-width: 130px; }
  button { padding: 10px 14px; border: 1px solid var(--brass-300); border-radius: 10px; color: var(--ivory); background: transparent; cursor: pointer; }
  button:focus-visible { outline: 2px solid var(--brass-300); outline-offset: 3px; }
  @media (max-width: 420px) { li { grid-template-columns: 24px minmax(0, 1fr); } .result { grid-column: 2; text-align: left; max-width: none; } }
</style>
