<script lang="ts">
  import { onMount } from 'svelte';

  import HubLobby from '$lib/components/hub/HubLobby.svelte';
  import { fade } from 'svelte/transition';

  import RoomShell from '$lib/components/RoomShell.svelte';
  import WalletGrantControls from '$lib/components/WalletGrantControls.svelte';
  import Leaderboard from '$lib/components/Leaderboard.svelte';
  import LedgerHistory from '$lib/components/LedgerHistory.svelte';
  import type { ApiLedgerResult } from '$lib/api/client';
  import { getTelegramWebApp } from '$lib/telegram/webapp';
  import BlackjackRoom from '$lib/rooms/BlackjackRoom.svelte';
  import PokerRoom from '$lib/rooms/PokerRoom.svelte';
  import SlotRoom from '$lib/rooms/SlotRoom.svelte';
  import {
    SLOT_ACTION_ACCEPT_DELAY,
    SLOT_SERVER_RESULT_PRELUDE,
    SLOT_SETTLE_DURATION,
    SLOT_TOTAL_DURATION,
    type SlotOutcome
  } from '$lib/game/slot';
  import { ApiClient, type ApiEventEnvelope } from '$lib/api/client';
  import {
    buildRoomActionPayload,
    isLiveApiEnabled,
    mapApiEventResult,
    mapApiPublicStateResult
  } from '$lib/api/runtime';
  import { SessionState } from '$lib/state/session.svelte';
  import {
    getResultBalance,
    RoomState,
    type BlackjackOutcome,
    type GameType,
    type RoomResult
  } from '$lib/state/room.svelte';

  const PUBLIC_API_BASE_URL = import.meta.env.PUBLIC_API_BASE_URL ?? '';

  const session = new SessionState();
  const roomState = new RoomState();

  const roomDefinitions = [
    {
      gameType: 'slot' as const,
      eyebrow: '3×7 · SKELETON',
      title: 'Однорукий бандит',
      description: 'Три барабана, чёткий payline и короткий раунд.',
      accent: '#e7bb70',
      icon: '✦',
      rulesetVersion: 'slot-siege-demo-1'
    },
    {
      gameType: 'blackjack' as const,
      eyebrow: 'GFL · SKELETON',
      title: 'Blackjack',
      description: 'Дилер, рука игрока и решение без лишнего шума.',
      accent: '#8ee4b6',
      icon: '♠',
      rulesetVersion: 'blackjack-skeleton-1'
    },
    {
      gameType: 'holdem' as const,
      eyebrow: 'HEADS-UP · КАМУРО-ТЁ',
      title: 'Hold’em',
      description: 'Один pot, два места и понятная линия действия.',
      accent: '#ce86f2',
      icon: '♣',
      rulesetVersion: 'holdem-v1'
    }
  ];

  const demoPokerResult: RoomResult = {
    headline: 'Рука подтверждена',
    detail: 'Демо-исход: сервер не подтверждал этот результат.',
    amount: 75
  };

  const demoSlotReels = [
    ['D1', 'D2', 'D3', 'D4', 'A1', 'A2', 'A3'],
    ['D2', 'A1', 'D1', 'D4', 'W', 'A3', 'D3'],
    ['D3', 'W', 'A1', 'D4', 'D1', 'A2', 'D2']
  ];

  const DEMO_BLACKJACK_RULESET = 'blackjack-demo-1';
  const DEMO_BLACKJACK_PLAYER_CARDS = [
    { rank: '10', suit: 'spades' },
    { rank: '7', suit: 'hearts' }
  ];
  const DEMO_BLACKJACK_DEALER_CARDS = [{ rank: '9', suit: 'clubs' }];
  const DEMO_BLACKJACK_DEALER_DRAW = { rank: '3', suit: 'diamonds' };
  const DEMO_BLACKJACK_DRAWS = [
    { rank: '3', suit: 'diamonds' },
    { rank: '2', suit: 'clubs' }
  ];

  interface DemoBlackjackHand {
    bet: number;
    playerCards: Array<Record<string, unknown>>;
    dealerCards: Array<Record<string, unknown>>;
    holeHidden: boolean;
    playerTotal: number;
    dealerTotal: number | null;
    phase: string;
    legalActions: string[];
    drawIndex: number;
    outcome: BlackjackOutcome | null;
  }

  let demoBlackjack: DemoBlackjackHand | null = null;

  let selectedGame: GameType | null = null;
  let hubActivity: GameType = 'slot';
  let hubPanel: 'play' | 'ranking' | 'history' = 'play';
  let hubMotionPaused = false;
  let pokerRoom: PokerRoom | null = null;
  let isRunning = false;
  let timers: number[] = [];
  let motionQuery: MediaQueryList | undefined;
  let demoFreeSpinsRemaining = 0;
  let apiClient: ApiClient | null = null;
  let liveApiEnabled = false;
  let ledgerReady = false;
  let ledgerRevision = 0;
  let apiLoading = false;
  let apiError: string | null = null;
  let closeRoomStream: (() => void) | null = null;

  function clearTimers() {
    for (const timer of timers) window.clearTimeout(timer);
    timers = [];
  }

  function after(delay: number, callback: () => void) {
    if (session.reducedMotion) {
      callback();
      return;
    }
    timers = [...timers, window.setTimeout(callback, delay)];
  }

  function updateBalanceFromResult(result: RoomResult | null) {
    const balance = getResultBalance(result);
    if (balance !== null) session.setBalance(balance);
  }

  function updateBalanceFromPublicState(publicState: Record<string, unknown>) {
    const balance = publicState.wallet_balance;
    if (typeof balance === 'number' && Number.isInteger(balance) && balance >= 0) {
      session.setBalance(balance);
    }
  }

  function connectRoomStream(roomId: string) {
    if (!apiClient) return;
    closeRoomStream?.();
    closeRoomStream = apiClient.subscribeToRoom(
      roomId,
      (snapshot) => {
        if (roomState.snapshot?.roomId !== roomId) return;
        ledgerRevision += 1;
        roomState.setSnapshot(snapshot);
        updateBalanceFromPublicState(snapshot.publicState);
        const snapshotResult = mapApiPublicStateResult(snapshot.publicState, snapshot.gameType);
        if (snapshotResult) {
          roomState.restoreConfirmedResult(snapshotResult);
          updateBalanceFromResult(snapshotResult);
        }
      },
      (event) => {
        if (roomState.snapshot?.roomId !== roomId) return;
        if (event.state_version < roomState.snapshot.stateVersion) return;
        ledgerRevision += 1;
        const publicState = publicStateFromEvent(event);
        const nextSnapshot = {
          ...roomState.snapshot,
          stateVersion: event.state_version,
          publicState
        };
        roomState.setSnapshot(nextSnapshot);
        updateBalanceFromPublicState(publicState);
        roomState.setResult(mapApiEventResult(event, nextSnapshot.gameType));
      }
    );
  }

  async function openRoom(gameType: GameType) {
    if (apiLoading) return;
    clearTimers();
    isRunning = false;
    selectedGame = gameType;
    demoFreeSpinsRemaining = 0;
    demoBlackjack = null;
    const definition = roomDefinitions.find((room) => room.gameType === gameType);
    if (!definition) return;

    apiError = null;
    if (liveApiEnabled && apiClient && gameType !== 'holdem') {
      apiLoading = true;
      session.setConnection('connecting');
      try {
        const snapshot = await apiClient.createRoom(gameType, 'solo');
        roomState.setSnapshot(snapshot);
        roomState.reset();
        connectRoomStream(snapshot.roomId);
        session.setConnection('connected');
      } catch (error) {
        selectedGame = null;
        session.setConnection('offline');
        apiError = error instanceof Error ? error.message : 'Не удалось открыть комнату';
      } finally {
        apiLoading = false;
      }
      return;
    }

    session.setConnection(liveApiEnabled ? 'connected' : 'demo');
    roomState.setSnapshot({
      roomId: `demo-${gameType}`,
      gameType,
      title: definition.title,
      rulesetVersion: definition.rulesetVersion,
      stateVersion: 1,
      publicState: { demo: true }
    });
    roomState.reset();
  }

  // Демо-выплата масштабируется от выбранной ставки; Free Spin берёт ставку последнего спина.
  let demoSlotBet = 10;

  function buildDemoSlotResult(action: string, fields: Record<string, unknown> = {}): RoomResult {
    const isFreeSpin = action === 'free-spin';
    if (!isFreeSpin && typeof fields.bet === 'number') demoSlotBet = fields.bet;
    const payout = demoSlotBet * (isFreeSpin ? 6 : 4);
    demoFreeSpinsRemaining = isFreeSpin
      ? Math.max(0, demoFreeSpinsRemaining - 1)
      : 5;

    const slotOutcome: SlotOutcome = {
      reels: demoSlotReels,
      winningRows: [3],
      payout,
      balance: session.balance + payout,
      freeSpinsAwarded: isFreeSpin ? 0 : 5,
      freeSpinsRemaining: demoFreeSpinsRemaining
    };

    return {
      headline: isFreeSpin ? 'Free Spin подтверждён' : 'Линия подтверждена',
      detail: 'Демо-исход: сервер не подтверждал этот результат.',
      amount: slotOutcome.payout,
      slotOutcome
    };
  }

  function blackjackTotal(cards: Array<Record<string, unknown>>): number {
    let total = 0;
    let aces = 0;
    for (const card of cards) {
      const rank = card.rank;
      if (rank === 'A') {
        aces += 1;
        total += 11;
      } else if (rank === 'K' || rank === 'Q' || rank === 'J' || rank === '10') {
        total += 10;
      } else {
        total += Number(rank);
      }
    }
    while (total > 21 && aces > 0) {
      total -= 10;
      aces -= 1;
    }
    return total;
  }

  function demoBlackjackPublicState(): Record<string, unknown> {
    if (!demoBlackjack) return { demo: true };
    return {
      demo: true,
      game_phase: demoBlackjack.phase,
      bet: demoBlackjack.bet,
      player_cards: demoBlackjack.playerCards,
      dealer_cards: demoBlackjack.holeHidden
        ? [...demoBlackjack.dealerCards, { hidden: true }]
        : demoBlackjack.dealerCards,
      dealer_hole_hidden: demoBlackjack.holeHidden,
      player_total: demoBlackjack.playerTotal,
      ...(demoBlackjack.dealerTotal === null ? {} : { dealer_total: demoBlackjack.dealerTotal }),
      legal_actions: demoBlackjack.legalActions,
      ruleset_version: DEMO_BLACKJACK_RULESET,
      wallet_balance: session.balance
    };
  }

  function syncDemoBlackjackSnapshot() {
    if (!roomState.snapshot) return;
    roomState.setSnapshot({ ...roomState.snapshot, publicState: demoBlackjackPublicState() });
  }

  function settleDemoBlackjack(playerBusted = false) {
    if (!demoBlackjack) return;
    const dealerCards = [...demoBlackjack.dealerCards, DEMO_BLACKJACK_DEALER_DRAW];
    const dealerTotal = blackjackTotal(dealerCards);
    const playerTotal = demoBlackjack.playerTotal;
    const outcome: BlackjackOutcome['outcome'] = playerBusted
      ? 'loss'
      : playerTotal > dealerTotal
        ? 'win'
        : playerTotal === dealerTotal
          ? 'push'
          : 'loss';
    const netDelta =
      outcome === 'win' ? demoBlackjack.bet : outcome === 'push' ? 0 : -demoBlackjack.bet;

    demoBlackjack = {
      ...demoBlackjack,
      dealerCards,
      dealerTotal,
      holeHidden: false,
      phase: 'settled',
      legalActions: ['deal'],
      outcome: {
        outcome,
        playerTotal,
        dealerTotal,
        grossPayout: outcome === 'loss' ? 0 : demoBlackjack.bet + Math.max(0, netDelta),
        netDelta,
        balanceAfter: session.balance + netDelta,
        rulesetVersion: DEMO_BLACKJACK_RULESET,
        finalBet: demoBlackjack.bet
      }
    };
  }

  function runDemoBlackjackAction(action: string, fields: Record<string, unknown>) {
    if (action === 'deal') {
      const bet = typeof fields.bet === 'number' ? fields.bet : 25;
      const playerCards = [...DEMO_BLACKJACK_PLAYER_CARDS];
      demoBlackjack = {
        bet,
        playerCards,
        dealerCards: [...DEMO_BLACKJACK_DEALER_CARDS],
        holeHidden: true,
        playerTotal: blackjackTotal(playerCards),
        dealerTotal: null,
        phase: 'player_turn',
        legalActions: ['hit', 'stand', 'double'],
        drawIndex: 0,
        outcome: null
      };
      return;
    }

    if (!demoBlackjack || demoBlackjack.phase !== 'player_turn') return;

    if (action === 'hit' || action === 'double') {
      const draw = DEMO_BLACKJACK_DRAWS[demoBlackjack.drawIndex % DEMO_BLACKJACK_DRAWS.length];
      const playerCards = [...demoBlackjack.playerCards, draw];
      demoBlackjack = {
        ...demoBlackjack,
        bet: action === 'double' ? demoBlackjack.bet * 2 : demoBlackjack.bet,
        playerCards,
        playerTotal: blackjackTotal(playerCards),
        // Как в домене: double разрешён только на стартовой руке из двух карт.
        legalActions: ['hit', 'stand'],
        drawIndex: demoBlackjack.drawIndex + 1
      };
      if (demoBlackjack.playerTotal > 21) {
        settleDemoBlackjack(true);
        return;
      }
      if (action === 'double') settleDemoBlackjack();
      return;
    }

    if (action === 'stand') settleDemoBlackjack();
  }

  function demoBlackjackResult(): RoomResult | null {
    const outcome = demoBlackjack?.outcome;
    if (!outcome) return null;
    const headlines = {
      blackjack: 'Натуральный блэкджек',
      win: 'Раунд выигран',
      push: 'Возврат ставки',
      loss: 'Раунд завершён'
    } as const;
    return {
      headline: headlines[outcome.outcome],
      detail: `${outcome.playerTotal} против ${outcome.dealerTotal}; демо-раунд, сервер не подтверждал.`,
      amount: outcome.grossPayout,
      blackjackOutcome: outcome
    };
  }

  function runDemoAction(action: string, fields: Record<string, unknown> = {}) {
    if (!selectedGame || isRunning || !roomState.snapshot) return;
    clearTimers();
    isRunning = true;
    roomState.setResult(null);
    roomState.transition({ type: 'USER_INTENT' }, session.reducedMotion);

    if (selectedGame === 'blackjack') {
      runDemoBlackjackAction(action, fields);
      syncDemoBlackjackSnapshot();
      const demoResult = demoBlackjackResult();

      after(SLOT_ACTION_ACCEPT_DELAY, () => {
        roomState.transition({ type: 'ACTION_ACCEPTED' }, session.reducedMotion);
        if (!demoResult) {
          clearTimers();
          roomState.reset();
          isRunning = false;
          return;
        }
        roomState.setResult(demoResult);
        after(360, () => {
          roomState.transition({ type: 'RESULT_CONFIRMED' }, session.reducedMotion);
          updateBalanceFromResult(demoResult);
          syncDemoBlackjackSnapshot();
          after(360, () => {
            roomState.transition({ type: 'SETTLE_COMPLETE' }, session.reducedMotion);
            isRunning = false;
          });
        });
      });
      return;
    }

    const confirmedResult = selectedGame === 'slot' ? buildDemoSlotResult(action, fields) : demoPokerResult;

    after(SLOT_ACTION_ACCEPT_DELAY, () => {
      roomState.transition({ type: 'ACTION_ACCEPTED' }, session.reducedMotion);
      if (selectedGame === 'slot') {
        after(SLOT_SERVER_RESULT_PRELUDE, () => roomState.setResult(confirmedResult));
        after(SLOT_TOTAL_DURATION, () => {
          roomState.transition({ type: 'RESULT_CONFIRMED' }, session.reducedMotion);
          updateBalanceFromResult(confirmedResult);
          after(SLOT_SETTLE_DURATION, () => {
            roomState.transition({ type: 'SETTLE_COMPLETE' }, session.reducedMotion);
            isRunning = false;
          });
        });
        return;
      }

      after(360, () => {
        roomState.setResult(confirmedResult);
        after(360, () => {
          roomState.transition({ type: 'RESULT_CONFIRMED' }, session.reducedMotion);
          after(360, () => {
            roomState.transition({ type: 'SETTLE_COMPLETE' }, session.reducedMotion);
            isRunning = false;
          });
        });
      });
    });
  }

  function publicStateFromEvent(event: ApiEventEnvelope) {
    const publicState = event.payload.public_state;
    return typeof publicState === 'object' && publicState !== null
      ? (publicState as Record<string, unknown>)
      : {};
  }

  async function reloadRoomSnapshot(roomId: string): Promise<boolean> {
    if (!apiClient) return false;
    try {
      const snapshot = await apiClient.getRoom(roomId);
      if (roomState.snapshot?.roomId !== roomId) return false;
      roomState.setSnapshot(snapshot, true);
      updateBalanceFromPublicState(snapshot.publicState);
      ledgerRevision += 1;
      const snapshotResult = mapApiPublicStateResult(snapshot.publicState, snapshot.gameType);
      if (snapshotResult) {
        roomState.restoreConfirmedResult(snapshotResult);
        updateBalanceFromResult(snapshotResult);
      }
      session.setConnection('connected');
      return true;
    } catch {
      session.setConnection('offline');
      return false;
    }
  }

  async function runLiveAction(action: string, fields: Record<string, unknown> = {}) {
    if (!apiClient || !selectedGame || isRunning || !roomState.snapshot) return;
    clearTimers();
    isRunning = true;
    apiError = null;
    roomState.setResult(null);
    roomState.transition({ type: 'USER_INTENT' }, session.reducedMotion);
    const roomAtStart = roomState.snapshot;
    const startedAt = performance.now();
    const actionId = crypto.randomUUID();
    const actionPayload = buildRoomActionPayload(action, fields);

    after(SLOT_ACTION_ACCEPT_DELAY, () => {
      roomState.transition({ type: 'ACTION_ACCEPTED' }, session.reducedMotion);
    });

    try {
      const response = await apiClient.applyAction(
        roomAtStart.roomId,
        roomAtStart.stateVersion,
        actionId,
        actionPayload
      );
      ledgerRevision += 1;

      if (!selectedGame || roomState.snapshot?.roomId !== roomAtStart.roomId) return;
      const event = response.event;
      const publicState = publicStateFromEvent(event);
      roomState.setSnapshot({
        ...roomState.snapshot,
        stateVersion: event.state_version,
        publicState
      });
      updateBalanceFromPublicState(publicState);
      roomState.transition({ type: 'ACTION_ACCEPTED' }, session.reducedMotion);

      if (!selectedGame || roomState.snapshot?.roomId !== roomAtStart.roomId) return;
      const confirmedResult = mapApiEventResult(event, selectedGame);
      roomState.setResult(confirmedResult);
      if (!confirmedResult) {
        clearTimers();
        roomState.reset();
        isRunning = false;
        return;
      }
      const resultDelay = selectedGame === 'slot'
        ? Math.max(0, SLOT_TOTAL_DURATION - (performance.now() - startedAt))
        : 360;
      after(resultDelay, () => {
        if (!selectedGame || roomState.snapshot?.roomId !== roomAtStart.roomId) return;
        roomState.transition({ type: 'RESULT_CONFIRMED' }, session.reducedMotion);
        updateBalanceFromResult(confirmedResult);
        after(selectedGame === 'slot' ? SLOT_SETTLE_DURATION : 360, () => {
          roomState.transition({ type: 'SETTLE_COMPLETE' }, session.reducedMotion);
          isRunning = false;
        });
      });
    } catch (error) {
      clearTimers();
      apiError = error instanceof Error ? error.message : 'Сервер не подтвердил действие';
      roomState.reset();
      // Stay busy until the room has been re-read, so a fresh tap cannot race the reload.
      await reloadRoomSnapshot(roomAtStart.roomId);
      isRunning = false;
    }
  }

  function applyConfirmedGrant(confirmed: ApiLedgerResult) {
    if (!Number.isInteger(confirmed.balance_after) || confirmed.balance_after < 0) return;
    session.setBalance(confirmed.balance_after);
    ledgerRevision += 1;
  }

  function runAction(action: string, fields: Record<string, unknown> = {}) {
    if (liveApiEnabled && apiClient) {
      void runLiveAction(action, fields);
      return;
    }
    runDemoAction(action, fields);
  }

  async function resync() {
    if (selectedGame === 'holdem') { await pokerRoom?.resync(); return; }
    if (!roomState.snapshot) return;
    clearTimers();
    isRunning = false;
    roomState.setResult(null);
    apiError = null;
    session.setConnection('syncing');

    if (liveApiEnabled && apiClient) {
      const reloaded = await reloadRoomSnapshot(roomState.snapshot.roomId);
      if (!reloaded) apiError = 'Не удалось синхронизировать комнату';
      return;
    }

    after(320, () => {
      session.setConnection('demo');
      if (roomState.snapshot) roomState.setSnapshot(roomState.snapshot, true);
    });
  }

  function backToRooms() {
    clearTimers();
    closeRoomStream?.();
    closeRoomStream = null;
    isRunning = false;
    roomState.reset();
    selectedGame = null;
    session.setConnection(liveApiEnabled ? 'connected' : 'demo');
  }

  onMount(() => {
    const webApp = getTelegramWebApp();
    webApp.ready();
    webApp.expand();
    webApp.setHeaderColor('#0b0b11');
    webApp.setBackgroundColor('#0b0b11');

    liveApiEnabled = isLiveApiEnabled(PUBLIC_API_BASE_URL, webApp.initData);
    if (liveApiEnabled) {
      apiClient = new ApiClient(PUBLIC_API_BASE_URL, webApp.initData);
      session.setConnection('connecting');
      void apiClient.getWallet().then((wallet) => {
        session.setBalance(wallet.balance, wallet.currency_code);
        session.setConnection('connected');
      }).catch((error) => {
        session.setConnection('offline');
        apiError = error instanceof Error ? error.message : 'Не удалось подключиться к API';
      }).finally(() => {
        ledgerReady = true;
      });
    }

    motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const updateMotionPreference = () => session.setReducedMotion(motionQuery?.matches ?? false);
    updateMotionPreference();
    motionQuery.addEventListener('change', updateMotionPreference);

    return () => {
      clearTimers();
      closeRoomStream?.();
      closeRoomStream = null;
      motionQuery?.removeEventListener('change', updateMotionPreference);
    };
  });
