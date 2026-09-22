import { expect, test } from '@playwright/test';

test.describe('Slot v2 stop continuity', () => {
  test('runs travel and staged left-to-right landing phases', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('room-card-slot').click();
    await page.getByTestId('slot-spin').click();

    const machine = page.getByTestId('slot-machine');
    await expect(machine).toHaveAttribute('data-slot-phase', 'spinning');
    await expect(machine).toHaveAttribute('data-stopped-reels', '0');
    await expect(machine).toHaveAttribute('data-slot-phase', 'stopping-left', { timeout: 3_000 });
    await expect(machine).toHaveAttribute('data-stopped-reels', '1', { timeout: 1_000 });
    await expect(machine).toHaveAttribute('data-slot-phase', 'stopping-center', { timeout: 1_000 });
    await expect(machine).toHaveAttribute('data-stopped-reels', '2', { timeout: 1_000 });
    await expect(machine).toHaveAttribute('data-slot-phase', 'stopping-right', { timeout: 1_000 });
    await expect(machine).toHaveAttribute('data-stopped-reels', '3', { timeout: 1_000 });
    await expect(machine).toHaveAttribute('data-slot-phase', 'settled', { timeout: 1_000 });
    await expect(machine.locator('[data-reel-phase="landed"]')).toHaveCount(3);
    await expect(page.getByTestId('slot-confirmed-grid')).toBeVisible();
  });

  test('settles every reel immediately under reduced motion', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    await page.getByTestId('room-card-slot').click();
    await page.getByTestId('slot-spin').click();

    const machine = page.getByTestId('slot-machine');
    await expect(machine).toHaveAttribute('data-slot-phase', 'settled');
    await expect(machine).toHaveAttribute('data-stopped-reels', '3');
    await expect(machine.locator('[data-reel-phase="landed"]')).toHaveCount(3);
  });

  test('renders the live canonical grid and payout without a client-side substitute', async ({ page }) => {
    const roomId = '00000000-0000-0000-0000-000000000042';
    const serverResult = {
      grid: [
        ['A', 'A', 'A', 'B', 'B', 'C', 'C'],
        ['A', 'A', 'A', 'B', 'B', 'C', 'C'],
        ['A', 'A', 'A', 'B', 'B', 'C', 'C']
      ],
      reel_stops: [0, 0, 0],
      winning_lines: [
        {
          payline_index: 0,
          rows: [3, 3, 3],
          symbols: ['B', 'B', 'B'],
          match_symbol: 'B',
          matched_columns: 3,
          payout: 20
        }
      ],
      gross_payout: 20,
      net_delta: 10,
      balance_after: 1_010,
      ruleset_version: 'slot-skeleton-1'
    };

    await page.addInitScript(() => {
      (window as typeof window & { Telegram?: unknown }).Telegram = {
        WebApp: {
          initData: 'query_id=verified',
          ready: () => undefined,
          expand: () => undefined,
          setHeaderColor: () => undefined,
          setBackgroundColor: () => undefined
        }
      };
    });
    await page.route('**/api/v1/me', (route) => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ user_id: 12345, telegram_user_id: 12345, display_name: 'Test User' })
    }));
    await page.route('**/api/v1/wallet', (route) => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ user_id: 12345, balance: 1_000, currency_code: 'JOKERGEM', version: 1 })
    }));
    await page.route('**/api/v1/rooms', async (route) => {
      if (route.request().method() !== 'POST') return route.continue();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          room_id: roomId,
          game_type: 'slot',
          mode: 'solo',
          status: 'waiting',
          ruleset_version: 'slot-skeleton-1',
          state_version: 0,
          public_state: { phase: 'waiting', legal_actions: ['spin'], action_count: 0 }
        })
      });
    });
    await page.route(`**/api/v1/rooms/${roomId}/actions`, async (route) => {
      const request = route.request().postDataJSON() as { action_id: string };
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          event: {
            event_id: request.action_id,
            room_id: roomId,
            state_version: 1,
            type: 'slot.action.accepted',
            ruleset_version: 'slot-skeleton-1',
            server_time: '2026-09-22T00:00:00Z',
            payload: {
              action_id: request.action_id,
              public_state: { phase: 'active', last_result: serverResult },
              result: serverResult
            },
            animation_hint: 'slot.reels.stop.staggered'
          }
        })
      });
    });
    await page.route(`**/api/v1/rooms/${roomId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          room_id: roomId,
          game_type: 'slot',
          mode: 'solo',
          status: 'active',
          ruleset_version: 'slot-skeleton-1',
          state_version: 1,
          public_state: { phase: 'active', last_result: serverResult }
        })
      });
    });

    await page.goto('/');
    await page.getByTestId('room-card-slot').click();
    await expect(page.getByTestId('room-shell')).toBeVisible();
    await page.getByTestId('slot-spin').click();
    await expect(page.getByTestId('result-band')).toContainText('RESOLVING · SERVER RESULT');
    await expect(page.getByTestId('slot-machine')).toHaveAttribute('data-stopped-reels', '3', { timeout: 5_000 });
    await expect(page.getByTestId('result-band')).toContainText('SERVER CONFIRMED · LIVE');
    await expect(page.getByTestId('result-band')).toContainText('+20 JG');
    await expect(page.getByTestId('slot-confirmed-grid')).toBeVisible();

    await page.getByTestId('resync-button').click();
    await expect(page.getByTestId('room-shell')).toHaveAttribute('data-motion', 'settle');
    await expect(page.getByTestId('resync-button')).toHaveText('LIVE');
    await expect(page.getByTestId('result-band')).toContainText('SERVER CONFIRMED · LIVE');
    await expect(page.getByTestId('slot-confirmed-grid')).toBeVisible();
  });
});
