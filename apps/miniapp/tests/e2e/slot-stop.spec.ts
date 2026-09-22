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
});
