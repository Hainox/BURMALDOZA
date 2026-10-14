import { expect, test, type Page } from '@playwright/test';
import { openRoom } from './helpers';

type Game = 'slot' | 'blackjack' | 'holdem';
const capture = (globalThis as typeof globalThis & { process?: { env: Record<string, string | undefined> } }).process?.env.POLISH_CAPTURE_PHASE ?? 'after';

async function roomFixture(page: Page, game: Game) {
  const id = '00000000-0000-0000-0000-000000000100';
  const ruleset = game === 'slot' ? 'slot-siege-2' : game === 'blackjack' ? 'blackjack-gfl-skeleton-1' : 'holdem-v1';
  let version = 0;
  let win = true;
  let balance = 1000;
  let state: Record<string, unknown> = game === 'blackjack'
    ? { game_phase: 'waiting', player_cards: [], dealer_cards: [], legal_actions: ['deal'], wallet_balance: 1000 }
    : { phase: 'waiting', legal_actions: ['spin'], operation_id: 'op1' };
  const snapshot = () => ({ room_id: id, game_type: game, mode: 'solo', status: 'active', ruleset_version: ruleset, state_version: version, public_state: state });
  await page.addInitScript(() => {
    (window as unknown as { Telegram: unknown }).Telegram = { WebApp: { initData: 'query_id=design-fixture', ready() {}, expand() {}, setHeaderColor() {}, setBackgroundColor() {} } };
  });
  await page.route('**/api/v1/me', r => r.fulfill({ json: { user_id: 1, telegram_user_id: 1, display_name: 'Fixture' } }));
  await page.route('**/api/v1/wallet', r => r.fulfill({ json: { balance: 1000, currency_code: 'JOKERGEM', version: 1 } }));
  await page.route('**/api/v1/wallet/ledger', r => r.fulfill({ json: [] }));
  await page.route('**/api/v1/leaderboard', r => r.fulfill({ json: { week_start: '2026-10-12T00:00:00+03:00', week_end: '2026-10-19T00:00:00+03:00', entries: [] } }));
  await page.route('**/api/v1/rooms', r => {
    if (game === 'holdem') { balance -= 100; state = {
      phase: 'active', game_phase: 'pre_flop', buy_in: 100, seat: 0, hero_code: 'Kazuma_Kiryu',
      current_seat: 0, current_bet: 10, minimum_raise: 20, pot: 15, stacks: [95, 90], street_contributions: [5, 10],
      legal_actions: ['fold', 'call', 'raise'], community_cards: [], hole_cards: [{ rank: 'A', suit: 'S' }, { rank: 'K', suit: 'S' }],
      wallet_balance: balance, opponent_cards: [{ hidden: true }, { hidden: true }], turn_deadline: new Date(Date.now() + 20000).toISOString(), showdown: false
    }; }
    return r.fulfill({ json: snapshot() });
  });
  await page.route(`**/api/v1/rooms/${id}`, r => r.fulfill({ json: snapshot() }));
  await page.routeWebSocket(`**/api/v1/rooms/${id}/events`, () => {});
  await page.route(`**/api/v1/rooms/${id}/actions`, async r => {
    const request = r.request().postDataJSON();
    version++;
    let result: Record<string, unknown> | undefined;
    if (game === 'slot') {
      balance += win ? 190 : -10;
      result = {
        grid: [[win ? 'A3' : 'D4', 'D1', 'A1', 'D2', 'D3', 'D1', 'D2'], [win ? 'A3' : 'A2', 'D2', 'D3', 'A1', 'D1', 'D3', 'D1'], [win ? 'A3' : 'D2', 'D3', 'D2', 'D1', 'D4', 'D2', 'D3']],
        reel_stops: [0, 0, 0], winning_lines: win ? [{ payline_index: 0, rows: [0, 0, 0], symbols: ['A3', 'A3', 'A3'], match_symbol: 'A3', matched_columns: 3, payout: 200 }] : [],
        gross_payout: win ? 200 : 0, net_delta: win ? 190 : -10, balance_after: balance, ruleset_version: ruleset, operation_id: 'op1'
      };
      state = { ...state, phase: 'active', last_result: result };
    } else if (game === 'blackjack') {
      const player = [{ rank: '10', suit: 'spades' }, { rank: '7', suit: 'hearts' }];
      if (request.payload.action === 'deal') { balance -= 25; state = { ...state, game_phase: 'player_turn', bet: 25, player_cards: player, dealer_cards: [{ rank: '9', suit: 'clubs' }, { hidden: true }], dealer_hole_hidden: true, player_total: 17, legal_actions: ['hit', 'stand', 'double'], wallet_balance: balance }; }
      else {
        if (win) balance += 50;
        state = { ...state, game_phase: 'settled', dealer_cards: [{ rank: '9', suit: 'clubs' }, { rank: win ? '7' : '10', suit: 'diamonds' }], dealer_hole_hidden: false, dealer_total: win ? 16 : 19, legal_actions: ['deal'] };
        result = { outcome: win ? 'win' : 'loss', player_total: 17, dealer_total: win ? 16 : 19, gross_payout: win ? 50 : 0, net_delta: win ? 25 : -25, balance_after: balance, final_bet: 25, ruleset_version: ruleset };
        state = { ...state, last_result: result, wallet_balance: balance };
      }
    } else { balance += win ? 150 : 50; state = {
      ...state, phase: 'settled', game_phase: 'showdown', turn_deadline: null, legal_actions: [], showdown: true, pot: 100, stacks: [50, 50], street_contributions: [50, 50],
      community_cards: win ? [{ rank: 'Q', suit: 'S' }, { rank: 'J', suit: 'S' }, { rank: '10', suit: 'S' }, { rank: '2', suit: 'D' }, { rank: '7', suit: 'C' }] : [{ rank: '9', suit: 'H' }, { rank: '9', suit: 'D' }, { rank: '9', suit: 'C' }, { rank: '2', suit: 'D' }, { rank: '7', suit: 'C' }],
      opponent_cards: win ? [{ rank: '9', suit: 'H' }, { rank: '9', suit: 'D' }] : [{ rank: '9', suit: 'S' }, { rank: 'K', suit: 'H' }], wallet_balance: balance,
      last_result: { winner_seats: [win ? 0 : 1], payouts: win ? [150, 50] : [50, 150], net_deltas: win ? [50, -50] : [-50, 50], outcome: 'showdown' }
    }; }
    await r.fulfill({ json: { event: { event_id: request.action_id, room_id: id, state_version: version, type: `${game}.action.accepted`, ruleset_version: ruleset, server_time: new Date().toISOString(), payload: { action_id: request.action_id, public_state: state, ...(result ? { result } : {}) } } } });
  });
  return { lose: () => { win = false; } };
}

