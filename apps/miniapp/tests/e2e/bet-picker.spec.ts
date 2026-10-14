import { expect, test } from '@playwright/test';
import { openRoom } from './helpers';

test('live slot sends the chosen bet from a preset or the slider', async ({ page }) => {
  const roomId = '00000000-0000-0000-0000-000000000077';
  const bets: unknown[] = [];
  const serverResult = {
    grid: [
      ['A', 'A', 'A', 'B', 'B', 'C', 'C'],
      ['A', 'A', 'A', 'B', 'B', 'C', 'C'],
      ['A', 'A', 'A', 'B', 'B', 'C', 'C']
    ],
    reel_stops: [0, 0, 0],
    winning_lines: [],
    gross_payout: 0,
    net_delta: -70,
    balance_after: 930,
    ruleset_version: 'slot-skeleton-1'
  };
  await page.addInitScript(() => {
    (window as typeof window & { Telegram?: unknown }).Telegram = {
      WebApp: { initData: 'query_id=verified', ready: () => undefined, expand: () => undefined, setHeaderColor: () => undefined, setBackgroundColor: () => undefined }
    };
  });
  await page.route('**/api/v1/me', (route) => route.fulfill({ json: { user_id: 1, telegram_user_id: 1, display_name: 'Bet' } }));
  await page.route('**/api/v1/wallet', (route) => route.fulfill({ json: { user_id: 1, balance: 1_000, currency_code: 'JOKERGEM', version: 1 } }));
  await page.route('**/api/v1/rooms', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    await route.fulfill({ json: { room_id: roomId, game_type: 'slot', mode: 'solo', status: 'waiting', ruleset_version: 'slot-skeleton-1', state_version: 0, public_state: { phase: 'waiting', legal_actions: ['spin'], action_count: 0 } } });
  });
  await page.route(`**/api/v1/rooms/${roomId}/actions`, async (route) => {
    const request = route.request().postDataJSON() as { action_id: string; payload: { bet?: unknown } };
    bets.push(request.payload.bet);
    await route.fulfill({ json: { event: { event_id: request.action_id, room_id: roomId, state_version: bets.length, type: 'slot.action.accepted', ruleset_version: 'slot-skeleton-1', server_time: '2026-10-14T00:00:00Z', payload: { action_id: request.action_id, public_state: { phase: 'active', last_result: serverResult }, result: serverResult }, animation_hint: 'slot.reels.stop.staggered' } } });
  });
  await page.route(`**/api/v1/rooms/${roomId}`, (route) => route.fulfill({ json: { room_id: roomId, game_type: 'slot', mode: 'solo', status: 'active', ruleset_version: 'slot-skeleton-1', state_version: bets.length, public_state: { phase: 'active', last_result: serverResult } } }));

  await page.goto('/');
  await openRoom(page, 'slot');
  await expect(page.getByTestId('slot-spin')).toContainText('Крутить за 10 JG');

  await page.getByRole('button', { name: '50', exact: true }).click();
  await expect(page.getByTestId('slot-spin')).toContainText('Крутить за 50 JG');
  await page.getByRole('slider').fill('70');
  await expect(page.getByTestId('slot-bet')).toHaveValue('70');
  await expect(page.getByTestId('slot-spin')).toContainText('Крутить за 70 JG');

  await page.getByTestId('slot-spin').click();
  await expect(page.getByTestId('slot-machine')).toHaveAttribute('data-stopped-reels', '3', { timeout: 5_000 });
  expect(bets).toEqual([70]);

  await page.getByTestId('slot-bet').fill('150');
  await expect(page.getByTestId('slot-spin')).toBeDisabled();
});

test('blackjack presets and slider set the deal amount', async ({ page }) => {
  await page.goto('/');
  await openRoom(page, 'blackjack');
  await page.getByRole('button', { name: '75', exact: true }).click();
  await expect(page.getByTestId('blackjack-deal')).toContainText('Раздать за 75 JG');
  await page.getByRole('slider').fill('33');
  await expect(page.getByTestId('blackjack-bet')).toHaveValue('33');
  await expect(page.getByTestId('blackjack-deal')).toContainText('Раздать за 33 JG');
});

test('demo slot payout follows the chosen bet', async ({ page }) => {
  await page.goto('/');
  await openRoom(page, 'slot');
  await page.getByRole('button', { name: '50', exact: true }).click();
  await page.getByTestId('slot-spin').click();
  await expect(page.getByTestId('result-band')).toContainText('200', { timeout: 8_000 });
});
