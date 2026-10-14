import { expect, test } from '@playwright/test';
import { openRoom } from './helpers';

for (const game of ['slot', 'blackjack'] as const) {
  test(`${game} custom bet respects the server ceiling even above a million`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.addInitScript(() => {
      (window as typeof window & { Telegram?: unknown }).Telegram = {
        WebApp: { initData: 'query_id=verified', ready: () => undefined, expand: () => undefined,
          setHeaderColor: () => undefined, setBackgroundColor: () => undefined }
      };
    });
    await page.route('**/api/v1/me', route => route.fulfill({ json: { user_id: 1, telegram_user_id: 1, display_name: 'Test' } }));
    await page.route('**/api/v1/wallet', route => route.fulfill({ json: { user_id: 1, balance: 2_171_000_000, currency_code: 'JOKERGEM', version: 1 } }));
    await page.route('**/api/v1/rooms', route => route.fulfill({ json: {
      room_id: '00000000-0000-0000-0000-000000000105', game_type: game, mode: 'solo',
      status: 'waiting', ruleset_version: game === 'slot' ? 'slot-siege-2' : 'blackjack-gfl-skeleton-1',
      state_version: 0, public_state: { phase: 'waiting', legal_actions: [game === 'slot' ? 'spin' : 'deal'] }
    } }));
    await page.goto('/');
    await openRoom(page, game);
    if (game === 'slot') await page.locator('.slot-bet summary').click();
    const input = page.getByTestId(`${game}-bet`);
    const action = page.getByTestId(game === 'slot' ? 'slot-spin' : 'blackjack-deal');
    await expect(input).toHaveAttribute('max', '1000000');
    await expect(page.getByRole('slider')).toHaveAttribute('max', '1000000');
    await input.fill('1000000');
    await expect(action).toBeEnabled();
    // Siege collapses the bet panel when its summary rerenders after an edit.
    if (game === 'slot' && !(await input.isVisible())) await page.locator('.slot-bet summary').click();
    await input.fill('1000001');
    await expect(action).toBeDisabled();
  });
}