async function screenshot(page: Page, game: Game, phase: string) {
  const directory = '../../assets/design/rooms-polish';
  await page.locator('[data-testid="room-shell"] img').evaluateAll(async images => {
    await Promise.all(images.map(image => (image as HTMLImageElement).decode().catch(() => undefined)));
  });
  await page.screenshot({ path: `${directory}/${capture}-${game}-${phase}-390.png` });
}

for (const game of ['slot', 'blackjack', 'holdem'] as const) {
  test(`${game}: 390px waiting, playing, win and loss`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const fixture = await roomFixture(page, game);
    await page.goto('/');
    await openRoom(page, game);
    if (capture !== 'before' && game === 'slot') {
      expect(await page.getByTestId('slot-spin').evaluate(node => node.getBoundingClientRect().bottom <= innerHeight)).toBe(true);
    }
    await screenshot(page, game, 'waiting');
    for (const outcome of ['win', 'loss']) {
      if (outcome === 'loss') fixture.lose();
      if (game === 'slot') {
        if (outcome === 'win') await page.emulateMedia({ reducedMotion: 'no-preference' });
        await page.getByTestId('slot-spin').click();
        if (outcome === 'win') {
          await expect(page.getByTestId('slot-machine')).not.toHaveAttribute('data-slot-phase', 'settled');
          await screenshot(page, game, 'playing');
        }
        await expect(page.getByTestId('slot-spin')).toBeEnabled({ timeout: 10000 });
        await expect(page.getByTestId('result-band')).toContainText('SERVER CONFIRMED · LIVE');
        await expect(page.locator('.result-amount')).toHaveText(outcome === 'win' ? '+200 JG' : '0 JG');
        if (capture !== 'before') await expect(page.getByTestId('slot-machine')).toHaveAttribute('data-big-win', outcome === 'win' ? 'true' : 'false');
        if (outcome === 'loss') await expect(page.getByTestId('slot-winning-beams')).toHaveCount(0);
      } else if (game === 'blackjack') {
        await page.getByTestId('blackjack-deal').click();
        await expect(page.getByTestId('blackjack-hole-hidden')).toBeVisible();
        if (outcome === 'win') await screenshot(page, game, 'playing');
        if (capture !== 'before') expect(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight)).toBe(true);
        await page.getByTestId('blackjack-stand').click();
        await expect(page.getByTestId('blackjack-settlement')).toContainText(outcome === 'win' ? 'Победа' : 'Поражение');
      } else {
        await page.getByTestId('holdem-start').click();
        await expect(page.getByTestId('holdem-own')).toBeVisible();
        if (outcome === 'win') await screenshot(page, game, 'playing');
        await page.getByTestId('holdem-call').click();
        await expect(page.getByTestId('holdem-result')).toContainText(outcome === 'win' ? 'Победа' : 'Поражение');
      }
      if (capture !== 'before') {
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        if (game === 'slot') expect(await page.getByTestId('slot-spin').evaluate(node => node.getBoundingClientRect().bottom <= innerHeight)).toBe(true);
      }
      await screenshot(page, game, outcome);
      if (capture !== 'before') expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeLessThanOrEqual(844);
      if (game === 'holdem') await page.getByRole('button', { name: 'Выбрать стол' }).click();
    }
  });

  test(`${game}: 320px fits, motion pause disables effects and actions remain usable`, async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 844 });
    await roomFixture(page, game);
    await page.goto('/');
    await expect(page.getByTestId('balance-pill')).toContainText('LIVE');
    await page.getByTestId('hub-motion-toggle').click();
    await expect(page.getByTestId('dashboard')).toHaveAttribute('data-motion-paused', 'true');
    await openRoom(page, game);
    await expect(page.getByTestId('room-shell')).toHaveClass(/quiet/);
    expect(await page.locator('.scene .backdrop').evaluate(node => getComputedStyle(node).animationName)).toBe('none');
    for (const img of await page.locator('.scene img').all()) {
      await expect.poll(() => img.evaluate(node => (node as HTMLImageElement).complete && (node as HTMLImageElement).naturalWidth > 0)).toBe(true);
    }
    if (game === 'slot') {
      await page.getByTestId('slot-spin').click();
      await expect(page.getByTestId('slot-spin')).toBeEnabled({ timeout: 10000 });
      await expect(page.getByTestId('slot-machine')).toHaveAttribute('data-big-win', 'true');
      await expect(page.getByTestId('result-amount')).toHaveText('+200 JG');
      await expect(page.locator('.big-win')).toBeHidden();
      await page.locator('.slot-bet summary').click();
      await page.getByTestId('slot-bet').fill('50');
      // Изменение следующей ставки не переписывает эффект подтверждённого спина.
      await expect(page.getByTestId('slot-machine')).toHaveAttribute('data-big-win', 'true');
    } else if (game === 'blackjack') {
      await page.getByTestId('blackjack-deal').click();
      await page.getByTestId('blackjack-stand').click();
      await expect(page.getByTestId('blackjack-settlement')).toContainText('Победа');
      expect(await page.locator('.felt-table').evaluate(node => getComputedStyle(node, '::after').animationName)).toBe('none');
      await expect(page.locator('.prize-chips')).toBeHidden();
    } else {
      await page.getByTestId('holdem-start').click();
      await expect(page.getByTestId('holdem-intro')).toHaveCount(0);
      await expect(page.locator('.avatar-ring.active')).toHaveCount(1);
      await page.getByTestId('holdem-call').click();
      await expect(page.getByTestId('holdem-result')).toContainText('Победа');
      expect(await page.locator('.stamp').evaluate(node => getComputedStyle(node).animationName)).toBe('none');
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByRole('button', { name: 'Назад к комнатам' }).click();
    await expect(page.getByTestId('dashboard')).toHaveAttribute('data-motion-paused', 'true');
  });
}
