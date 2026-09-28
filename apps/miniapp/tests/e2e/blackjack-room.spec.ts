import { expect, test, type Page, type Route } from '@playwright/test';

const roomId = '00000000-0000-0000-0000-00000000b16c';
const approvedRuleset = 'blackjack-gfl-skeleton-1';

const waitingPublicState = {
  game_phase: 'waiting',
  bet: 0,
  player_cards: [],
  dealer_cards: [],
  dealer_hole_hidden: false,
  player_total: 0,
  legal_actions: ['deal'],
  ruleset_version: approvedRuleset,
  wallet_balance: 1000
};

const dealPublicState = {
  game_phase: 'player_turn',
  bet: 25,
  player_cards: [
    { rank: '10', suit: 'spades' },
    { rank: '7', suit: 'hearts' }
  ],
  dealer_cards: [{ rank: '9', suit: 'clubs' }, { hidden: true }],
  dealer_hole_hidden: true,
  player_total: 17,
  legal_actions: ['hit', 'stand', 'double'],
  ruleset_version: approvedRuleset,
  wallet_balance: 975
};

const settledPublicState = {
  game_phase: 'settled',
  bet: 25,
  player_cards: [
    { rank: '10', suit: 'spades' },
    { rank: '7', suit: 'hearts' }
  ],
  dealer_cards: [
    { rank: '9', suit: 'clubs' },
    { rank: '10', suit: 'diamonds' }
  ],
  dealer_hole_hidden: false,
  player_total: 17,
  dealer_total: 19,
  legal_actions: ['deal'],
  ruleset_version: approvedRuleset,
  wallet_balance: 975
};

const settledResult = {
  outcome: 'loss',
  player_total: 17,
  dealer_total: 19,
  gross_payout: 0,
  net_delta: -25,
  balance_after: 975,
  ruleset_version: approvedRuleset,
  final_bet: 25
};

/** A natural blackjack is resolved by the server inside the `deal` response. */
const naturalPublicState = {
  game_phase: 'settled',
  bet: 25,
  player_cards: [
    { rank: 'A', suit: 'hearts' },
    { rank: 'K', suit: 'hearts' }
  ],
  dealer_cards: [
    { rank: '10', suit: 'spades' },
    { rank: '6', suit: 'clubs' }
  ],
  dealer_hole_hidden: false,
  player_total: 21,
  dealer_total: 16,
  legal_actions: ['deal'],
  ruleset_version: approvedRuleset,
  wallet_balance: 1037
};

const naturalResult = {
  outcome: 'blackjack',
  player_total: 21,
  dealer_total: 16,
  gross_payout: 62,
  net_delta: 37,
  balance_after: 1037,
  ruleset_version: approvedRuleset,
  final_bet: 25
};

interface StubOptions {
  /** `natural` resolves the round inside the deal response, `normal` opens a player turn. */
  hand?: 'natural' | 'normal';
  /** Another writer bumps the room before the first action, so it must be rejected with 409. */
  externalWrite?: boolean;
  /** Keeps the action pending long enough for the test to tap a second time. */
  actionDelayMs?: number;
}

