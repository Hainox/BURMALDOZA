import { expect, test } from '@playwright/test';

test.describe('Mini App shell', () => {
  test('exposes the three rooms and a clear demo boundary', async ({ page }) => {
    await page.goto('/');

    await expect(page.getByRole('heading', { name: 'Игровой лаунж' })).toBeVisible();
    await expect(page.getByTestId('demo-banner')).toContainText('ДЕМО-КОНТУР');
    await expect(page.locator('[data-testid^="room-card-"]')).toHaveCount(3);
    await expect(page.getByTestId('balance-pill')).toHaveAccessibleName(/Баланс/);
  });

  test('runs a slot action through server-confirmed result state', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    await page.getByTestId('room-card-slot').click();

    await expect(page.getByTestId('room-shell')).toBeVisible();
    await expect(page.getByTestId('slot-reel-track-0')).toHaveAttribute('data-track-length', '28');
    await page.getByTestId('slot-spin').click();
    await expect(page.getByTestId('result-band')).toContainText('SERVER CONFIRMED · DEMO');
    await expect(page.getByTestId('result-band')).toContainText('Линия подтверждена');
    await expect(page.getByTestId('slot-free-spins')).toContainText('5');
  });

  test('plays a full reel cycle before revealing the confirmed grid', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('room-card-slot').click();
    await page.getByTestId('slot-spin').click();

    await expect(page.getByTestId('slot-machine')).toHaveAttribute('data-reel-phase', 'outcome', { timeout: 3000 });
    await expect(page.getByTestId('slot-confirmed-grid')).toBeVisible();
    await expect(page.getByTestId('slot-payline')).toBeVisible();
  });
});
