import { expect, test } from '@playwright/test';

test('resync returns to a stable room snapshot', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('room-card-holdem').click();

  await expect(page.getByTestId('room-shell')).toBeVisible();
  await page.getByTestId('resync-button').click();
  await expect(page.getByTestId('resync-button')).toHaveText('DEMO');
  await expect(page.getByTestId('room-shell')).toHaveAttribute('data-motion', 'idle');
  await expect(
    page.getByTestId('room-shell').getByRole('heading', { name: 'Hold’em', level: 2 })
  ).toBeVisible();
});