async function stubLiveBlackjack(page: Page, options: StubOptions = {}) {
  const hand = options.hand ?? 'normal';
  let version = 0;
  let publicState: Record<string, unknown> = { ...waitingPublicState };
  let result: Record<string, unknown> | null = null;
  let actionCalls = 0;
  let externalWritePending = options.externalWrite === true;
  const requestedVersions: number[] = [];

  await page.addInitScript(() => {
    (window as typeof window & { Telegram?: unknown }).Telegram = {
      WebApp: {
        initData: 'query_id=verified-blackjack',
        ready: () => undefined,
        expand: () => undefined,
        setHeaderColor: () => undefined,
        setBackgroundColor: () => undefined
      }
    };
  });
  await page.route('**/api/v1/me', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ user_id: 777, telegram_user_id: 777, display_name: 'Blackjack Tester' })
    })
  );
  await page.route('**/api/v1/wallet', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ user_id: 777, balance: 1000, currency_code: 'JOKERGEM', version: 1 })
    })
  );
  await page.route('**/api/v1/rooms', async (route: Route) => {
    if (route.request().method() !== 'POST') return route.continue();
    version = 0;
    publicState = { ...waitingPublicState };
    result = null;
    externalWritePending = options.externalWrite === true;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        room_id: roomId,
        game_type: 'blackjack',
        mode: 'solo',
        status: 'waiting',
        ruleset_version: approvedRuleset,
        state_version: version,
        public_state: publicState
      })
    });
  });
  await page.route(`**/api/v1/rooms/${roomId}/actions`, async (route: Route) => {
    const request = route.request().postDataJSON() as {
      action_id: string;
      expected_state_version: number;
      payload: Record<string, unknown>;
    };
    actionCalls += 1;
    requestedVersions.push(request.expected_state_version);
    if (options.actionDelayMs) {
      await new Promise((resolve) => setTimeout(resolve, options.actionDelayMs));
    }

    if (externalWritePending) {
      externalWritePending = false;
      version += 1;
      publicState = { ...waitingPublicState, wallet_balance: 990 };
      result = null;
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'state version is stale; refresh and retry' })
      });
      return;
    }

    if (request.expected_state_version !== version) {
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'state version is stale; refresh and retry' })
      });
      return;
    }

    version += 1;
    if (request.payload.action === 'deal' && hand === 'natural') {
      publicState = { ...naturalPublicState };
      result = { ...naturalResult };
    } else if (request.payload.action === 'deal') {
      publicState = { ...dealPublicState };
      result = null;
    } else {
      publicState = { ...settledPublicState };
      result = { ...settledResult };
    }

    const payload: Record<string, unknown> = {
      action_id: request.action_id,
      public_state: publicState
    };
    if (result) payload.result = result;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        event: {
          event_id: request.action_id,
          room_id: roomId,
          state_version: version,
          type: 'blackjack.action.accepted',
          ruleset_version: approvedRuleset,
          server_time: '2026-09-24T00:00:00Z',
          payload,
          animation_hint: 'blackjack.cards.deal.staged'
        }
      })
    });
  });
  await page.route(`**/api/v1/rooms/${roomId}`, async (route: Route) => {
    const snapshotState: Record<string, unknown> = result
      ? { ...publicState, last_result: result }
      : publicState;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        room_id: roomId,
        game_type: 'blackjack',
        mode: 'solo',
        status: 'active',
        ruleset_version: approvedRuleset,
        state_version: version,
        public_state: snapshotState
      })
    });
  });

  return {
    actionCalls: () => actionCalls,
    requestedVersions: () => [...requestedVersions]
  };
}

