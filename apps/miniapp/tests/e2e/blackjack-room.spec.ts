import { expect, test, type Page, type Route } from '@playwright/test';

const roomId = '00000000-0000-0000-0000-00000000b16c';
const approvedRuleset = 'blackjack-gfl-skeleton-1';

const dealPublicState = {
  game_phase: 'player_turn',
  bet: 25,
  player_cards: [
    { rank: 'A', suit: 'hearts' },
    { rank: 'K', suit: 'hearts' }
  ],
  dealer_cards: [{ rank: '10', suit: 'spades' }, { hidden: true }],
  dealer_hole_hidden: true,
  player_total: 21,
  legal_actions: ['hit', 'stand', 'double'],
  ruleset_version: approvedRuleset,
  wallet_balance: 975
};

const standPublicState = {
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

const standResult = {
  outcome: 'blackjack',
  player_total: 21,
  dealer_total: 16,
  gross_payout: 62,
  net_delta: 37,
  balance_after: 1037,
  ruleset_version: approvedRuleset,
  final_bet: 25
};

async function stubLiveBlackjack(page: Page, options: { dealOnce?: boolean } = {}) {
  let roomVersion = 0;
  let lastPublicState: Record<string, unknown> = {
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
  let lastResult: Record<string, unknown> | null = null;
  let actionCalls = 0;
  let failNext = options.dealOnce === true;

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
    roomVersion = 0;
    lastPublicState = {
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
    lastResult = null;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        room_id: roomId,
        game_type: 'blackjack',
        mode: 'solo',
        status: 'waiting',
        ruleset_version: approvedRuleset,
        state_version: roomVersion,
        public_state: lastPublicState
      })
    });
  });
  await page.route(`**/api/v1/rooms/${roomId}/actions`, async (route: Route) => {
    const request = route.request().postDataJSON() as { action_id: string; payload: Record<string, unknown> };
    actionCalls += 1;
    if (failNext) {
      failNext = false;
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'state version is stale; refresh and retry' })
      });
      return;
    }
    roomVersion += 1;
    if (request.payload.action === 'deal') {
      lastPublicState = { ...dealPublicState };
      lastResult = null;
    } else {
      lastPublicState = { ...standPublicState };
      lastResult = { ...standResult };
    }
    const payload: Record<string, unknown> = {
      action_id: request.action_id,
      public_state: lastPublicState
    };
    if (lastResult) payload.result = lastResult;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        event: {
          event_id: request.action_id,
          room_id: roomId,
          state_version: roomVersion,
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
    const payload: Record<string, unknown> = { public_state: lastPublicState };
    if (lastResult) {
      payload.public_state = { ...lastPublicState, last_result: lastResult };
      payload.result = lastResult;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        room_id: roomId,
        game_type: 'blackjack',
        mode: 'solo',
        status: 'active',
        ruleset_version: approvedRuleset,
        state_version: roomVersion,
        public_state: payload.public_state
      })
    });
  });

  return {
    actionCalls: () => actionCalls
  };
}

test.describe('Blackjack GFL room', () => {
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
    await expect(page.getByTestId('blackjack-player-total')).toContainText('total 21');
    await expect(page.getByTestId('blackjack-dealer-total')).toContainText('total скрыт');
    await expect(page.getByTestId('blackjack-hole-hidden')).toBeVisible();
    await expect(page.getByTestId('blackjack-hole-hidden')).toContainText('S09');
    await expect(page.getByTestId('blackjack-player-cards')).toContainText('RPK-16');
    await expect(page.getByTestId('blackjack-player-cards')).toContainText('AK-12');
    await expect(page.getByTestId('blackjack-hit')).toBeVisible();
    await expect(page.getByTestId('blackjack-stand')).toBeVisible();
    await expect(page.getByTestId('blackjack-double')).toBeVisible();
    await expect(page.getByTestId('blackjack-bet')).toHaveCount(0);
    await expect(page.getByTestId('blackjack-settlement')).toHaveCount(0);

    await page.getByTestId('blackjack-stand').click();
    await expect(page.getByTestId('blackjack-settlement')).toContainText('Натуральный блэкджек');
    await expect(page.getByTestId('blackjack-settlement')).toContainText('+62 JG');
    await expect(page.getByTestId('blackjack-settlement')).toContainText('BALANCE 1037 JG');
    await expect(page.getByTestId('blackjack-dealer-total')).toContainText('total 16');
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

  test('blocks a second tap while an action is pending', async ({ page }) => {
    const counters = await stubLiveBlackjack(page);
    await page.goto('/');
    await page.getByTestId('room-card-blackjack').click();

    const deal = page.getByTestId('blackjack-deal');
    await page.getByTestId('blackjack-bet').fill('25');
    await Promise.all([deal.click(), page.getByTestId('blackjack-bet').waitFor({ state: 'detached' })]);
    await expect(page.getByTestId('blackjack-room')).toHaveAttribute('data-game-phase', 'player_turn');

    const stand = page.getByTestId('blackjack-stand');
    await Promise.all([stand.click(), page.getByTestId('blackjack-settlement').waitFor({ state: 'visible' })]);
    await expect(page.getByTestId('blackjack-settlement')).toBeVisible();
    expect(counters.actionCalls()).toBe(2);
  });

  test('keeps an error visible and lets a retry confirm the next snapshot', async ({ page }) => {
    await stubLiveBlackjack(page, { dealOnce: true });
    await page.goto('/');
    await page.getByTestId('room-card-blackjack').click();

    await page.getByTestId('blackjack-bet').fill('25');
    await page.getByTestId('blackjack-deal').click();
    await expect(page.getByTestId('blackjack-error')).toContainText('Сервер не подтвердил действие');

    await page.getByTestId('blackjack-deal').click();
    await expect(page.getByTestId('blackjack-room')).toHaveAttribute('data-game-phase', 'player_turn');
    await expect(page.getByTestId('blackjack-error')).toHaveCount(0);
  });

  test('restores the confirmed server snapshot after reconnect without client math', async ({ page }) => {
    await stubLiveBlackjack(page);
    await page.goto('/');
    await page.getByTestId('room-card-blackjack').click();

    await page.getByTestId('blackjack-bet').fill('25');
    await page.getByTestId('blackjack-deal').click();
    await page.getByTestId('blackjack-stand').click();
    await expect(page.getByTestId('blackjack-settlement')).toContainText('BALANCE 1037 JG');

    await page.getByTestId('resync-button').click();
    await expect(page.getByTestId('room-shell')).toHaveAttribute('data-motion', 'settle');
    await expect(page.getByTestId('blackjack-room')).toHaveAttribute('data-game-phase', 'settled');
    await expect(page.getByTestId('blackjack-settlement')).toContainText('BALANCE 1037 JG');
    await expect(page.getByTestId('result-band')).toContainText('SERVER CONFIRMED · LIVE');
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
    await expect(page.getByTestId('blackjack-dealer-total')).toContainText('total 16');
  });
});
