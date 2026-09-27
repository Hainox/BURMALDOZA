<script lang="ts">
  import { onMount } from 'svelte';

  import ResultBand from '$lib/components/ResultBand.svelte';
  import type { MotionState } from '$lib/game/motion';
  import type { RoomResult, RoomSnapshot } from '$lib/state/room.svelte';

  export let snapshot: RoomSnapshot | null = null;
  export let motion: MotionState = 'idle';
  export let result: RoomResult | null = null;
  export let pending = false;
  export let apiError: string | null = null;
  export let onAction: (action: string, fields?: Record<string, unknown>) => void = () => undefined;
  export let resultSource: 'demo' | 'live' = 'demo';

  const BET_MIN = 25;
  const BET_MAX = 100;

  const RANK_ORDER = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K'];

  const DECK_A: Record<string, string[]> = {
    spades: ['UMP45', 'Vector', 'Welrod MkII', 'C-MS', 'P90', 'Grizzly', 'Thompson', 'MP5', 'Five-seveN', 'Contender', 'G11', 'UMP9', 'HK416'],
    clubs: ['M4A1', 'G36', 'G36C', 'G41', 'FAL', 'TAR-21', 'K2', 'Type 95', 'Type 97', 'RO635', 'M4 SOPMOD II', 'ST AR-15', 'M16A1'],
    hearts: ['RPK-16', 'Makarov', 'SVD', 'Mosin-Nagant', 'Suomi', 'PPSh-41', 'PPS-43', 'Lee-Enfield', 'WA2000', 'Kar98k', 'AN-94', 'AK-15', 'AK-12'],
    diamonds: ['Springfield', 'G3', 'Sten MkII', 'M1918', 'Negev', 'M1895', 'P7', 'M99', 'M200', 'G28', 'M1 Garand', 'Hecate II', 'OTs-14']
  };

  const SUIT_GLYPH: Record<string, string> = { spades: '♠', clubs: '♣', hearts: '♥', diamonds: '♦' };

  const DEALER_POOL = ['M4A1', 'UMP45', 'AK-12', 'RPK-16', 'HK416', 'WA2000'];

  const OUTCOME_LABEL: Record<string, string> = {
    blackjack: 'Натуральный блэкджек · 3:2',
    win: 'Победа',
    push: 'Пуш · возврат ставки',
    loss: 'Поражение'
  };

  interface FaceCard {
    rank: string;
    suit: string;
  }

  type PublicState = Record<string, unknown>;

  $: ps = (snapshot?.publicState ?? {}) as PublicState;
  $: isDemo = ps.demo === true;
  $: gamePhase =
    typeof ps.game_phase === 'string'
      ? (ps.game_phase as string)
      : typeof ps.phase === 'string'
        ? (ps.phase as string)
        : isDemo
          ? 'demo'
          : 'waiting';

  function stringList(value: unknown): string[] {
    if (!Array.isArray(value)) return [];
    return value.filter((entry): entry is string => typeof entry === 'string');
  }

  function intOrNull(value: unknown): number | null {
    return typeof value === 'number' && Number.isInteger(value) ? value : null;
  }

  function isFaceCard(value: unknown): value is FaceCard {
    if (typeof value !== 'object' || value === null) return false;
    const record = value as Record<string, unknown>;
    return typeof record.rank === 'string' && typeof record.suit === 'string';
  }

  function isHoleCard(value: unknown): boolean {
    if (typeof value !== 'object' || value === null) return false;
    return (value as Record<string, unknown>).hidden === true;
  }

  function faceCards(value: unknown): FaceCard[] {
    if (!Array.isArray(value)) return [];
    return (value as unknown[]).filter(isFaceCard);
  }

  $: rawLegal = stringList(ps.legal_actions);
  $: legalActions = rawLegal.filter(
    (action) => action === 'deal' || action === 'hit' || action === 'stand' || action === 'double'
  );
  $: handActions = legalActions.filter((action) => action !== 'deal');
  $: canDeal = legalActions.includes('deal') || (isDemo && legalActions.length === 0);
  $: playerFaces = faceCards(ps.player_cards);
  $: dealerFaces = faceCards(ps.dealer_cards);
  $: holeShown = Array.isArray(ps.dealer_cards) && (ps.dealer_cards as unknown[]).some(isHoleCard);
  $: holeHidden = ps.dealer_hole_hidden === true || holeShown;
  $: betShown = intOrNull(ps.bet);
  $: playerTotal = intOrNull(ps.player_total);
  $: dealerTotal = 'dealer_total' in ps ? intOrNull(ps.dealer_total) : null;
  $: walletBalance = intOrNull(ps.wallet_balance);
  $: ruleset =
    typeof ps.ruleset_version === 'string'
      ? (ps.ruleset_version as string)
      : (snapshot?.rulesetVersion ?? 'blackjack-gfl-skeleton-1');
  $: stateVersion = snapshot?.stateVersion ?? 0;

  $: busy = pending || motion === 'resolving';
  $: isConfirmed = result !== null && (motion === 'outcome' || motion === 'settle');
  $: outcome = result?.blackjackOutcome ?? null;

  let bet = 25;
  let reducedMotion = false;

  $: betValid = Number.isInteger(bet) && bet >= BET_MIN && bet <= BET_MAX;
  $: canSendDeal = canDeal && betValid && !busy;

  onMount(() => {
    if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
      reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }
  });

  function hashRoom(roomId: string): number {
    let hash = 0;
    for (let index = 0; index < roomId.length; index += 1) {
      hash = (hash * 31 + roomId.charCodeAt(index)) >>> 0;
    }
    return hash;
  }

  $: dealerName = DEALER_POOL[hashRoom(snapshot?.roomId ?? 'demo') % DEALER_POOL.length] ?? 'M4A1';

  function dollFor(rank: string, suit: string): string | null {
    const list = DECK_A[suit];
    const index = RANK_ORDER.indexOf(rank);
    if (!list || index < 0) return null;
    return list[index] ?? null;
  }

  function suitGlyph(suit: string): string {
    return SUIT_GLYPH[suit] ?? '·';
  }

  function rankHint(rank: string): string {
    if (rank === 'A') return '1 / 11';
    if (rank === 'J' || rank === 'Q' || rank === 'K') return '10';
    return rank;
  }

  function isRedSuit(suit: string): boolean {
    return suit === 'hearts' || suit === 'diamonds';
  }

  function cardDelay(index: number): string {
    return reducedMotion ? '0ms' : `${index * 130}ms`;
  }

  function deal() {
    if (!canSendDeal) return;
    onAction('deal', { bet });
  }

  function act(action: 'hit' | 'stand' | 'double') {
    if (busy || !legalActions.includes(action)) return;
    onAction(action);
  }

  function setBet(value: number) {
    bet = value;
  }
