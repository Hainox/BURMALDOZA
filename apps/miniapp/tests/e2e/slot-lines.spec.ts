import { expect, test } from '@playwright/test';
import { openRoom } from './helpers';

// slot-siege-2 (#91): 9 линий — подпись комнаты и лучи для верхнего ряда и диагонали.
test('slot-siege-2 room shows nine lines and beams for any row or diagonal', async ({ page }) => {
  const roomId = '00000000-0000-0000-0000-000000000091';
  const grid = [
    ['A3', 'D1', 'A1', 'D2', 'D3', 'D1', 'D2'],
    ['A3', 'D2', 'D3', 'A1', 'D1', 'D3', 'D1'],
    ['A3', 'D3', 'D2', 'D1', 'A1', 'D2', 'D3']
  ];
  const result = {
    grid,
    reel_stops: [0, 0, 0],
    winning_lines: [
      { payline_index: 0, rows: [0, 0, 0], symbols: ['A3', 'A3', 'A3'], match_symbol: 'A3', matched_columns: 3, payout: 200 },
      { payline_index: 7, rows: [2, 3, 4], symbols: ['A1', 'A1', 'A1'], match_symbol: 'A1', matched_columns: 3, payout: 80 }
    ],
    gross_payout: 280,
    net_delta: 270,
    balance_after: 1_270,
    ruleset_version: 'slot-siege-2',
    operation_id: 'op1',
    next_operation_id: 'op2',
    operation_changes_at: '2026-10-19T00:00:00+03:00'
  };
  const meta = { operation_id: 'op1', next_operation_id: 'op2', operation_changes_at: '2026-10-19T00:00:00+03:00' };
  await page.addInitScript(() => {
    (window as typeof window & { Telegram?: unknown }).Telegram = {
      WebApp: { initData: 'query_id=verified', ready: () => undefined, expand: () => undefined, setHeaderColor: () => undefined, setBackgroundColor: () => undefined }
    };
  });
  await page.route('**/api/v1/me', (route) => route.fulfill({ json: { user_id: 1, telegram_user_id: 1, display_name: 'Lines' } }));
  await page.route('**/api/v1/wallet', (route) => route.fulfill({ json: { user_id: 1, balance: 1_000, currency_code: 'JOKERGEM', version: 1 } }));
  await page.route('**/api/v1/rooms', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    await route.fulfill({ json: { room_id: roomId, game_type: 'slot', mode: 'solo', status: 'waiting', ruleset_version: 'slot-siege-2', state_version: 0, public_state: { phase: 'waiting', legal_actions: ['spin'], action_count: 0, ...meta } } });
  });
  await page.route(`**/api/v1/rooms/${roomId}/actions`, async (route) => {
    const request = route.request().postDataJSON() as { action_id: string };
    await route.fulfill({ json: { event: { event_id: request.action_id, room_id: roomId, state_version: 1, type: 'slot.action.accepted', ruleset_version: 'slot-siege-2', server_time: '2026-10-14T00:00:00Z', payload: { action_id: request.action_id, public_state: { phase: 'active', ...meta, last_result: result }, result }, animation_hint: 'slot.reels.stop.staggered' } } });
  });
  await page.route(`**/api/v1/rooms/${roomId}`, (route) => route.fulfill({ json: { room_id: roomId, game_type: 'slot', mode: 'solo', status: 'active', ruleset_version: 'slot-siege-2', state_version: 1, public_state: { phase: 'active', ...meta, last_result: result } } }));

  await page.goto('/');
  await openRoom(page, 'slot');
  await expect(page.getByTestId('slot-lines')).toContainText('9 active');
  await page.getByTestId('slot-spin').click();
  await expect(page.getByTestId('slot-machine')).toHaveAttribute('data-slot-phase', 'settled', { timeout: 8_000 });
  await expect(page.getByTestId('slot-winning-beams').locator('polyline')).toHaveCount(2);
  await expect(page.getByTestId('slot-confirmed-grid')).toContainText('2 PAYLINES');
  // Пока родитель доигрывает итог, кнопка недоступна, а потом снова активна.
  await expect(page.getByTestId('slot-spin')).toBeEnabled({ timeout: 8_000 });
});
