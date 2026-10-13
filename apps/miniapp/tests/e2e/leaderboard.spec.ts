import { expect, test, type Page } from '@playwright/test';

const snapshot = { week_start: '2026-10-11T21:00:00Z', week_end: '2026-10-18T21:00:00Z',
  entries: [{ rank: 1, nickname: '@winner', net_result: 250 },
    { rank: 2, nickname: 'Игрок без ника', net_result: -75 }] };

async function live(page: Page) {
  await page.addInitScript(() => {
    (window as typeof window & { Telegram?: unknown }).Telegram = { WebApp: {
      initData: 'query_id=leaderboard-test', ready() {}, expand() {}, setHeaderColor() {}, setBackgroundColor() {}
    } };
  });
  await page.route('**/api/v1/wallet', route => route.fulfill({ json: {
    user_id: 1, balance: 1000, currency_code: 'JOKERGEM', version: 1
  } }));
  await page.route('**/api/v1/wallet/ledger', route => route.fulfill({ json: [] }));
}

test('DEMO never invents a leaderboard or requests one', async ({ page }) => {
  let requests = 0;
  await page.route('**/api/v1/leaderboard', route => { requests++; return route.fulfill({ json: snapshot }); });
  await page.goto('/');
  await expect(page.getByTestId('leaderboard-demo')).toContainText('Настоящий рейтинг');
  await expect(page.getByTestId('leaderboard-entry')).toHaveCount(0);
  expect(requests).toBe(0);
});

for (const viewport of [{ width: 320, height: 812 }, { width: 1440, height: 900 }]) {
  test(`confirmed net results and Moscow period at ${viewport.width}px with reduced motion`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await live(page);
    await page.route('**/api/v1/leaderboard', route => {
      expect(route.request().headers()['x-telegram-init-data']).toBe('query_id=leaderboard-test');
      return route.fulfill({ json: snapshot });
    });
    await page.goto('/');
    const ranking = page.getByTestId('leaderboard');
    await expect(ranking).toContainText('@winner');
    await expect(ranking).toContainText('Игрок без ника');
    await expect(ranking).toContainText('+250 JG');
    await expect(ranking).toContainText('-75 JG');
    await expect(page.getByTestId('leaderboard-period')).toHaveText('12.10.2026 00:00 — 19.10.2026 00:00 МСК');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}

test('loading, error, keyboard retry, empty current week', async ({ page }) => {
  await live(page);
  let release: () => void = () => {};
  const gate = new Promise<void>(resolve => { release = resolve; });
  let calls = 0;
  await page.route('**/api/v1/leaderboard', async route => {
    if (++calls === 1) { await gate; await route.fulfill({ status: 503, json: { detail: 'unavailable' } }); }
    else await route.fulfill({ json: { ...snapshot, entries: [] } });
  });
  await page.goto('/');
  await expect(page.getByTestId('leaderboard')).toContainText('Загружаем рейтинг');
  release();
  const retry = page.getByRole('button', { name: 'Повторить загрузку рейтинга' });
  await expect(retry).toBeVisible();
  await retry.focus();
  await retry.press('Enter');
  await expect(page.getByTestId('leaderboard-empty')).toBeVisible();
});
