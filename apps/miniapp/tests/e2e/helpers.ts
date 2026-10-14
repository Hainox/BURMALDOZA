import { expect, type Page } from '@playwright/test';

/**
 * Opens a room from the dashboard. Under parallel load a click can land before
 * SvelteKit hydration attaches the handler and is silently lost; retry the click
 * until the room shell is actually shown instead of failing on a 30 s timeout.
 */
export async function openRoom(page: Page, game: 'slot' | 'blackjack' | 'holdem') {
  const shell = page.getByTestId('room-shell');
  await expect(async () => {
    if (!(await shell.isVisible())) {
      await page.getByTestId(`room-card-${game}`).click();
      await page.getByTestId('hub-open-room').click();
    }
    await expect(shell).toBeVisible({ timeout: 1_500 });
  }).toPass({ timeout: 15_000 });
}