</script>

<svelte:head>
  <title>Бурмалдоза · Casino lounge</title>
  <meta name="description" content="Игровой лаунж Бурмалдозы: слоты, blackjack и heads-up hold’em." />
</svelte:head>

<div class="app-shell" class:hub-mode={!selectedGame || !roomState.snapshot}>
  {#if selectedGame && roomState.snapshot}
    <div class="room-entry" in:fade={{duration:session.reducedMotion || hubMotionPaused ? 0 : 180}}>
    <RoomShell room={roomState.snapshot} connection={session.connection} motion={roomState.motion} onBack={backToRooms} onResync={resync}>
      {#if selectedGame === 'slot'}
        <SlotRoom motion={roomState.motion} result={roomState.result} onAction={runAction} resultSource={liveApiEnabled ? 'live' : 'demo'} rulesetVersion={roomState.snapshot.rulesetVersion} publicState={roomState.snapshot.publicState} />
      {:else if selectedGame === 'blackjack'}
        <BlackjackRoom
          snapshot={roomState.snapshot}
          motion={roomState.motion}
          result={roomState.result}
          pending={isRunning}
          apiError={apiError}
          onAction={runAction}
          resultSource={liveApiEnabled ? 'live' : 'demo'}
        />
      {:else}
        <PokerRoom bind:this={pokerRoom} client={apiClient} live={liveApiEnabled} reducedMotion={session.reducedMotion} onBalance={(balance) => { session.setBalance(balance); ledgerRevision += 1; }} />
      {/if}
    </RoomShell>
    </div>
  {:else}
    <div in:fade={{duration:session.reducedMotion || hubMotionPaused ? 0 : 180}}>
      <HubLobby balance={session.balance} balanceReady={!liveApiEnabled || ledgerReady} currencyCode={session.currencyCode} connection={session.connection} live={liveApiEnabled} busy={apiLoading} {apiError} reducedMotion={session.reducedMotion} bind:paused={hubMotionPaused} bind:activity={hubActivity} bind:panel={hubPanel} onOpen={openRoom}>
        <Leaderboard slot="ranking" apiClient={ledgerReady ? apiClient : null} live={liveApiEnabled} revision={ledgerRevision} />
        <LedgerHistory slot="history" apiClient={ledgerReady ? apiClient : null} live={liveApiEnabled} revision={ledgerRevision} />
        <svelte:fragment slot="bonus">
          {#if liveApiEnabled && apiClient}
            <WalletGrantControls apiClient={apiClient} live={liveApiEnabled} balance={session.balance} onConfirmed={applyConfirmedGrant} />
          {/if}
        </svelte:fragment>
      </HubLobby>
    </div>
  {/if}
  {#if selectedGame && roomState.snapshot}
  <Leaderboard apiClient={ledgerReady ? apiClient : null} live={liveApiEnabled} revision={ledgerRevision} />
  <LedgerHistory apiClient={ledgerReady ? apiClient : null} live={liveApiEnabled} revision={ledgerRevision} />
  {/if}
</div>

<style>
  @import '$lib/styles/tokens.css';
  :global(html) { min-width: 320px; background: var(--ink-950); }
  :global(body) { min-width: 320px; }
  :global(button) { font-family: inherit; }
  :global(button:focus-visible) { outline: 2px solid var(--brass-300); outline-offset: 3px; }
  .app-shell { width: min(100%, 760px); min-height: 100dvh; margin: 0 auto; padding: max(18px, env(safe-area-inset-top)) max(16px, env(safe-area-inset-right)) max(24px, env(safe-area-inset-bottom)) max(16px, env(safe-area-inset-left)); }
  .app-shell.hub-mode { width: 100%; padding: 0; }
</style>
