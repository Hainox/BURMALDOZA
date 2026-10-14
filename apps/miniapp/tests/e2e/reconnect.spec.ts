import { expect, test } from '@playwright/test';
import { openRoom } from './helpers';

test('resync returns to a stable room snapshot', async ({ page }) => {
  await page.goto('/');
  await openRoom(page, 'holdem');

  await expect(page.getByTestId('room-shell')).toBeVisible();
  await page.getByTestId('resync-button').click();
  await expect(page.getByTestId('resync-button')).toContainText('DEMO');
  await expect(page.getByTestId('room-shell')).toHaveAttribute('data-motion', 'idle');
  await expect(
    page.getByTestId('room-shell').getByRole('heading', { name: 'Камуро-тё', level: 2 })
  ).toBeVisible();
});
