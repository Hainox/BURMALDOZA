<script lang="ts">
  import { onMount } from 'svelte';
  import { base } from '$app/paths';

  import BetPicker from '$lib/components/BetPicker.svelte';
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
  // Своя ставка — до всего баланса (решение владельца 14.10.2026); сервер проверяет баланс.
  export let balance = 1000;
  const BET_PRESETS = [25, 50, 100, 250, 500].map((value) => ({ value }));
  $: betMax = Math.max(BET_MIN, Math.floor(balance));

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

  // Номер раздачи: сервер его не присылает, считаем по входу в новую игру из ожидания/итога.
  // Карты привязаны к нему ключом — на каждой раздаче они монтируются заново и снова «прилетают».
  let roundSeq = 0;
  let lastPhase = '';
  $: trackRound(gamePhase);
  function trackRound(phase: string) {
    if (phase && phase !== lastPhase && phase !== 'waiting' && (lastPhase === '' || lastPhase === 'waiting' || lastPhase === 'settled')) roundSeq += 1;
    lastPhase = phase;
  }

  $: busy = pending || motion === 'resolving';
  $: isConfirmed = result !== null && (motion === 'outcome' || motion === 'settle');
  $: outcome = result?.blackjackOutcome ?? null;
  $: tableOutcome = isConfirmed ? outcome?.outcome ?? '' : '';
  let previousHoleShown = false;
  let revealRound = -1;
  $: trackHole(holeShown, roundSeq);
  function trackHole(shown: boolean, round: number) {
    if (previousHoleShown && !shown) revealRound = round;
    previousHoleShown = shown;
  }

  let bet = 25;
  let reducedMotion = false;

  $: betValid = Number.isInteger(bet) && bet >= BET_MIN && bet <= betMax && bet <= balance;
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

  // Портреты Deck A лежат в static/blackjack/portraits/<имя куклы>_S.webp.
  function portraitUrl(doll: string): string {
    return `${base}/blackjack/portraits/${encodeURIComponent(`${doll}_S.webp`)}`;
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

</script>

<div
  class="game-room blackjack-room"
  data-testid="blackjack-room"
  data-game-phase={gamePhase}
  data-hole-hidden={holeHidden}
>
  <div class="room-intro">
    <div>
      <p>{isDemo ? 'Заброшенный корпус за полицейским периметром. Демо-раздачу и результат показывает клиент.' : 'Заброшенный корпус за полицейским периметром. Раздаёт только сервер.'}</p>
    </div>
    <span class="bet-chip" data-testid="blackjack-wallet">
      {betShown !== null ? `${betShown} JG ставка` : `от ${BET_MIN} JG`}
      {walletBalance !== null ? ` · ${walletBalance} JG` : ''}
    </span>
  </div>

  <div class="perimeter-tape" aria-hidden="true"><span>ПОЛИЦЕЙСКОЕ ОЦЕПЛЕНИЕ · SECTOR 09</span></div>

  {#if isDemo}
    <p class="demo-note" data-testid="blackjack-demo-note" role="status">
      ДЕМО · стол без сервера: карты и итог показывает клиент, серверного подтверждения нет.
    </p>
  {/if}

  <section class="felt-table" class:won={tableOutcome === 'win' || tableOutcome === 'blackjack'} class:lost={tableOutcome === 'loss'} aria-label="Blackjack table" data-outcome={tableOutcome}>
    <div class="table-orbit orbit-one"></div>
    <div class="table-orbit orbit-two"></div>
    <div class="dealer-deck" aria-hidden="true"><img src={`${base}/blackjack/card-back.webp`} alt="" /></div>
    {#if tableOutcome === 'win' || tableOutcome === 'blackjack'}
      {#key result}<div class="win-light" aria-hidden="true"></div><div class="prize-chips" aria-hidden="true"><i></i><i></i><i></i></div>{/key}
    {:else if tableOutcome === 'loss'}<div class="loss-shade" aria-hidden="true"></div>{/if}

    <div class="dealer-line" data-testid="blackjack-dealer">
      <img class="dealer-avatar" src={portraitUrl(dealerName)} alt="" aria-hidden="true" decoding="async" data-testid="blackjack-dealer-portrait" />
      <span class="dealer-copy">DEALER · <b>{dealerName}</b> <small>GFL DOSSIER · COSMETIC</small></span>
    </div>

    <div class="hand dealer-hand">
      <span class="hand-label">DEALER <b>{dealerTotal !== null ? dealerTotal : holeHidden ? 'скрыто' : '—'}</b></span>
      <div class="cards" data-testid="blackjack-dealer-cards">
        {#each dealerFaces as card, index (`${roundSeq}-${index}`)}
          {@const doll = dollFor(card.rank, card.suit)}
          <div
            class="playing-card"
            class:revealed={index === 1 && revealRound === roundSeq && !holeShown}
            class:red={isRedSuit(card.suit)}
            style={`--card-delay: ${cardDelay(index)}; --card-rotation: ${index % 2 === 0 ? '-4deg' : '5deg'}; --card-offset: ${index % 2 === 0 ? '0px' : '3px'}`}
            data-card={`${card.rank}-${card.suit}`}
            aria-label={`${card.rank} ${suitGlyph(card.suit)} · ${doll ?? 'карта'}`}
          >
            <div class="card-front">
            {#if doll}<img class="portrait" src={portraitUrl(doll)} alt="" loading="eager" decoding="async" />{/if}
            <span class="corner top">{card.rank}{suitGlyph(card.suit)}</span>
            <span class="dossier">
              <strong>{doll ?? `${card.rank} ${suitGlyph(card.suit)}`}</strong>
              <em>{card.rank}{suitGlyph(card.suit)} · {rankHint(card.rank)}</em>
            </span>
            <span class="corner bottom">{card.rank}{suitGlyph(card.suit)}</span>
            </div>
            <img class="flip-back" src={`${base}/blackjack/card-back.webp`} alt="" aria-hidden="true" />
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
            <img class="back-art" src={`${base}/blackjack/card-back.webp`} alt="" decoding="async" />
          </div>
        {/if}
        {#if dealerFaces.length === 0 && !holeShown}
          <span class="ghost">{isDemo ? 'Карты дилера появятся после демо-раздачи' : 'Карты дилера покажет сервер'}</span>
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
        {#each playerFaces as card, index (`${roundSeq}-${index}`)}
          {@const doll = dollFor(card.rank, card.suit)}
          <div
            class="playing-card player-card"
            class:red={isRedSuit(card.suit)}
            style={`--card-delay: ${cardDelay(index)}; --card-rotation: ${index % 2 === 0 ? '-4deg' : '5deg'}; --card-offset: ${index % 2 === 0 ? '0px' : '3px'}`}
            data-card={`${card.rank}-${card.suit}`}
            aria-label={`${card.rank} ${suitGlyph(card.suit)} · ${doll ?? 'карта'}`}
          >
            {#if doll}<img class="portrait" src={portraitUrl(doll)} alt="" loading="eager" decoding="async" />{/if}
            <span class="corner top">{card.rank}{suitGlyph(card.suit)}</span>
            <span class="dossier">
              <strong>{doll ?? `${card.rank} ${suitGlyph(card.suit)}`}</strong>
              <em>{card.rank}{suitGlyph(card.suit)} · {rankHint(card.rank)}</em>
            </span>
            <span class="corner bottom">{card.rank}{suitGlyph(card.suit)}</span>
          </div>
        {/each}
        {#if playerFaces.length === 0}
          <span class="ghost">{isDemo ? 'Ваши карты появятся после демо-раздачи' : 'Ваши карты покажет сервер'}</span>
        {/if}
      </div>
      <span class="total bright" data-testid="blackjack-player-total">
        {playerTotal !== null ? `total ${playerTotal}` : 'ожидание раздачи'}
      </span>
    </div>
  </section>


  {#if canDeal}
    <section class="bet-panel" aria-label="Выбор ставки">
      <details class="bet-settings" open={!outcome}><summary>Ставка: {bet} JG <span>Изменить ▾</span></summary>
      <BetPicker
        bind:value={bet}
        min={BET_MIN}
        max={betMax}
        presets={BET_PRESETS}
        disabled={busy}
        inputId="blackjack-bet"
        inputTestId="blackjack-bet"
      />
      {#if !betValid}
        <p class="bet-hint" role="alert">Ставка — целое число от {BET_MIN} до {betMax} JG (ваш баланс).</p>
      {/if}
      </details>
      <button
        type="button"
        class="deal-action"
        data-testid="blackjack-deal"
        on:click={deal}
        disabled={!canSendDeal}
      >
        {busy ? (isDemo ? 'Раскладываем…' : 'Ожидаем сервер…') : betValid ? `Раздать за ${bet} JG` : 'Выберите ставку'}
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
    <strong>
      {busy
        ? isDemo ? 'Ход демо-раунда' : 'Ожидаем сервер…'
        : isConfirmed
          ? isDemo ? 'Демо-раунд завершён' : 'Сервер подтвердил'
          : canDeal
            ? 'Готов к раздаче'
            : isDemo ? 'Ваш ход' : 'Ход по серверу'}
    </strong>
  </div>

  {#if apiError}
    <p class="bj-error" data-testid="blackjack-error" role="alert">
      Сервер не подтвердил действие: {apiError} Клиент перечитывает комнату — действуйте по актуальному снимку, а не повторяйте тот же тап.
    </p>
  {/if}

  {#if isConfirmed && outcome}
    <section class="settlement" data-testid="blackjack-settlement" aria-live="polite">
      <span class="settle-kicker">
        {isDemo ? 'DEMO ROUND · БЕЗ СЕРВЕРНОГО ПОДТВЕРЖДЕНИЯ' : `SERVER SETTLEMENT · ${outcome.rulesetVersion}`}
      </span>
      <div class="settle-row">
        <div>
          <strong>{OUTCOME_LABEL[outcome.outcome] ?? outcome.outcome}</strong>
          <p>{outcome.playerTotal} против {outcome.dealerTotal} · ставка {outcome.finalBet} JG</p>
        </div>
        <span class="settle-amount">{outcome.grossPayout > 0 ? '+' : ''}{outcome.grossPayout} <small>JG</small></span>
      </div>
      <span class="settle-balance">{isDemo ? 'DEMO BALANCE' : 'BALANCE'} {outcome.balanceAfter} JG · NET {outcome.netDelta > 0 ? '+' : ''}{outcome.netDelta}</span>
    </section>
  {/if}

  <ResultBand {result} {motion} source={resultSource} compact={Boolean(outcome) || canDeal} />
  <details class="sources">
    <summary>Источники изображений</summary>
    <p>Портреты T-Doll © MICA Team / SUNBORN, источник — IOP Wiki. Некоммерческий фанатский интерфейс по решению владельца. Общая лицензия на изображения не заявляется.</p>
    <a href={`${base}/blackjack/sources.json`} target="_blank" rel="noreferrer">Источники портретов Deck A</a>
  </details>
  <p class="rules-line">{isDemo ? 'Soft 17 — stand · Natural 3:2 · Split нет · Демо-раунд без серверного подтверждения' : 'Soft 17 — stand · Natural 3:2 · Split нет · Только серверный snapshot'}</p>
</div>

<style>
  .game-room { position: relative; z-index: 1; display: grid; gap: 14px; }
  .room-intro { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
  p { max-width: 260px; margin: 0; color: #d6d0c8; font-size: 12px; line-height: 1.45; text-shadow: 0 1px 6px rgb(0 0 0 / 80%); }
  .bet-chip { height: fit-content; padding: 7px 10px; border: 1px solid rgb(142 228 182 / 40%); border-radius: 999px; background: rgb(6 20 18 / 70%); color: #a4f0c4; font-size: 10px; font-weight: 800; white-space: nowrap; backdrop-filter: blur(8px); }
  .perimeter-tape { overflow: hidden; border-radius: 8px; background: repeating-linear-gradient(-45deg, #e7bb70 0 14px, #14141c 14px 28px); padding: 3px; }
  .perimeter-tape span { display: block; padding: 5px 10px; border-radius: 6px; background: rgb(11 11 17 / 88%); color: #e7bb70; font-size: 9px; font-weight: 800; letter-spacing: 0.16em; text-align: center; }
  .felt-table { position: relative; display: grid; align-content: space-between; gap: 14px; min-height: 368px; overflow: hidden; padding: 25px 20px; border: 1px solid rgb(142 228 182 / 38%); border-radius: 42% / 18%; background: radial-gradient(ellipse at 50% 18%, rgb(58 74 92 / 45%), transparent 55%), radial-gradient(ellipse at center, rgb(23 74 64 / 94%), rgb(10 40 41 / 96%) 72%); box-shadow: inset 0 0 40px rgb(0 0 0 / 40%), 0 0 0 1px rgb(0 0 0 / 30%), 0 18px 50px rgb(0 0 0 / 55%), 0 0 60px rgb(64 196 150 / 14%); }
  /* Медленный блик по сукну — как живой свет лампы над столом. */
  .felt-table::after { content: ''; position: absolute; inset: -40% -60%; background: linear-gradient(105deg, transparent 42%, rgb(255 240 200 / 7%) 50%, transparent 58%); animation: feltSheen 9s ease-in-out infinite; pointer-events: none; }
  .table-orbit { position: absolute; inset: 16px; border: 1px solid rgb(142 228 182 / 12%); border-radius: 42% / 20%; pointer-events: none; }
  .orbit-two { inset: 28px; border-color: rgb(231 187 112 / 12%); }
  .dealer-line { position: relative; z-index: 1; display: flex; align-items: center; gap: 9px; justify-self: center; padding: 6px 12px 6px 6px; border: 1px solid rgb(255 247 237 / 16%); border-radius: 999px; background: rgb(11 11 17 / 55%); color: rgb(255 247 237 / 80%); font-size: 9px; font-weight: 800; letter-spacing: 0.12em; }
  .dealer-avatar { width: 34px; height: 34px; border: 1px solid rgb(231 187 112 / 70%); border-radius: 50%; object-fit: cover; object-position: 50% 12%; background: #3b2430; }
  .dealer-copy b { color: var(--brass-300); }
  .dealer-copy small { color: rgb(255 247 237 / 55%); font-weight: 700; }
  .hand { position: relative; z-index: 1; display: grid; justify-items: center; gap: 8px; }
  .hand-label { color: rgb(255 247 237 / 68%); font-size: 9px; font-weight: 800; letter-spacing: 0.16em; }
  .hand-label b { color: var(--brass-300); }
  .cards { display: flex; flex-wrap: wrap; justify-content: center; gap: 4px; }
  /* Карта Deck A: портрет на всю площадь, как в одобренном превью assets/design/blackjack-gfl/deck-a. */
  .playing-card { position: relative; display: grid; align-content: end; width: 104px; aspect-ratio: 2.5 / 3.65; overflow: hidden; padding: 0 8px 9px; margin-left: -10px; border: 1px solid #b9a27a; border-radius: 9px; background: linear-gradient(155deg, #24232b, #0d1017 62%); color: #f4ece0; box-shadow: 0 8px 16px rgb(0 0 0 / 45%); transform: translate3d(0, var(--card-offset), 0) rotate(var(--card-rotation)); animation: dealCard 440ms var(--ease-spring) var(--card-delay) both; backface-visibility: hidden; will-change: transform, opacity; }
  .playing-card:first-child { margin-left: 0; }
  .playing-card::before { content: ''; position: absolute; z-index: 1; inset: 4px; border: 1px solid rgb(215 189 129 / 25%); border-radius: 5px; pointer-events: none; }
  .playing-card::after { content: ''; position: absolute; inset: 0; background: linear-gradient(180deg, rgb(9 11 18 / 45%) 0%, transparent 26%, rgb(10 11 16 / 92%) 100%); }
  .portrait, .back-art { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  .portrait { object-position: 50% 15%; filter: saturate(0.9) contrast(1.04); }
  .hole-card { place-items: center; align-content: center; border-color: rgb(231 187 112 / 60%); background: #1d2b33; }
  .hole-card::after { background: none; }
  .corner { position: absolute; z-index: 2; color: #fff; font: 700 15px/1 Georgia, serif; text-shadow: 0 2px 6px #000; }
  .corner.top { top: 7px; left: 8px; }
  .corner.bottom { right: 7px; top: 7px; color: #e6c17b; font-size: 12px; }
  .red .corner.bottom { color: #e47d83; }
  .dossier { position: relative; z-index: 2; display: grid; gap: 1px; text-align: left; }
  .dossier strong { font: 700 13px/1.05 Georgia, serif; text-shadow: 0 2px 8px #000; overflow-wrap: anywhere; }
  .dossier em { color: #c3bdb8; font-style: normal; font-size: 8px; font-weight: 800; letter-spacing: 0.06em; }
  .red .dossier em { color: #e9a3a8; }
  .sources { margin-top: 0; color: var(--muted, #b9b2a8); font-size: 11px; }
  .sources summary { min-height: 44px; display: flex; align-items: center; cursor: pointer; }
  .sources p { margin: 6px 0; }
  .sources a { color: inherit; }
  .ghost { color: rgb(255 247 237 / 55%); font-size: 11px; }
  .total { color: rgb(255 247 237 / 72%); font-size: 13px; font-weight: 800; }
  .total.bright { color: var(--brass-300); }
  .table-mark { position: absolute; top: 50%; left: 50%; color: rgb(231 187 112 / 15%); font-size: 58px; font-weight: 800; transform: translate(-50%, -50%); }
  .bet-panel { --bet-accent: var(--brass-300); --bet-line: rgb(255 247 237 / 16%); --bet-ink: var(--ivory); display: grid; gap: 10px; padding: 14px; border: 1px solid rgb(231 187 112 / 26%); border-radius: 20px; background: rgb(10 12 16 / 72%); backdrop-filter: blur(12px); box-shadow: 0 14px 40px rgb(0 0 0 / 45%); }
  .bet-hint { max-width: none; color: #ff9cae; font-size: 11px; }
  .deal-action { min-height: 52px; border: 0; border-radius: 15px; background: linear-gradient(120deg, var(--brass-300), #c98f4e); color: #2a1820; font: inherit; font-size: 14px; font-weight: 850; cursor: pointer; }
  .deal-action:disabled { cursor: not-allowed; filter: saturate(0.6); opacity: 0.75; }
  .action-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .action-grid button { min-height: 58px; border: 1px solid rgb(255 247 237 / 18%); border-radius: 16px; background: rgb(10 12 16 / 72%); color: var(--ivory); font-weight: 800; font-size: 14px; letter-spacing: .04em; cursor: pointer; backdrop-filter: blur(10px); transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease, background 180ms ease; }
  .action-grid button:hover:not(:disabled) { transform: translateY(-2px); border-color: rgb(231 187 112 / 60%); box-shadow: 0 6px 22px rgb(213 144 59 / 28%); }
  .action-grid button:active:not(:disabled) { transform: translateY(1px) scale(.97); }
  .action-grid button small { display: block; color: var(--muted); font-size: 9px; font-weight: 700; }
  .action-grid button:disabled { cursor: wait; opacity: 0.65; }
  .action-grid .action-primary { border-color: rgb(231 187 112 / 70%); background: linear-gradient(180deg, rgb(239 192 107 / 22%), rgb(10 12 16 / 75%)); box-shadow: 0 0 18px rgb(213 144 59 / 22%); }
  .bj-status { display: flex; align-items: center; justify-content: center; gap: 10px; color: var(--muted); font-size: 9px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }
  .bj-status strong { color: var(--brass-300); }
  .demo-note { max-width: none; padding: 10px 12px; border: 1px dashed rgb(231 187 112 / 48%); border-radius: 12px; background: rgb(231 187 112 / 8%); color: var(--brass-300); font-size: 11px; font-weight: 800; line-height: 1.45; }
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
  button:focus-visible { outline: 2px solid var(--brass-300); outline-offset: 3px; }
  @keyframes feltSheen { 0%, 100% { transform: translateX(-30%); } 50% { transform: translateX(30%); } }
  @keyframes dealCard {
    from { opacity: 0; transform: translate3d(0, calc(-140px + var(--card-offset)), 0) rotate(calc(var(--card-rotation) - 8deg)) scale(0.92); }
    to { opacity: 1; transform: translate3d(0, var(--card-offset), 0) rotate(var(--card-rotation)) scale(1); }
  }
  .blackjack-room { gap: 8px; }
  .blackjack-room[data-game-phase='player_turn'] .room-intro { display: none; }
  .blackjack-room[data-game-phase='settled'] .room-intro { display: none; }
  .felt-table { min-height: 280px; padding: 14px 12px; gap: 8px; }
  .blackjack-room[data-game-phase='player_turn'] .felt-table { margin-top: 70px; }
  .playing-card { width: 78px; padding: 0 6px 6px; }
  .blackjack-room[data-game-phase='settled'] .playing-card { width: 66px; flex-basis: 66px; }
  .blackjack-room[data-game-phase='settled'] .total { display: none; }
  .blackjack-room[data-game-phase='waiting'] .felt-table { min-height: 190px; }
  .dealer-line { padding: 3px 9px 3px 3px; }
  .dealer-avatar { width: 28px; height: 28px; }
  .dealer-copy small { display: none; }
  .hand { gap: 4px; }
  .cards { flex-wrap: nowrap; max-width: 100%; }
  .cards .playing-card { flex: 0 1 78px; min-width: 34px; }
  .dossier strong { font-size: 10px; }
  .bet-panel { padding: 8px; gap: 8px; backdrop-filter: none; }
  .bet-settings summary { display: flex; align-items: center; justify-content: space-between; min-height: 44px; cursor: pointer; font-size: 12px; color: #ffe0a1; }
  .bet-settings summary span { font-size: 10px; }
  .action-grid button { min-height: 48px; backdrop-filter: none; }
  .dealer-deck { position: absolute; top: 15px; right: 27px; width: 23px; height: 34px; transform: rotate(12deg); border-radius: 3px; border: 1px solid #d1ac72; box-shadow: 3px 3px #0c171e, 5px 5px #d1ac72; }
  .dealer-deck img { width: 100%; height: 100%; object-fit: cover; border-radius: inherit; }
  .win-light, .loss-shade { position: absolute; inset: 0; pointer-events: none; border-radius: inherit; }
  .win-light { background: radial-gradient(ellipse,#ffe3a766,transparent 72%); animation: tableWin 900ms ease-out both; }
  .loss-shade { background: #03071066; animation: lossIn 300ms ease both; }
  .prize-chips { position: absolute; left: 50%; top: 43%; display: flex; gap: 6px; pointer-events: none; }
  .prize-chips i { width: 24px; height: 12px; border-radius: 50%; background: #d4a450; border: 3px dashed #fff0bc; box-shadow: 0 3px #705029; animation: chipsToPlayer 750ms ease-out both; }
  .prize-chips i:nth-child(2) { animation-delay: 90ms; }
  .prize-chips i:nth-child(3) { animation-delay: 180ms; }
  .playing-card.revealed { overflow: visible; transform-style: preserve-3d; backface-visibility: visible; animation: dealerFlip 620ms ease both; }
  .card-front { position: absolute; inset: 0; display: grid; align-content: end; padding: 0 6px 6px; overflow: hidden; border-radius: inherit; background: #0d1017; backface-visibility: hidden; }
  .flip-back { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; border-radius: inherit; transform: rotateY(180deg); backface-visibility: hidden; }
  .card-front::after { content: ''; position: absolute; inset: 0; background: linear-gradient(transparent 35%,#0a0b10ee); }
  .dealer-hand .cards { perspective: 900px; }
  @keyframes dealerFlip { from { transform: translateY(var(--card-offset)) rotate(var(--card-rotation)) rotateY(-180deg); } to { transform: translateY(var(--card-offset)) rotate(var(--card-rotation)) rotateY(0); } }
  @keyframes tableWin { 0% { opacity: 0; transform: scale(.7); } 30% { opacity: 1; } 100% { opacity: 0; transform: scale(1.3); } }
  @keyframes chipsToPlayer { from { opacity: 0; transform: translate(-50%,0) scale(.5); } 20% { opacity: 1; } to { opacity: 0; transform: translate(-50%,130px) scale(1.2); } }
  @keyframes lossIn { from { opacity: 0; } to { opacity: 1; } }
  @media (max-width: 390px) {
    .playing-card { width: 78px; }
  }
  @media (min-width: 720px) {
    .playing-card { width: 118px; }
  }
  @media (prefers-reduced-motion: reduce) {
    .playing-card, .playing-card.revealed, .win-light, .loss-shade, .prize-chips i { animation: none; }
    .win-light, .prize-chips { display: none; }
    .action-grid button { transition: none; }
    .felt-table::after { animation: none; }
  }
</style>
