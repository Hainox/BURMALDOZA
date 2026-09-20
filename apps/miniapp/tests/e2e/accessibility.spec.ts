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
    await page.getByTestId('slot-spin').click();
    await expect(page.getByTestId('result-band')).toContainText('SERVER CONFIRMED · DEMO');
    await expect(page.getByTestId('result-band')).toContainText('Линия подтверждена');
  });
});
