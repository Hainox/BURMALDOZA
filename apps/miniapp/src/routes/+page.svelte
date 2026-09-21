<script lang="ts">
  import { onMount } from 'svelte';

  import BalancePill from '$lib/components/BalancePill.svelte';
  import RoomCard from '$lib/components/RoomCard.svelte';
  import RoomShell from '$lib/components/RoomShell.svelte';
  import { getTelegramWebApp } from '$lib/telegram/webapp';
  import BlackjackRoom from '$lib/rooms/BlackjackRoom.svelte';
  import PokerRoom from '$lib/rooms/PokerRoom.svelte';
  import SlotRoom from '$lib/rooms/SlotRoom.svelte';
  import { SLOT_REVEAL_DURATION, type SlotOutcome } from '$lib/game/slot';
  import { SessionState } from '$lib/state/session.svelte';
  import { RoomState, type GameType, type RoomResult } from '$lib/state/room.svelte';

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
      rulesetVersion: 'slot-skeleton-1'
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
      eyebrow: 'HEADS-UP · SKELETON',
      title: 'Hold’em',
      description: 'Один pot, два места и понятная линия действия.',
      accent: '#ce86f2',
      icon: '♣',
      rulesetVersion: 'holdem-skeleton-1'
    }
  ];

  const demoResults: Record<GameType, RoomResult> = {
    slot: { headline: 'Линия подтверждена', detail: 'Исход пришёл с сервера; анимация только показала его.', amount: 40 },
    blackjack: { headline: 'Стол подтверждён', detail: 'Рука закрыта после серверной раздачи.', amount: 25 },
    holdem: { headline: 'Рука подтверждена', detail: 'Pot рассчитан после подтверждённого действия.', amount: 75 }
  };

  const demoSlotReels = [
    ['♣', '◆', '7', '✦', '♠', 'A', '♦'],
    ['7', '♠', '✦', '✦', '◆', 'Q', '♣'],
    ['◆', '7', '♣', '✦', 'A', '♠', '♦']
  ];

  let selectedGame: GameType | null = null;
  let isRunning = false;
  let timers: number[] = [];
  let motionQuery: MediaQueryList | undefined;
  let demoFreeSpinsRemaining = 0;

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

  function openRoom(gameType: GameType) {
    clearTimers();
    isRunning = false;
    selectedGame = gameType;
    demoFreeSpinsRemaining = 0;
    session.setConnection('demo');
    const definition = roomDefinitions.find((room) => room.gameType === gameType);
    if (!definition) return;
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

  function buildDemoSlotResult(action: string): RoomResult {
    const isFreeSpin = action === 'free-spin';
    demoFreeSpinsRemaining = isFreeSpin
      ? Math.max(0, demoFreeSpinsRemaining - 1)
      : 5;

    const slotOutcome: SlotOutcome = {
      reels: demoSlotReels,
      winningRows: [3],
      payout: isFreeSpin ? 60 : 40,
      balance: session.balance + (isFreeSpin ? 60 : 40),
      freeSpinsAwarded: isFreeSpin ? 0 : 5,
      freeSpinsRemaining: demoFreeSpinsRemaining
    };

    return {
      headline: isFreeSpin ? 'Free Spin подтверждён' : 'Линия подтверждена',
      detail: 'Исход пришёл с сервера; анимация только показала его.',
      amount: slotOutcome.payout,
      slotOutcome
    };
  }

  function runAction(action: string) {
    if (!selectedGame || isRunning || !roomState.snapshot) return;
    void action;
    clearTimers();
    isRunning = true;
    roomState.setResult(null);
    roomState.transition({ type: 'USER_INTENT' }, session.reducedMotion);
    after(140, () => {
      roomState.transition({ type: 'ACTION_ACCEPTED' }, session.reducedMotion);
      after(520, () => {
        roomState.setResult(
          selectedGame === 'slot'
            ? buildDemoSlotResult(action)
            : demoResults[selectedGame as GameType]
        );
        const revealDelay = selectedGame === 'slot' ? SLOT_REVEAL_DURATION : 360;
        after(revealDelay, () => {
          roomState.transition({ type: 'RESULT_CONFIRMED' }, session.reducedMotion);
          after(360, () => {
            roomState.transition({ type: 'SETTLE_COMPLETE' }, session.reducedMotion);
            isRunning = false;
          });
        });
      });
    });
  }

  function resync() {
    if (!roomState.snapshot) return;
    clearTimers();
    isRunning = false;
    roomState.setResult(null);
    session.setConnection('syncing');
    after(320, () => {
      session.setConnection('demo');
      if (roomState.snapshot) roomState.setSnapshot(roomState.snapshot, true);
    });
  }

  function backToRooms() {
    clearTimers();
    isRunning = false;
    roomState.reset();
    selectedGame = null;
    session.setConnection('demo');
  }

  onMount(() => {
    const webApp = getTelegramWebApp();
    webApp.ready();
    webApp.expand();
    webApp.setHeaderColor('#0b0b11');
    webApp.setBackgroundColor('#0b0b11');

    motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const updateMotionPreference = () => session.setReducedMotion(motionQuery?.matches ?? false);
    updateMotionPreference();
    motionQuery.addEventListener('change', updateMotionPreference);

    return () => {
      clearTimers();
      motionQuery?.removeEventListener('change', updateMotionPreference);
    };
  });
</script>

<svelte:head>
  <title>Бурмалдоза · Casino lounge</title>
  <meta name="description" content="Игровой лаунж Бурмалдозы: слоты, blackjack и heads-up hold’em." />
</svelte:head>

<div class="app-shell">
  {#if selectedGame && roomState.snapshot}
    <RoomShell room={roomState.snapshot} connection={session.connection} motion={roomState.motion} onBack={backToRooms} onResync={resync}>
      {#if selectedGame === 'slot'}
        <SlotRoom motion={roomState.motion} result={roomState.result} onAction={runAction} />
      {:else if selectedGame === 'blackjack'}
        <BlackjackRoom motion={roomState.motion} result={roomState.result} onAction={runAction} />
      {:else}
        <PokerRoom motion={roomState.motion} result={roomState.result} onAction={runAction} />
      {/if}
    </RoomShell>
  {:else}
    <main class="dashboard" data-testid="dashboard">
      <header class="topbar">
        <div class="brand-lockup">
          <span class="brand-mark" aria-hidden="true">✦</span>
          <span class="brand-copy"><span>BURMALDOZA</span><strong>AFTER-HOURS CLUB</strong></span>
        </div>
        <BalancePill balance={session.balance} currencyCode={session.currencyCode} connection={session.connection} />
      </header>

      <section class="hero-copy" aria-labelledby="lounge-title">
        <span class="eyebrow">JOKERGEM CLUB · PRIVATE TABLES</span>
        <h1 id="lounge-title">Игровой лаунж</h1>
        <p>Короткие раунды для тех, кто любит хороший ритм, ясные правила и немного театра.</p>
        <div class="hero-meta"><span class="pulse-dot"></span><span>3 комнаты готовы</span><span class="meta-divider">·</span><span>server-first motion</span></div>
      </section>

      <aside class="demo-banner" data-testid="demo-banner" role="status">
        <span class="banner-icon" aria-hidden="true">◎</span>
        <span><strong>ДЕМО-КОНТУР</strong><small>Сейчас показываем механику и движение. Ставки не имеют денежной ценности.</small></span>
      </aside>

      <section class="rooms-section" aria-labelledby="rooms-title">
        <div class="section-heading"><div><span class="eyebrow">CHOOSE YOUR TABLE</span><h2 id="rooms-title">Комнаты</h2></div><span class="room-count">03 / 03</span></div>
        <div class="room-list">
          {#each roomDefinitions as room}
            <RoomCard gameType={room.gameType} eyebrow={room.eyebrow} title={room.title} description={room.description} accent={room.accent} icon={room.icon} onSelect={() => openRoom(room.gameType)} />
          {/each}
        </div>
      </section>

      <footer class="footer-note">
        <span class="footer-mark" aria-hidden="true">✦</span>
        <span><strong>Jokergem</strong> — внутриигровая единица без вывода и денежной ценности.</span>
        <span class="footer-rule" aria-hidden="true"></span>
      </footer>
    </main>
  {/if}
</div>

<style>
  @import '$lib/styles/tokens.css';

  :global(html) { min-width: 320px; background: var(--ink-950); }
  :global(body) { min-width: 320px; }
  :global(button) { font-family: inherit; }
  :global(button:focus-visible) { outline: 2px solid var(--brass-300); outline-offset: 3px; }

  .app-shell { width: min(100%, 760px); min-height: 100dvh; margin: 0 auto; padding: max(18px, env(safe-area-inset-top)) max(16px, env(safe-area-inset-right)) max(24px, env(safe-area-inset-bottom)) max(16px, env(safe-area-inset-left)); }
  .dashboard { display: grid; gap: 28px; }
  .topbar { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
  .brand-lockup { display: inline-flex; align-items: center; gap: 9px; }
  .brand-mark { display: grid; place-items: center; width: 31px; height: 31px; border: 1px solid rgb(231 187 112 / 62%); border-radius: 11px; background: linear-gradient(145deg, rgb(231 187 112 / 22%), rgb(143 53 89 / 22%)); color: var(--brass-300); font-size: 17px; box-shadow: 0 0 22px rgb(231 187 112 / 12%); animation: markFloat 3.8s ease-in-out infinite; }
  .brand-copy { display: grid; gap: 2px; }
  .brand-copy span { color: var(--brass-300); font-size: 9px; font-weight: 850; letter-spacing: 0.16em; }
  .brand-copy strong { color: var(--muted-strong); font-size: 9px; letter-spacing: 0.1em; }
  .hero-copy { display: grid; gap: 8px; padding: 15px 0 1px; }
  .eyebrow { color: var(--brass-300); font-size: 9px; font-weight: 850; letter-spacing: 0.16em; }
  h1 { max-width: 450px; margin: 0; color: var(--ivory); font-size: clamp(40px, 12vw, 72px); line-height: 0.92; letter-spacing: -0.085em; }
  .hero-copy p { max-width: 460px; margin: 5px 0 3px; color: var(--muted-strong); font-size: 14px; line-height: 1.5; }
  .hero-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; color: var(--muted); font-size: 10px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; }
  .pulse-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--success); box-shadow: 0 0 0 5px rgb(142 228 182 / 10%); animation: statusPulse 1.8s ease-in-out infinite; }
  .meta-divider { color: var(--brass-400); }
  .demo-banner { display: flex; align-items: flex-start; gap: 11px; padding: 13px 14px; border: 1px solid rgb(231 187 112 / 22%); border-radius: var(--radius-md); background: linear-gradient(100deg, rgb(231 187 112 / 10%), rgb(143 53 89 / 9%)); }
  .banner-icon { color: var(--brass-300); font-size: 18px; line-height: 1; }
  .demo-banner > span:last-child { display: grid; gap: 3px; }
  .demo-banner strong { color: var(--brass-300); font-size: 10px; letter-spacing: 0.12em; }
  .demo-banner small { color: var(--muted-strong); font-size: 11px; line-height: 1.35; }
  .rooms-section { display: grid; gap: 13px; }
  .section-heading { display: flex; align-items: end; justify-content: space-between; gap: 12px; }
  h2 { margin: 4px 0 0; color: var(--ivory); font-size: 25px; letter-spacing: -0.06em; }
  .room-count { color: var(--muted); font-size: 10px; font-weight: 800; letter-spacing: 0.1em; }
  .room-list { display: grid; gap: 10px; }
  .footer-note { display: flex; align-items: center; gap: 9px; padding: 3px 1px 4px; color: var(--muted); font-size: 10px; line-height: 1.4; }
  .footer-note strong { color: var(--muted-strong); }
  .footer-mark { color: var(--brass-400); }
  .footer-rule { flex: 1; height: 1px; background: linear-gradient(90deg, var(--line), transparent); }
  @keyframes markFloat { 0%, 100% { transform: translateY(0) rotate(0); } 50% { transform: translateY(-2px) rotate(8deg); } }
  @keyframes statusPulse { 0%, 100% { opacity: 0.55; transform: scale(0.9); } 50% { opacity: 1; transform: scale(1.12); } }
  @media (min-width: 620px) { .dashboard { gap: 34px; } .topbar { padding-top: 4px; } .hero-copy { padding-top: 28px; } .room-list { grid-template-columns: repeat(3, 1fr); } .room-list :global(.room-card) { min-height: 210px; grid-template-columns: 1fr; align-content: space-between; gap: 16px; } .room-list :global(.room-icon) { width: 48px; height: 48px; } .room-list :global(.room-arrow) { position: absolute; top: 18px; right: 18px; } .room-list :global(.room-card-copy > span:last-child) { white-space: normal; } }
</style>