</script>

<div
  class="game-room blackjack-room"
  data-testid="blackjack-room"
  data-game-phase={gamePhase}
  data-hole-hidden={holeHidden}
>
  <div class="room-intro">
    <div>
      <span class="room-kicker">GFL POST-COLLAPSE · SECTOR 09 PERIMETER</span>
      <h2>Blackjack</h2>
      <p>Заброшенный корпус за полицейским периметром. Раздаёт только сервер.</p>
    </div>
    <span class="bet-chip" data-testid="blackjack-wallet">
      {betShown !== null ? `${betShown} JG ставка` : `${BET_MIN}–${BET_MAX} JG`}
      {walletBalance !== null ? ` · ${walletBalance} JG` : ''}
    </span>
  </div>

  <div class="perimeter-tape" aria-hidden="true"><span>ПОЛИЦЕЙСКОЕ ОЦЕПЛЕНИЕ · SECTOR 09</span></div>

  <section class="felt-table" aria-label="Blackjack table">
    <div class="table-orbit orbit-one"></div>
    <div class="table-orbit orbit-two"></div>

    <div class="dealer-line" data-testid="blackjack-dealer">
      <span class="dealer-avatar" aria-hidden="true">{dealerName.slice(0, 1)}</span>
      <span class="dealer-copy">DEALER · <b>{dealerName}</b> <small>GFL DOSSIER · COSMETIC</small></span>
    </div>

    <div class="hand dealer-hand">
      <span class="hand-label">DEALER <b>{dealerTotal !== null ? dealerTotal : holeHidden ? 'скрыто' : '—'}</b></span>
      <div class="cards" data-testid="blackjack-dealer-cards">
        {#each dealerFaces as card, index (index)}
          {@const doll = dollFor(card.rank, card.suit)}
          <div
            class="playing-card"
            class:red={isRedSuit(card.suit)}
            style={`--card-delay: ${cardDelay(index)}; --card-rotation: ${index % 2 === 0 ? '-4deg' : '5deg'}; --card-offset: ${index % 2 === 0 ? '0px' : '3px'}`}
            data-card={`${card.rank}-${card.suit}`}
            aria-label={`${card.rank} ${suitGlyph(card.suit)} · ${doll ?? 'карта'}`}
          >
            <span class="corner top">{card.rank}{suitGlyph(card.suit)}</span>
            <span class="dossier">
              <small>GFL DOSSIER · DECK A</small>
              <strong>{doll ?? `${card.rank} ${suitGlyph(card.suit)}`}</strong>
              <em>{card.rank}{suitGlyph(card.suit)} · {rankHint(card.rank)}</em>
            </span>
            <span class="corner bottom">{card.rank}{suitGlyph(card.suit)}</span>
          </div>
        {/each}
        {#if holeShown}
          <div
            class="playing-card hole-card"
            data-testid="blackjack-hole-hidden"
            role="img"
            aria-label="Скрытая карта дилера"
            style={`--card-delay: ${cardDelay(dealerFaces.length)}; --card-rotation: 5deg; --card-offset: 3px`}
          >
            <span class="back-stamp"><b>S09</b><span>РУБАШКА A</span></span>
          </div>
        {/if}
        {#if dealerFaces.length === 0 && !holeShown}
          <span class="ghost">Карты дилера покажет сервер</span>
        {/if}
      </div>
      <span class="total" data-testid="blackjack-dealer-total">
        {dealerTotal !== null ? `total ${dealerTotal}` : holeHidden ? 'total скрыт' : 'ожидание раздачи'}
      </span>
    </div>

    <div class="table-mark" aria-hidden="true">09</div>

    <div class="hand player-hand">
      <span class="hand-label">YOU <b>{playerTotal !== null ? playerTotal : '—'}</b></span>
      <div class="cards" data-testid="blackjack-player-cards">
        {#each playerFaces as card, index (index)}
          {@const doll = dollFor(card.rank, card.suit)}
          <div
            class="playing-card player-card"
            class:red={isRedSuit(card.suit)}
            style={`--card-delay: ${cardDelay(index)}; --card-rotation: ${index % 2 === 0 ? '-4deg' : '5deg'}; --card-offset: ${index % 2 === 0 ? '0px' : '3px'}`}
            data-card={`${card.rank}-${card.suit}`}
            aria-label={`${card.rank} ${suitGlyph(card.suit)} · ${doll ?? 'карта'}`}
          >
            <span class="corner top">{card.rank}{suitGlyph(card.suit)}</span>
            <span class="dossier">
              <small>GFL DOSSIER · DECK A</small>
              <strong>{doll ?? `${card.rank} ${suitGlyph(card.suit)}`}</strong>
              <em>{card.rank}{suitGlyph(card.suit)} · {rankHint(card.rank)}</em>
            </span>
            <span class="corner bottom">{card.rank}{suitGlyph(card.suit)}</span>
          </div>
        {/each}
        {#if playerFaces.length === 0}
          <span class="ghost">Ваши карты покажет сервер</span>
        {/if}
      </div>
      <span class="total bright" data-testid="blackjack-player-total">
        {playerTotal !== null ? `total ${playerTotal}` : 'ожидание раздачи'}
      </span>
    </div>
  </section>

  {#if canDeal}
    <section class="bet-panel" aria-label="Выбор ставки">
      <div class="bet-row">
        <label for="blackjack-bet">Ставка · {BET_MIN}–{BET_MAX} JG</label>
        <input
          id="blackjack-bet"
          data-testid="blackjack-bet"
          type="number"
          min={BET_MIN}
          max={BET_MAX}
          step="1"
          bind:value={bet}
          disabled={busy}
        />
      </div>
      <div class="chip-row" role="group" aria-label="Быстрый выбор ставки">
        <button type="button" on:click={() => setBet(25)} disabled={busy} aria-pressed={bet === 25}>25</button>
        <button type="button" on:click={() => setBet(50)} disabled={busy} aria-pressed={bet === 50}>50</button>
        <button type="button" on:click={() => setBet(100)} disabled={busy} aria-pressed={bet === 100}>100</button>
      </div>
      {#if !betValid}
        <p class="bet-hint" role="alert">Ставка — целое число от {BET_MIN} до {BET_MAX}.</p>
      {/if}
      <button
        type="button"
        class="deal-action"
        data-testid="blackjack-deal"
        on:click={deal}
        disabled={!canSendDeal}
      >
        {busy ? 'Ожидаем сервер…' : betValid ? `Раздать за ${bet} JG` : 'Выберите ставку'}
      </button>
    </section>
  {/if}

  {#if handActions.length > 0}
    <div class="action-grid" data-testid="blackjack-actions" role="group" aria-label="Действия руки">
      {#if handActions.includes('hit')}
        <button type="button" data-testid="blackjack-hit" on:click={() => act('hit')} disabled={busy}>
          HIT <small>+ card</small>
        </button>
      {/if}
      {#if handActions.includes('stand')}
        <button type="button" class="action-primary" data-testid="blackjack-stand" on:click={() => act('stand')} disabled={busy}>
          STAND <small>lock hand</small>
        </button>
      {/if}
      {#if handActions.includes('double')}
        <button type="button" data-testid="blackjack-double" on:click={() => act('double')} disabled={busy}>
          DOUBLE <small>×2 stake</small>
        </button>
      {/if}
    </div>
  {/if}

  <div class="bj-status" data-testid="blackjack-status" aria-live="polite">
    <span>PHASE {gamePhase} · {ruleset} · v{stateVersion}</span>
    <strong>{busy ? 'Ожидаем сервер…' : isConfirmed ? 'Сервер подтвердил' : canDeal ? 'Готов к раздаче' : 'Ход по серверу'}</strong>
  </div>

  {#if apiError}
    <p class="bj-error" data-testid="blackjack-error" role="alert">
      Сервер не подтвердил действие: {apiError} Повторите разрешённое действие — повтор получит новый ключ и не задвоит ставку.
    </p>
  {/if}

  {#if isConfirmed && outcome}
    <section class="settlement" data-testid="blackjack-settlement" aria-live="polite">
      <span class="settle-kicker">SERVER SETTLEMENT · {outcome.rulesetVersion}</span>
      <div class="settle-row">
        <div>
          <strong>{OUTCOME_LABEL[outcome.outcome] ?? outcome.outcome}</strong>
          <p>{outcome.playerTotal} против {outcome.dealerTotal} · ставка {outcome.finalBet} JG</p>
        </div>
        <span class="settle-amount">{outcome.grossPayout > 0 ? '+' : ''}{outcome.grossPayout} <small>JG</small></span>
      </div>
      <span class="settle-balance">BALANCE {outcome.balanceAfter} JG · NET {outcome.netDelta > 0 ? '+' : ''}{outcome.netDelta}</span>
    </section>
  {/if}

  <ResultBand {result} {motion} source={resultSource} />
  <p class="rules-line">Soft 17 — stand · Natural 3:2 · Split нет · Только серверный snapshot</p>
</div>

<style>
  .game-room { position: relative; z-index: 1; display: grid; gap: 14px; }
  .room-intro { display: flex; justify-content: space-between; gap: 18px; }
  .room-kicker { color: #78d3a2; font-size: 9px; font-weight: 800; letter-spacing: 0.13em; }
  h2 { margin: 6px 0 5px; font-size: clamp(27px, 8vw, 38px); letter-spacing: -0.06em; }
  p { max-width: 250px; margin: 0; color: var(--muted); font-size: 12px; line-height: 1.45; }
  .bet-chip { height: fit-content; padding: 7px 9px; border: 1px solid rgb(142 228 182 / 30%); border-radius: 999px; color: #a4f0c4; font-size: 10px; font-weight: 800; white-space: nowrap; }
  .perimeter-tape { overflow: hidden; border-radius: 8px; background: repeating-linear-gradient(-45deg, #e7bb70 0 14px, #14141c 14px 28px); padding: 3px; }
  .perimeter-tape span { display: block; padding: 5px 10px; border-radius: 6px; background: rgb(11 11 17 / 88%); color: #e7bb70; font-size: 9px; font-weight: 800; letter-spacing: 0.16em; text-align: center; }
  .felt-table { position: relative; display: grid; align-content: space-between; gap: 14px; min-height: 368px; overflow: hidden; padding: 25px 20px; border: 1px solid rgb(142 228 182 / 32%); border-radius: 42% / 18%; background: radial-gradient(ellipse at 50% 18%, rgb(58 74 92 / 55%), transparent 55%), radial-gradient(ellipse at center, #174a40, #0a2829 72%); box-shadow: inset 0 0 40px rgb(0 0 0 / 40%), 0 18px 42px rgb(0 0 0 / 25%); }
  .table-orbit { position: absolute; inset: 16px; border: 1px solid rgb(142 228 182 / 12%); border-radius: 42% / 20%; pointer-events: none; }
  .orbit-two { inset: 28px; border-color: rgb(231 187 112 / 12%); }
  .dealer-line { position: relative; z-index: 1; display: flex; align-items: center; gap: 9px; justify-self: center; padding: 6px 12px 6px 6px; border: 1px solid rgb(255 247 237 / 16%); border-radius: 999px; background: rgb(11 11 17 / 55%); color: rgb(255 247 237 / 80%); font-size: 9px; font-weight: 800; letter-spacing: 0.12em; }
  .dealer-avatar { display: grid; place-items: center; width: 26px; height: 26px; border-radius: 50%; background: linear-gradient(145deg, #8f3559, #3b2430); color: #ffe9c4; font-size: 13px; }
  .dealer-copy b { color: var(--brass-300); }
  .dealer-copy small { color: rgb(255 247 237 / 55%); font-weight: 700; }
  .hand { position: relative; z-index: 1; display: grid; justify-items: center; gap: 8px; }
  .hand-label { color: rgb(255 247 237 / 68%); font-size: 9px; font-weight: 800; letter-spacing: 0.16em; }
  .hand-label b { color: var(--brass-300); }
  .cards { display: flex; flex-wrap: wrap; justify-content: center; gap: 4px; }
  .playing-card { position: relative; display: grid; place-items: center; width: 104px; min-height: 128px; padding: 22px 8px; margin-left: -10px; border: 1px solid rgb(255 247 237 / 55%); border-radius: 8px; background: #fff8ee; color: #3b2430; box-shadow: 0 7px 14px rgb(0 0 0 / 25%); transform: translate3d(0, var(--card-offset), 0) rotate(var(--card-rotation)); animation: dealCard 440ms var(--ease-spring) var(--card-delay) both; backface-visibility: hidden; will-change: transform, opacity; }
  .playing-card:first-child { margin-left: 0; }
  .playing-card.red { color: #8f2f3f; }
  .hole-card { background: repeating-linear-gradient(45deg, #1d2b33 0 6px, #2e4a3a 6px 9px); border-color: rgb(231 187 112 / 60%); }
  .back-stamp { display: grid; gap: 4px; place-items: center; color: #e7bb70; font-size: 8px; font-weight: 800; letter-spacing: 0.18em; text-align: center; }
  .back-stamp b { font-size: 22px; letter-spacing: 0.1em; }
  .player-card { border-color: rgb(231 187 112 / 75%); }
  .corner { position: absolute; font-size: 15px; font-weight: 850; line-height: 1; }
  .corner.top { top: 6px; left: 7px; }
  .corner.bottom { right: 7px; bottom: 6px; transform: rotate(180deg); }
  .dossier { display: grid; gap: 2px; justify-items: center; text-align: center; }
  .dossier small { font-size: 7px; font-weight: 800; letter-spacing: 0.14em; opacity: 0.65; }
  .dossier strong { font-size: 15px; line-height: 1.1; letter-spacing: -0.01em; }
  .dossier em { font-style: normal; font-size: 10px; font-weight: 800; opacity: 0.75; }
  .ghost { color: rgb(255 247 237 / 55%); font-size: 11px; }
  .total { color: rgb(255 247 237 / 72%); font-size: 13px; font-weight: 800; }
  .total.bright { color: var(--brass-300); }
  .table-mark { position: absolute; top: 50%; left: 50%; color: rgb(231 187 112 / 15%); font-size: 58px; font-weight: 800; transform: translate(-50%, -50%); }
  .bet-panel { display: grid; gap: 10px; padding: 13px 14px; border: 1px solid var(--line); border-radius: var(--radius-md); background: rgb(255 247 237 / 4%); }
  .bet-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .bet-row label { color: var(--muted-strong); font-size: 11px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }
  .bet-row input { width: 110px; min-height: 44px; padding: 8px 10px; border: 1px solid var(--line); border-radius: 10px; background: rgb(11 11 17 / 60%); color: var(--ivory); font: inherit; font-size: 15px; font-weight: 800; text-align: center; }
  .chip-row { display: flex; gap: 8px; }
  .chip-row button { flex: 1; min-height: 44px; border: 1px solid var(--line); border-radius: 11px; background: rgb(255 247 237 / 6%); color: var(--ivory); font: inherit; font-size: 13px; font-weight: 800; cursor: pointer; }
  .chip-row button[aria-pressed='true'] { border-color: rgb(231 187 112 / 60%); color: var(--brass-300); }
  .bet-hint { max-width: none; color: #ff9cae; font-size: 11px; }
  .deal-action { min-height: 52px; border: 0; border-radius: 15px; background: linear-gradient(120deg, var(--brass-300), #c98f4e); color: #2a1820; font: inherit; font-size: 14px; font-weight: 850; cursor: pointer; }
  .deal-action:disabled { cursor: not-allowed; filter: saturate(0.6); opacity: 0.75; }
  .action-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .action-grid button { min-height: 54px; border: 1px solid var(--line); border-radius: 13px; background: rgb(255 247 237 / 6%); color: var(--ivory); font-weight: 800; font-size: 13px; cursor: pointer; transition: transform 160ms ease, border-color 160ms ease; }
  .action-grid button small { display: block; color: var(--muted); font-size: 9px; font-weight: 700; }
  .action-grid button:disabled { cursor: wait; opacity: 0.65; }
  .action-grid .action-primary { border-color: rgb(231 187 112 / 55%); }
  .bj-status { display: flex; align-items: center; justify-content: space-between; gap: 10px; color: var(--muted); font-size: 9px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }
  .bj-status strong { color: var(--brass-300); }
  .bj-error { max-width: none; padding: 11px 12px; border: 1px solid rgb(255 156 174 / 45%); border-radius: 12px; background: rgb(255 156 174 / 8%); color: #ffc2cd; font-size: 11px; line-height: 1.45; }
  .settlement { display: grid; gap: 8px; padding: 13px 15px; border: 1px solid rgb(142 228 182 / 38%); border-radius: var(--radius-md); background: linear-gradient(105deg, rgb(142 228 182 / 12%), rgb(231 187 112 / 8%)); }
  .settle-kicker { color: var(--success); font-size: 9px; font-weight: 800; letter-spacing: 0.15em; }
  .settle-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .settle-row strong { font-size: 14px; }
  .settle-row p { max-width: none; margin: 3px 0 0; color: var(--muted); font-size: 11px; }
  .settle-amount { color: var(--brass-300); font-size: 19px; font-weight: 800; white-space: nowrap; }
  .settle-amount small { font-size: 10px; letter-spacing: 0.12em; }
  .settle-balance { color: var(--success); font-size: 9px; font-weight: 800; letter-spacing: 0.1em; }
  .rules-line { max-width: none; color: var(--muted); font-size: 10px; letter-spacing: 0.04em; }
  button:focus-visible, input:focus-visible { outline: 2px solid var(--brass-300); outline-offset: 3px; }
  @keyframes dealCard {
    from { opacity: 0; transform: translate3d(0, calc(-22px + var(--card-offset)), 0) rotate(calc(var(--card-rotation) - 8deg)) scale(0.92); }
    to { opacity: 1; transform: translate3d(0, var(--card-offset), 0) rotate(var(--card-rotation)) scale(1); }
  }
  @media (max-width: 390px) {
    .playing-card { width: 96px; }
    .action-grid { grid-template-columns: 1fr; }
  }
  @media (min-width: 720px) {
    .playing-card { width: 118px; min-height: 142px; }
  }
  @media (prefers-reduced-motion: reduce) {
    .playing-card { animation: none; }
    .action-grid button { transition: none; }
  }
</style>
