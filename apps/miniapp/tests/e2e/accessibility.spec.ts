import { expect, test } from '@playwright/test';

test.describe('Mini App shell', () => {
  test('exposes the three rooms and a clear demo boundary', async ({ page }) => {
    await page.goto('/');

    await expect(page.getByRole('heading', { name: 'Игровой лаунж' })).toBeVisible();
    await expect(page.getByTestId('demo-banner')).toContainText('ДЕМО-КОНТУР');
    await expect(page.locator('[data-testid^="room-card-"]')).toHaveCount(3);
    await expect(page.getByTestId('balance-pill')).toHaveAccessibleName(/Баланс/);
  });

  test('shows a completed slot demo result without server claims', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    await page.getByTestId('room-card-slot').click();

    await expect(page.getByTestId('room-shell')).toBeVisible();
    const slotRoom = page.locator('.slot-room');
    await expect(slotRoom).toContainText('Демо-прокрутка барабанов. Клиент показывает сетку и движение; сервер не подтверждает исход.');
    await expect(slotRoom).not.toContainText('Сервер подтверждает сетку');
    await expect(page.getByTestId('slot-status')).toContainText('READY · DEMO');
    await expect(page.getByTestId('slot-reel-track-0')).toHaveAttribute('data-track-length', '28');
    await expect(page.getByTestId('slot-machine')).toHaveAttribute('data-spin-duration', '2940');
    await page.getByTestId('slot-spin').click();
    const resultBand = page.getByTestId('result-band');
    await expect(resultBand).toContainText('DEMO ROUND · БЕЗ СЕРВЕРНОГО ПОДТВЕРЖДЕНИЯ');
    await expect(resultBand).not.toContainText('SERVER CONFIRMED');
    await expect(resultBand).toContainText('Линия подтверждена');
    await expect(resultBand).toContainText('Демо-исход: сервер не подтверждал этот результат.');
    await expect(page.getByTestId('confirmed-balance')).toHaveCount(0);
    await expect(page.getByTestId('slot-confirmed-grid')).toContainText('DEMO GRID · CLIENT RESULT');
    await expect(page.getByTestId('slot-confirmed-grid')).not.toContainText('SERVER GRID CONFIRMED');
    await expect(page.getByTestId('slot-free-spins')).toContainText('DEMO BONUS STATE · CLIENT RESULT');
    await expect(page.getByTestId('slot-free-spins')).not.toContainText('SERVER CONFIRMED');
    await expect(page.getByTestId('slot-status')).toContainText('SETTLED · DEMO GRID');
    await expect(page.getByTestId('slot-free-spins')).toContainText('5');
  });

  test('labels an in-progress slot demo result as demo', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('room-card-slot').click();
    await page.getByTestId('slot-spin').click();

    const resultBand = page.getByTestId('result-band');
    await expect(resultBand).toContainText('RESOLVING · DEMO RESULT', { timeout: 2_000 });
    await expect(resultBand).not.toContainText('SERVER');
    await expect(resultBand).toContainText('Демо-исход появится после завершения движения.');
  });

  test('labels a Hold’em demo outcome as unconfirmed', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('room-card-holdem').click();
    const pokerRoom = page.locator('.poker-room');
    await expect(pokerRoom).toContainText('Демо-действия выполняются на клиенте; серверного подтверждения нет.');
    await expect(pokerRoom).not.toContainText('только подтверждённые действия');
    await page.getByRole('button', { name: 'CHECK' }).click();

    const resultBand = page.getByTestId('result-band');
    await expect(resultBand).toContainText('RESOLVING · DEMO RESULT', { timeout: 2_000 });
    await expect(resultBand).toContainText('DEMO ROUND · БЕЗ СЕРВЕРНОГО ПОДТВЕРЖДЕНИЯ', { timeout: 2_000 });
    await expect(resultBand).not.toContainText('SERVER CONFIRMED');
    await expect(resultBand).toContainText('Демо-исход: сервер не подтверждал этот результат.');
    await expect(page.getByTestId('confirmed-balance')).toHaveCount(0);
  });

  test('demo Slot description does not claim the result came from a server', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    await page.getByTestId('room-card-slot').click();
    await page.getByTestId('slot-spin').click();

    const resultBand = page.getByTestId('result-band');
    await expect(resultBand).toContainText('Линия подтверждена');
    await expect(resultBand).not.toContainText('Исход пришёл с сервера');
  });

  test('Hold’em demo description does not imply a server-confirmed action', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    await page.getByTestId('room-card-holdem').click();
    await page.getByRole('button', { name: 'CHECK' }).click();

    const resultBand = page.getByTestId('result-band');
    await expect(resultBand).toContainText('Рука подтверждена');
    await expect(resultBand).not.toContainText('подтверждённого действия');
  });

  test('plays a full reel cycle before revealing the confirmed grid', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('room-card-slot').click();
    await page.getByTestId('slot-spin').click();

    await expect(page.getByTestId('slot-machine')).toHaveAttribute('data-reel-phase', 'spinning');
    await expect(page.getByTestId('slot-reel-0')).toHaveAttribute('data-launch-delay', '0');
    await expect(page.getByTestId('slot-reel-1')).toHaveAttribute('data-launch-delay', '110');
    await expect(page.getByTestId('slot-reel-2')).toHaveAttribute('data-launch-delay', '220');
    await expect(page.getByTestId('slot-machine')).toHaveAttribute('data-reel-phase', 'outcome', { timeout: 5000 });
    await expect(page.getByTestId('slot-confirmed-grid')).toBeVisible();
    await expect(page.getByTestId('slot-payline')).toBeVisible();
  });

  test('keeps the reel transform moving during the travel phase', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('room-card-slot').click();
    await page.getByTestId('slot-spin').click();

    const track = page.getByTestId('slot-reel-track-0');
    await expect(page.getByTestId('slot-machine')).toHaveAttribute('data-reel-phase', 'spinning');

    const transformBefore = await track.evaluate((element) => getComputedStyle(element).transform);
    await page.waitForTimeout(160);
    const transformDuring = await track.evaluate((element) => getComputedStyle(element).transform);

    expect(transformDuring).not.toBe(transformBefore);
  });
});
