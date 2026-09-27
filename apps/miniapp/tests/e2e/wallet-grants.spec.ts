import { expect, test, type Page, type Route } from '@playwright/test';

async function stubLiveWallet(page: Page, options: { reliefCooldown?: boolean } = {}) {
  let walletBalance = 1000;
  let grantCalls = 0;

  await page.addInitScript(() => {
    (window as typeof window & { Telegram?: unknown }).Telegram = {
      WebApp: {
        initData: 'query_id=verified-wallet',
        ready: () => undefined,
        expand: () => undefined,
        setHeaderColor: () => undefined,
        setBackgroundColor: () => undefined
      }
    };
  });
  await page.route('**/api/v1/wallet', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ user_id: 777, balance: walletBalance, currency_code: 'JOKERGEM', version: 1 })
    })
  );
  await page.route('**/api/v1/wallet/daily-bonus/claim', async (route: Route) => {
    grantCalls += 1;
    walletBalance += 250;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        operation_id: `daily-${grantCalls}`,
        idempotency_key: route.request().headers()['x-request-id'] ?? 'daily',
        user_id: 777,
        delta: 250,
        balance_after: walletBalance,
        reason: 'daily'
      })
    });
  });
  await page.route('**/api/v1/wallet/relief/claim', async (route: Route) => {
    grantCalls += 1;
    if (options.reliefCooldown === true) {
      await route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ detail: 'cooldown' }) });
      return;
    }
    walletBalance += 300;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        operation_id: `relief-${grantCalls}`,
        idempotency_key: route.request().headers()['x-request-id'] ?? 'relief',
        user_id: 777,
        delta: 300,
        balance_after: walletBalance,
        reason: 'relief'
      })
    });
  });

  return {
    grantCalls: () => grantCalls
  };
}

test.describe('Wallet grants', () => {
  test('claims daily once, blocks a repeated tap, and updates balance from the server', async ({ page }) => {
    const counters = await stubLiveWallet(page);
    await page.goto('/');

    await expect(page.getByTestId('wallet-daily-claim')).toBeVisible();
    await page.getByTestId('wallet-daily-claim').click();
    await expect(page.getByTestId('wallet-daily-message')).toContainText('Начислено +250 JG');
    await expect(page.getByTestId('wallet-daily-message')).toContainText('баланс 1250 JG');
    await expect(page.getByTestId('balance-pill')).toContainText('1 250');
    expect(counters.grantCalls()).toBe(1);

    const claim = page.getByTestId('wallet-daily-claim');
    await Promise.all([claim.click(), page.getByTestId('wallet-daily-message').waitFor({ state: 'visible' })]);
    expect(counters.grantCalls()).toBeLessThanOrEqual(2);
  });

  test('treats relief 409 as an expected cooldown state', async ({ page }) => {
    await stubLiveWallet(page, { reliefCooldown: true });
    await page.goto('/');

    await page.getByTestId('wallet-relief-claim').click();
    await expect(page.getByTestId('wallet-relief-message')).toContainText('Relief пока недоступен');
    await expect(page.getByTestId('balance-pill')).toContainText('1 000');
  });

  test('keeps grants in live mode only', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('demo-banner')).toContainText('ДЕМО-КОНТУР');
    await expect(page.getByTestId('wallet-grants')).toHaveCount(0);
  });
});
