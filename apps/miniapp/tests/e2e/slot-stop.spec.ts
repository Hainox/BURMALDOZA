import { expect, test, type Page } from '@playwright/test';

async function sampleTrackTransform(page: Page, index: number) {
  return page.getByTestId(`slot-reel-track-${index}`).evaluate((element) => getComputedStyle(element).transform);
}

test.describe('Slot v2 stop continuity', () => {
  test('moves the computed transform through travel and lands reels at staggered times', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('room-card-slot').click();
    await page.getByTestId('slot-spin').click();

    const machine = page.getByTestId('slot-machine');
    await expect(machine).toHaveAttribute('data-slot-phase', 'spinning', { timeout: 2000 });

    const launches = [
      await page.getByTestId('slot-reel-0').getAttribute('data-launch-delay'),
      await page.getByTestId('slot-reel-1').getAttribute('data-launch-delay'),
      await page.getByTestId('slot-reel-2').getAttribute('data-launch-delay')
    ];
    expect(launches).toEqual(['0', '110', '220']);

    const totalDuration = Number(await machine.getAttribute('data-spin-duration'));
    expect(totalDuration).toBeGreaterThanOrEqual(2000);
    expect(totalDuration).toBeLessThanOrEqual(3000);

    const before = await sampleTrackTransform(page, 0);
    await page.waitForTimeout(200);
    const during = await sampleTrackTransform(page, 0);
    expect(during).not.toBe(before);

    const spinTelemetry = await page.evaluate(async () => {
      const read = (index: number) =>
        (document.querySelector(`[data-testid="slot-reel-${index}"]`) as HTMLElement).getAttribute(
          'data-reel-phase'
        );
      const readTrack = (index: number) =>
        document.querySelector(`[data-testid="slot-reel-track-${index}"]`) as HTMLElement;
      const stamps: number[] = [];
      const started = performance.now();
      const frames: Array<{
        t: number;
        transforms: string[];
        offsets: number[];
        phases: Array<string | null>;
      }> = [];
      for (let guard = 0; guard < 500; guard++) {
        let landed = 0;
        const phases: Array<string | null> = [];
        for (let index = 0; index < 3; index++) {
          const phase = read(index);
          phases.push(phase);
          if (stamps[index] === undefined && phase === 'landed') {
            stamps[index] = performance.now() - started;
          }
          if (phase === 'landed') landed += 1;
        }
        frames.push({
          t: performance.now() - started,
          transforms: [0, 1, 2].map((index) => getComputedStyle(readTrack(index)).transform),
          offsets: [0, 1, 2].map((index) =>
            Number.parseFloat(getComputedStyle(readTrack(index)).getPropertyValue('--reel-offset-rows'))
          ),
          phases
        });
        if (landed === 3) break;
        await new Promise((resolve) => setTimeout(resolve, 10));
      }
      return { stamps, frames };
    });
    const { stamps: landedMs, frames } = spinTelemetry as {
      stamps: number[];
      frames: Array<{
        t: number;
        transforms: string[];
        offsets: number[];
        phases: Array<string | null>;
      }>;
    };
    expect(landedMs).toHaveLength(3);
    expect(landedMs[1]).toBeGreaterThanOrEqual(landedMs[0]);
    expect(landedMs[2]).toBeGreaterThanOrEqual(landedMs[1]);
    expect(landedMs[2] - landedMs[0]).toBeGreaterThanOrEqual(100);

    // Regression for issue #1: all three reels used to share one eased travel and went still
    // together at 2000 ms, so the center and right reel stood parked for 160/320 ms and were
    // then jerked out of standstill by the landing phase. Every reel must keep travelling at
    // its own cruising speed right up to its own stop start.
    for (let reelIndex = 0; reelIndex < 3; reelIndex += 1) {
      const landingIndex = frames.findIndex((frame) => frame.phases[reelIndex] === 'landing');
      expect(landingIndex, `reel ${reelIndex} must pass through a landing phase`).toBeGreaterThan(0);
      const beforeLanding = frames.slice(Math.max(0, landingIndex - 12), landingIndex);
      expect(
        beforeLanding.length,
        `reel ${reelIndex} needs samples before its own stop start`
      ).toBeGreaterThanOrEqual(3);
      const first = beforeLanding[0];
      const last = beforeLanding[beforeLanding.length - 1];
      const span = Math.max(1, last.t - first.t);
      const movedRows = Math.abs(last.offsets[reelIndex] - first.offsets[reelIndex]);
      expect(Number.isFinite(movedRows), `reel ${reelIndex} offset must be a readable number`).toBe(true);
      expect(movedRows / span, `reel ${reelIndex} stalled before its own stop start`).toBeGreaterThan(0.002);
      expect(last.transforms[reelIndex]).not.toBe(first.transforms[reelIndex]);
    }

    const firstLeftLanded = frames.findIndex((frame) => frame.phases[0] === 'landed');
    expect(firstLeftLanded).toBeGreaterThanOrEqual(0);
    const afterLeftLanded = frames.slice(Math.max(0, firstLeftLanded - 1), firstLeftLanded + 5);
    const centerKeepsMoving = afterLeftLanded.some(
      (frame, frameIndex) => frameIndex > 0 && frame.transforms[1] !== afterLeftLanded[frameIndex - 1].transforms[1]
    );
    const rightKeepsMoving = afterLeftLanded.some(
      (frame, frameIndex) => frameIndex > 0 && frame.transforms[2] !== afterLeftLanded[frameIndex - 1].transforms[2]
    );
    expect(centerKeepsMoving).toBe(true);
    expect(rightKeepsMoving).toBe(true);

    const travelStart = frames.findIndex((frame) => frame.phases[0] === 'travel');
    expect(travelStart).toBeGreaterThanOrEqual(0);
    const earlyTravel = frames.slice(travelStart, travelStart + 8);
    expect(earlyTravel.length).toBeGreaterThanOrEqual(4);
    const transformMoves = [0, 1, 2].map((index) =>
      earlyTravel.some(
        (frame, frameIndex) => frameIndex > 0 && frame.transforms[index] !== earlyTravel[frameIndex - 1].transforms[index]
      )
    );
    expect(transformMoves).toEqual([true, true, true]);

    await expect(machine).toHaveAttribute('data-slot-phase', 'settled', { timeout: 5000 });
    await expect(machine).toHaveAttribute('data-stopped-reels', '3');
    await expect(machine.locator('[data-reel-phase="landed"]')).toHaveCount(3);
    await expect(page.getByTestId('slot-confirmed-grid')).toBeVisible();
  });

  test('runs travel and staged left-to-right landing phases', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('room-card-slot').click();

    const machine = page.getByTestId('slot-machine');
    await machine.evaluate((element) => {
      type SlotMachineDebug = HTMLElement & {
        __slotPhaseLog?: string[];
        __slotPhaseObserver?: MutationObserver;
      };
      const target = element as SlotMachineDebug;
      const log: string[] = [];
      const record = () => {
        const signature = `${target.getAttribute('data-slot-phase')}:${target.getAttribute('data-stopped-reels')}`;
        if (log.at(-1) !== signature) log.push(signature);
      };
      record();
      target.__slotPhaseObserver = new MutationObserver(record);
      target.__slotPhaseObserver.observe(target, {
        attributes: true,
        attributeFilter: ['data-slot-phase', 'data-stopped-reels']
      });
      target.__slotPhaseLog = log;
    });
    await page.getByTestId('slot-spin').click();

    await expect(machine).toHaveAttribute('data-slot-phase', 'settled', { timeout: 5_000 });
    const phaseLog = await machine.evaluate((element) => {
      type SlotMachineDebug = HTMLElement & {
        __slotPhaseLog?: string[];
        __slotPhaseObserver?: MutationObserver;
      };
      const target = element as SlotMachineDebug;
      target.__slotPhaseObserver?.disconnect();
      return target.__slotPhaseLog ?? [];
    });
    const phases = phaseLog.map((entry) => entry.split(':')[0]);
    expect(phases).toEqual(expect.arrayContaining(['spinning', 'stopping-left', 'stopping-center', 'stopping-right', 'settled']));
    expect(phases.indexOf('stopping-left')).toBeLessThan(phases.indexOf('stopping-center'));
    expect(phases.indexOf('stopping-center')).toBeLessThan(phases.indexOf('stopping-right'));
    expect(phaseLog.map((entry) => entry.split(':')[1])).toEqual(expect.arrayContaining(['0', '1', '2', '3']));
    await expect(machine.locator('[data-reel-phase="landed"]')).toHaveCount(3);
    await expect(page.getByTestId('slot-confirmed-grid')).toBeVisible();
  });

  test('announces landing progress and disables spin until settled', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('room-card-slot').click();

    const machine = page.getByTestId('slot-machine');
    const spin = page.getByTestId('slot-spin');
    const status = page.getByTestId('slot-status');
    const seqBefore = await machine.getAttribute('data-spin-seq');

    await spin.click();
    await expect(machine).toHaveAttribute('data-slot-phase', 'spinning', { timeout: 2_000 });
    await expect(status).toContainText('TRAVEL');
    await expect(spin).toBeDisabled();
    await expect(spin).toContainText('Барабаны останавливаются');

    // A repeated tap mid-spin must not restart the reel ticker.
    await spin.click({ force: true });
    const seqAfterSecondTap = await machine.getAttribute('data-spin-seq');
    expect(seqAfterSecondTap).toBe(seqBefore === null ? '1' : String(Number(seqBefore) + 1));

    await expect(machine).toHaveAttribute('data-slot-phase', 'settled', { timeout: 5_000 });
    await expect(status).toContainText('SETTLED');
    await expect(spin).toBeEnabled();
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

  test('renders the live canonical grid and payout without a client-side substitute', async ({ page }) => {
    const roomId = '00000000-0000-0000-0000-000000000042';
    const serverResult = {
      grid: [
        ['A', 'A', 'A', 'B', 'B', 'C', 'C'],
        ['A', 'A', 'A', 'B', 'B', 'C', 'C'],
        ['A', 'A', 'A', 'B', 'B', 'C', 'C']
      ],
      reel_stops: [0, 0, 0],
      winning_lines: [
        {
          payline_index: 0,
          rows: [3, 3, 3],
          symbols: ['B', 'B', 'B'],
          match_symbol: 'B',
          matched_columns: 3,
          payout: 20
        }
      ],
      gross_payout: 20,
      net_delta: 10,
      balance_after: 1_010,
      ruleset_version: 'slot-skeleton-1'
    };

    await page.addInitScript(() => {
      (window as typeof window & { Telegram?: unknown }).Telegram = {
        WebApp: {
          initData: 'query_id=verified',
          ready: () => undefined,
          expand: () => undefined,
          setHeaderColor: () => undefined,
          setBackgroundColor: () => undefined
        }
      };
    });
    await page.route('**/api/v1/me', (route) => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ user_id: 12345, telegram_user_id: 12345, display_name: 'Test User' })
    }));
    await page.route('**/api/v1/wallet', (route) => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ user_id: 12345, balance: 1_000, currency_code: 'JOKERGEM', version: 1 })
    }));
    await page.route('**/api/v1/rooms', async (route) => {
      if (route.request().method() !== 'POST') return route.continue();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          room_id: roomId,
          game_type: 'slot',
          mode: 'solo',
          status: 'waiting',
          ruleset_version: 'slot-skeleton-1',
          state_version: 0,
          public_state: { phase: 'waiting', legal_actions: ['spin'], action_count: 0 }
        })
      });
    });
    await page.route(`**/api/v1/rooms/${roomId}/actions`, async (route) => {
      const request = route.request().postDataJSON() as { action_id: string };
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          event: {
            event_id: request.action_id,
            room_id: roomId,
            state_version: 1,
            type: 'slot.action.accepted',
            ruleset_version: 'slot-skeleton-1',
            server_time: '2026-09-22T00:00:00Z',
            payload: {
              action_id: request.action_id,
              public_state: { phase: 'active', last_result: serverResult },
              result: serverResult
            },
            animation_hint: 'slot.reels.stop.staggered'
          }
        })
      });
    });
    await page.route(`**/api/v1/rooms/${roomId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          room_id: roomId,
          game_type: 'slot',
          mode: 'solo',
          status: 'active',
          ruleset_version: 'slot-skeleton-1',
          state_version: 1,
          public_state: { phase: 'active', last_result: serverResult }
        })
      });
    });

    await page.goto('/');
    await page.getByTestId('room-card-slot').click();
    await expect(page.getByTestId('room-shell')).toBeVisible();
    await expect(page.locator('.slot-room')).toContainText('Полная прокрутка барабанов. Сервер подтверждает сетку, клиент показывает движение.');
    await expect(page.getByTestId('slot-status')).toContainText('READY · SERVER-FIRST');
    await page.getByTestId('slot-spin').click();
    await expect(page.getByTestId('result-band')).toContainText('RESOLVING · SERVER RESULT');
    await expect(page.getByTestId('slot-machine')).toHaveAttribute('data-stopped-reels', '3', { timeout: 5_000 });
    await expect(page.getByTestId('result-band')).toContainText('SERVER CONFIRMED · LIVE');
    await expect(page.getByTestId('result-band')).toContainText('+20 JG');
    await expect(page.getByTestId('slot-confirmed-grid')).toBeVisible();
    await expect(page.getByTestId('slot-confirmed-grid')).toContainText('SERVER GRID CONFIRMED');
    await expect(page.getByTestId('slot-status')).toContainText('SETTLED · SERVER GRID');
    await expect(page.getByTestId('confirmed-balance')).toContainText('BALANCE 1010 JG');

    await page.getByTestId('resync-button').click();
    await expect(page.getByTestId('room-shell')).toHaveAttribute('data-motion', 'settle');
    await expect(page.getByTestId('resync-button')).toHaveText('LIVE');
    await expect(page.getByTestId('result-band')).toContainText('SERVER CONFIRMED · LIVE');
    await expect(page.getByTestId('slot-confirmed-grid')).toBeVisible();
    await expect(page.getByTestId('confirmed-balance')).toContainText('BALANCE 1010 JG');
  });
});
