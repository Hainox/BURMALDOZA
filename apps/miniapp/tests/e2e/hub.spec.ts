import { expect, test } from '@playwright/test';
import { openRoom } from './helpers';

test('chooses a portal before entering and remembers selection and motion pause on return', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('room-card-blackjack').click();
  await expect(page.getByTestId('room-card-blackjack')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('room-shell')).toHaveCount(0);
  await page.getByTestId('hub-motion-toggle').click();
  await expect(page.getByTestId('dashboard')).toHaveAttribute('data-motion-paused', 'true');
  await page.getByTestId('hub-open-room').click();
  await expect(page.getByTestId('blackjack-deal')).toBeVisible();
  await page.getByRole('button', { name: 'Назад к комнатам' }).click();
  await expect(page.getByTestId('room-card-blackjack')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('dashboard')).toHaveAttribute('data-motion-paused', 'true');
});

test('keyboard navigation exposes real DEMO boundaries in all hub panels', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('hub-nav-ranking').press('Enter');
  await expect(page.getByTestId('leaderboard-demo')).toBeVisible();
  await expect(page.getByTestId('hub-open-room')).toBeHidden();
  await page.getByTestId('hub-nav-history').press('Enter');
  await expect(page.getByTestId('ledger-demo')).toBeVisible();
  await page.getByTestId('hub-nav-play').press('Enter');
  await page.getByTestId('hub-bonus-toggle').press('Enter');
  await expect(page.getByText('В демо бонусы не начисляются.')).toBeVisible();
  await expect(page.getByTestId('wallet-grants')).toHaveCount(0);
});

for (const width of [320, 390, 1440]) {
  test(`all artwork loads and the hub fits ${width}px with reduced motion`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 844 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    await expect(page.getByTestId('dashboard')).toHaveAttribute('data-motion-paused', 'true');
    await expect(page.getByTestId('hub-motion-toggle')).toBeDisabled();
    for (const img of await page.locator('[data-testid="dashboard"] img').all()) {
      await expect.poll(() => img.evaluate((node: HTMLImageElement) => node.complete && node.naturalWidth > 0)).toBe(true);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await page.locator('.backdrop img').evaluate(node => getComputedStyle(node).animationName)).toBe('none');
    if (width === 390) await page.screenshot({ path: testInfo.outputPath('hub-390.png') });
    await openRoom(page, 'holdem');
    await expect(page.getByTestId('holdem-start')).toBeVisible();
  });
}
