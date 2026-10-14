import { expect, test, type Page } from '@playwright/test';
import { openRoom } from './helpers';

const entry = (reason: string, amount_delta: number, balance_after: number) => ({
  id: reason, operation_id: reason, amount_delta, balance_after, reason,
  reference_type: 'game_round', reference_id: null, created_at: '2026-10-12T21:04:00Z'
});

async function live(page: Page) {
  await page.addInitScript(() => {
    (window as typeof window & { Telegram?: unknown }).Telegram = { WebApp: {
      initData: 'query_id=ledger-test', ready() {}, expand() {}, setHeaderColor() {}, setBackgroundColor() {}
    } };
  });
  await page.route('**/api/v1/wallet', route => route.fulfill({ json: {
    user_id: 1, balance: 1000, currency_code: 'JOKERGEM', version: 1
  } }));
}

test('DEMO shows no invented history and sends no ledger requests', async ({ page }) => {
  let requests = 0;
  await page.route('**/api/v1/wallet/ledger', route => { requests++; return route.fulfill({ json: [] }); });
  await page.goto('/');
  await page.getByTestId('hub-nav-history').click();
  await expect(page.getByTestId('ledger-demo')).toContainText('после входа через Telegram');
  await expect(page.getByTestId('ledger-entry')).toHaveCount(0);
  expect(requests).toBe(0);
});

for (const viewport of [{ width: 375, height: 812 }, { width: 1440, height: 900 }]) {
  test(`shows server entries and Moscow time at ${viewport.width}px with reduced motion`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await live(page);
    await page.route('**/api/v1/wallet/ledger', route => route.fulfill({ json: [
      entry('game_stake', -25, 912), entry('game_payout', 75, 987), entry('welcome', 1000, 1000)
    ] }));
    await page.goto('/');
  await page.getByTestId('hub-nav-history').click();
    const history = page.getByTestId('ledger-history');
    await expect(history).toContainText('13.10.2026, 00:04 МСК');
    await expect(history).toContainText('Ставка');
    await expect(history).toContainText('-25 JG');
    await expect(history).toContainText('Баланс после: 912 JG');
    await expect(history).toContainText('+75 JG');
    await expect(page.getByTestId('ledger-entry')).toHaveCount(3);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}

test('shows loading, error/retry, then the empty state', async ({ page }) => {
  await live(page);
  let release: () => void = () => {};
  const gate = new Promise<void>(resolve => { release = resolve; });
  let calls = 0;
  await page.route('**/api/v1/wallet/ledger', async route => {
    if (++calls === 1) { await gate; await route.fulfill({ status: 503, json: { detail: 'unavailable' } }); }
    else await route.fulfill({ json: [] });
  });
  await page.goto('/');
  await page.getByTestId('hub-nav-history').click();
  await expect(page.getByTestId('ledger-history')).toContainText('Загружаем историю');
  release();
  const retry = page.getByRole('button', { name: 'Повторить загрузку истории' });
  await expect(retry).toBeVisible();
  await retry.focus();
  await retry.press('Enter');
  await expect(page.getByTestId('ledger-empty')).toBeVisible();
});

test('rereads after a grant without fabricating history from the grant response', async ({ page }) => {
  await live(page);
  let entries = [entry('welcome', 1000, 1000)];
  let reads = 0;
  await page.route('**/api/v1/wallet/ledger', route => { reads++; return route.fulfill({ json: entries }); });
  await page.route('**/api/v1/wallet/daily-bonus/claim', route => {
    entries = [entry('daily_bonus', 250, 1250), ...entries];
    return route.fulfill({ json: { operation_id: 'grant', idempotency_key: 'grant', user_id: 1,
      delta: 250, balance_after: 1250, reason: 'daily_bonus' } });
  });
  await page.goto('/');
  await page.getByTestId('hub-nav-history').click();
  await expect(page.getByTestId('ledger-entry')).toHaveCount(1);
  await page.getByTestId('hub-nav-play').click();
  await page.getByTestId('hub-bonus-toggle').click();
  await page.getByTestId('wallet-daily-claim').click();
  await page.getByTestId('hub-nav-history').click();
  await expect(page.getByTestId('ledger-entry')).toHaveCount(2);
  await expect(page.getByTestId('ledger-history')).toContainText('Ежедневный бонус');
  expect(reads).toBe(2);
});

test('rereads after confirmed game actions even before a round has settled', async ({ page }) => {
  await live(page);
  const roomId = '00000000-0000-0000-0000-000000000051';
  const snapshot = { room_id: roomId, game_type: 'blackjack', mode: 'solo', status: 'waiting',
    ruleset_version: 'blackjack-gfl-skeleton-1', state_version: 0,
    public_state: { game_phase: 'waiting', legal_actions: ['deal'], wallet_balance: 1000 } };
  let entries = [entry('welcome', 1000, 1000)];
  await page.route('**/api/v1/wallet/ledger', route => route.fulfill({ json: entries }));
  await page.route('**/api/v1/rooms', route => route.fulfill({ json: snapshot }));
  await page.route(`**/api/v1/rooms/${roomId}/actions`, route => {
    entries = [entry('game_stake', -25, 975), ...entries];
    return route.fulfill({ json: { event: { event_id: 'stake', room_id: roomId, state_version: 1,
      type: 'blackjack.action.accepted', ruleset_version: snapshot.ruleset_version,
      server_time: '2026-10-12T21:04:00Z', animation_hint: '', payload: { public_state: {
        game_phase: 'player_turn', legal_actions: ['stand'], wallet_balance: 975,
        player_cards: [{ rank: '10', suit: 'spades' }, { rank: '7', suit: 'hearts' }],
        dealer_cards: [{ rank: '9', suit: 'clubs' }, { hidden: true }], dealer_hole_hidden: true,
        player_total: 17, bet: 25
      } } } } });
  });
  await page.goto('/');
  await page.getByTestId('hub-nav-history').click();
  await expect(page.getByTestId('ledger-entry')).toHaveCount(1);
  await page.getByTestId('hub-nav-play').click();
  await openRoom(page, 'blackjack');
  await page.getByTestId('blackjack-deal').click();
  await expect(page.getByTestId('ledger-entry')).toHaveCount(2);
  await expect(page.getByTestId('ledger-history')).toContainText('Баланс после: 975 JG');
});