test.describe('Blackjack GFL room', () => {
  test('resolves a natural blackjack inside the deal response', async ({ page }) => {
    const counters = await stubLiveBlackjack(page, { hand: 'natural' });
    await page.goto('/');
    await page.getByTestId('room-card-blackjack').click();
    await expect(page.getByTestId('blackjack-room')).toBeVisible();

    await page.getByTestId('blackjack-room').evaluate((element) => {
      type RoomWithPhaseLog = HTMLElement & { __phaseLog?: string[]; __phaseObserver?: MutationObserver };
      const target = element as RoomWithPhaseLog;
      const log: string[] = [target.getAttribute('data-game-phase') ?? ''];
      const observer = new MutationObserver(() => {
        const phase = target.getAttribute('data-game-phase') ?? '';
        if (log.at(-1) !== phase) log.push(phase);
      });
      observer.observe(target, { attributes: true, attributeFilter: ['data-game-phase'] });
      target.__phaseObserver = observer;
      target.__phaseLog = log;
    });

    await page.getByTestId('blackjack-deal').click();

    // The server settles A+K immediately: no player-turn phase may ever be rendered.
    await expect(page.getByTestId('blackjack-settlement')).toContainText('Натуральный блэкджек');
    await expect(page.getByTestId('blackjack-settlement')).toContainText('+62 JG');
    await expect(page.getByTestId('blackjack-settlement')).toContainText('BALANCE 1037 JG');
    await expect(page.getByTestId('blackjack-room')).toHaveAttribute('data-game-phase', 'settled');
    await expect(page.getByTestId('blackjack-dealer-total')).toContainText('total 16');
    await expect(page.getByTestId('blackjack-hole-hidden')).toHaveCount(0);
    await expect(page.getByTestId('blackjack-actions')).toHaveCount(0);
    await expect(page.getByTestId('blackjack-player-cards')).toContainText('RPK-16');
    await expect(page.getByTestId('blackjack-player-cards')).toContainText('AK-12');

    const phases = await page.getByTestId('blackjack-room').evaluate((element) => {
      type RoomWithPhaseLog = HTMLElement & { __phaseLog?: string[]; __phaseObserver?: MutationObserver };
      const target = element as RoomWithPhaseLog;
      target.__phaseObserver?.disconnect();
      return target.__phaseLog ?? [];
    });
    expect(phases).not.toContain('player_turn');
    expect(phases).toContain('settled');
    expect(counters.actionCalls()).toBe(1);
  });

  test('renders the server deal, hides the hole card, and settles from the server', async ({ page }) => {
    await stubLiveBlackjack(page);
    await page.goto('/');
    await page.getByTestId('room-card-blackjack').click();
    await expect(page.getByTestId('blackjack-room')).toBeVisible();

    await expect(page.getByTestId('blackjack-deal')).toBeEnabled();
    await expect(page.getByTestId('blackjack-actions')).toHaveCount(0);
    await page.getByTestId('blackjack-bet').fill('25');
    await page.getByTestId('blackjack-deal').click();

    await expect(page.getByTestId('blackjack-room')).toHaveAttribute('data-game-phase', 'player_turn');
    await expect(page.getByTestId('blackjack-player-total')).toContainText('total 17');
    await expect(page.getByTestId('blackjack-dealer-total')).toContainText('total скрыт');
    await expect(page.getByTestId('blackjack-hole-hidden')).toBeVisible();
    await expect(page.getByTestId('blackjack-hole-hidden')).toContainText('S09');
    await expect(
      page.getByTestId('blackjack-player-cards').locator('[data-card="10-spades"]')
    ).toBeVisible();
    await expect(
      page.getByTestId('blackjack-player-cards').locator('[data-card="7-hearts"]')
    ).toBeVisible();
    await expect(page.getByTestId('blackjack-hit')).toBeVisible();
    await expect(page.getByTestId('blackjack-stand')).toBeVisible();
    await expect(page.getByTestId('blackjack-double')).toBeVisible();
    await expect(page.getByTestId('blackjack-bet')).toHaveCount(0);
    await expect(page.getByTestId('blackjack-settlement')).toHaveCount(0);

    await page.getByTestId('blackjack-stand').click();
    await expect(page.getByTestId('blackjack-settlement')).toContainText('Поражение');
    await expect(page.getByTestId('blackjack-settlement')).toContainText('17 против 19');
    await expect(page.getByTestId('blackjack-settlement')).toContainText('BALANCE 975 JG');
    await expect(page.getByTestId('blackjack-dealer-total')).toContainText('total 19');
    await expect(page.getByTestId('result-band')).toContainText('SERVER CONFIRMED · LIVE');
    await expect(page.getByTestId('blackjack-room')).toHaveAttribute('data-game-phase', 'settled');
  });

  test('accepts only integer bets between 25 and 100', async ({ page }) => {
    await stubLiveBlackjack(page);
    await page.goto('/');
    await page.getByTestId('room-card-blackjack').click();

    await page.getByTestId('blackjack-bet').fill('10');
    await expect(page.getByTestId('blackjack-deal')).toBeDisabled();
    await expect(page.getByText('Ставка — целое число от 25 до 100.')).toBeVisible();

    await page.getByTestId('blackjack-bet').fill('101');
    await expect(page.getByTestId('blackjack-deal')).toBeDisabled();

    await page.getByTestId('blackjack-bet').fill('50');
    await expect(page.getByTestId('blackjack-deal')).toContainText('Раздать за 50 JG');
  });

  test('answers a repeated tap with exactly one action request', async ({ page }) => {
    const counters = await stubLiveBlackjack(page, { actionDelayMs: 250 });
    await page.goto('/');
    await page.getByTestId('room-card-blackjack').click();
    await page.getByTestId('blackjack-bet').fill('25');

    const deal = page.getByTestId('blackjack-deal');
    await deal.click();
    await expect(deal).toBeDisabled();
    await expect(deal).toContainText('Ожидаем сервер');
    await deal.click({ force: true });
    expect(counters.actionCalls()).toBe(1);

    await expect(page.getByTestId('blackjack-room')).toHaveAttribute('data-game-phase', 'player_turn');
    const stand = page.getByTestId('blackjack-stand');
    await stand.click();
    await expect(stand).toBeDisabled();
    await stand.click({ force: true });
    await expect(page.getByTestId('blackjack-settlement')).toBeVisible();
    expect(counters.actionCalls()).toBe(2);
    expect(counters.requestedVersions()).toEqual([0, 1]);
  });

  test('re-reads a stale room after 409 so the retry uses the new state version', async ({ page }) => {
    const counters = await stubLiveBlackjack(page, { externalWrite: true });
    await page.goto('/');
    await page.getByTestId('room-card-blackjack').click();
    await page.getByTestId('blackjack-bet').fill('25');

    await page.getByTestId('blackjack-deal').click();
    await expect(page.getByTestId('blackjack-error')).toContainText('Сервер не подтвердил действие');
    // The client must show the version the server actually holds, not the rejected one.
    await expect(page.getByTestId('blackjack-wallet')).toContainText('990 JG');

    await page.getByTestId('blackjack-deal').click();
    await expect(page.getByTestId('blackjack-room')).toHaveAttribute('data-game-phase', 'player_turn');
    await expect(page.getByTestId('blackjack-error')).toHaveCount(0);
    expect(counters.requestedVersions()).toEqual([0, 1]);
  });

  test('restores the confirmed server snapshot after reconnect without client math', async ({ page }) => {
    await stubLiveBlackjack(page);
    await page.goto('/');
    await page.getByTestId('room-card-blackjack').click();

    await page.getByTestId('blackjack-bet').fill('25');
    await page.getByTestId('blackjack-deal').click();
    await page.getByTestId('blackjack-stand').click();
    await expect(page.getByTestId('blackjack-settlement')).toContainText('BALANCE 975 JG');

    await page.getByTestId('resync-button').click();
    await expect(page.getByTestId('room-shell')).toHaveAttribute('data-motion', 'settle');
    await expect(page.getByTestId('blackjack-room')).toHaveAttribute('data-game-phase', 'settled');
    await expect(page.getByTestId('blackjack-settlement')).toContainText('BALANCE 975 JG');
    await expect(page.getByTestId('result-band')).toContainText('SERVER CONFIRMED · LIVE');
  });

  test('plays a marked demo hand and never presents it as a server result', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('room-card-blackjack').click();
    await expect(page.getByTestId('blackjack-demo-note')).toContainText('ДЕМО');

    await page.getByTestId('blackjack-deal').click();
    await expect(page.getByTestId('blackjack-room')).toHaveAttribute('data-game-phase', 'player_turn');
    await expect(page.getByTestId('blackjack-player-total')).toContainText('total 17');
    await expect(page.getByTestId('blackjack-dealer-total')).toContainText('total скрыт');
    await expect(page.getByTestId('blackjack-hole-hidden')).toBeVisible();
    await expect(page.getByTestId('blackjack-hit')).toBeVisible();
    await expect(page.getByTestId('blackjack-stand')).toBeVisible();
    await expect(page.getByTestId('blackjack-double')).toBeVisible();

    await page.getByTestId('blackjack-stand').click();
    await expect(page.getByTestId('blackjack-settlement')).toContainText('DEMO ROUND');
    await expect(page.getByTestId('blackjack-settlement')).not.toContainText('SERVER SETTLEMENT');
    await expect(page.getByTestId('result-band')).toContainText('RESOLVING · DEMO RESULT');
    await expect(page.getByTestId('result-band')).toContainText('DEMO ROUND · БЕЗ СЕРВЕРНОГО ПОДТВЕРЖДЕНИЯ');
    await expect(page.getByTestId('result-band')).not.toContainText('SERVER CONFIRMED');
    await expect(page.getByTestId('result-band')).toContainText('демо-раунд, сервер не подтверждал');
    await expect(page.getByTestId('blackjack-dealer-total')).toContainText('total 12');
    await expect(page.getByTestId('blackjack-deal')).toBeVisible();
  });

  test('reveals dealer and player rows immediately under reduced motion', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await stubLiveBlackjack(page);
    await page.goto('/');
    await page.getByTestId('room-card-blackjack').click();

    await page.getByTestId('blackjack-bet').fill('25');
    await page.getByTestId('blackjack-deal').click();
    await expect(page.getByTestId('blackjack-room')).toHaveAttribute('data-game-phase', 'player_turn');
    await expect(page.getByTestId('blackjack-player-cards')).toBeVisible();

    await page.getByTestId('blackjack-stand').click();
    await expect(page.getByTestId('blackjack-settlement')).toBeVisible();
    await expect(page.getByTestId('blackjack-dealer-total')).toContainText('total 19');
  });
});
