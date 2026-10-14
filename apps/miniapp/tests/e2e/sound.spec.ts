import { expect, test } from '@playwright/test';
import { openRoom } from './helpers';

// Звук по умолчанию выключен; переключатель виден в хабе и комнате; без пакета (/audio/ — 404, как на Pages)
// страница работает без ошибок, выбор игрока запоминается.
test('sound toggle is muted by default, remembered, and safe without a sound pack', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  const hubToggle = page.getByTestId('sound-toggle');
  await expect(hubToggle).toHaveAttribute('aria-pressed', 'false');
  await hubToggle.click();
  await expect(hubToggle).toHaveAttribute('aria-pressed', 'true');
  await expect(hubToggle).toHaveAccessibleName('Выключить звук');

  await openRoom(page, 'blackjack');
  const roomToggle = page.getByTestId('room-shell').getByTestId('sound-toggle');
  await expect(roomToggle).toHaveAttribute('aria-pressed', 'true');
  await page.getByTestId('blackjack-deal').click();
  await expect(page.getByTestId('blackjack-room')).toHaveAttribute('data-game-phase', 'player_turn');

  await page.reload();
  await expect(page.getByTestId('sound-toggle')).toHaveAttribute('aria-pressed', 'true');
  await page.getByTestId('sound-toggle').click();
  await expect(page.getByTestId('sound-toggle')).toHaveAttribute('aria-pressed', 'false');
  expect(errors).toEqual([]);
});
