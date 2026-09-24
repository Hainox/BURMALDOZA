import { expect, test } from '@playwright/test';

test.describe('Slot stop continuity', () => {
  test('travels full reels then lands left-center-right without snapping', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('room-card-slot').click();
    await expect(page.getByTestId('room-shell')).toBeVisible();
    await page.getByTestId('slot-spin').click();

    const reelGrid = page.locator('.slot-room .reel-grid');
    await expect
      .poll(async () => reelGrid.getAttribute('data-motion'), { timeout: 2000 })
      .toBe('resolving');
    await expect(reelGrid).toHaveAttribute('data-slot-phase', 'spinning', { timeout: 2000 });
    await expect(page.getByTestId('slot-status')).toContainText('Барабаны вращаются');

    await expect
      .poll(async () => reelGrid.getAttribute('data-slot-phase'), { timeout: 5000, intervals: [25, 50, 100] })
      .toBe('stopping-left');
    await expect(page.getByTestId('slot-reel-0')).toHaveAttribute('data-reel-phase', 'landed');

    await expect
      .poll(async () => reelGrid.getAttribute('data-slot-phase'), { timeout: 5000, intervals: [25, 50, 100] })
      .toBe('stopping-center');
    await expect(page.getByTestId('slot-reel-1')).toHaveAttribute('data-reel-phase', 'landed');

    await expect
      .poll(async () => reelGrid.getAttribute('data-slot-phase'), { timeout: 5000, intervals: [25, 50, 100] })
      .toBe('stopping-right');
    await expect(page.getByTestId('slot-reel-2')).toHaveAttribute('data-reel-phase', 'landed');

    await expect(page.getByTestId('result-band')).toContainText('SERVER CONFIRMED · DEMO');
    await expect(page.getByTestId('result-band')).toContainText('Линия подтверждена');
    await expect(reelGrid).toHaveAttribute('data-stopped-reels', '3');

    // Every reel lands back on the confirmed strip: no shift, and the first symbol fills the window top.
    const landing = await page.evaluate(() =>
      [...document.querySelectorAll<HTMLElement>('.slot-room .reel')].map((reel) => {
        const track = reel.querySelector<HTMLElement>('.reel-track');
        const windowNode = reel.querySelector<HTMLElement>('.reel-window');
        const first = reel.querySelector<HTMLElement>('.symbol');
        const windowTop = windowNode?.getBoundingClientRect().top ?? NaN;
        const firstTop = first?.getBoundingClientRect().top ?? NaN;
        return { transform: track?.style.transform ?? '', drift: Math.abs(firstTop - windowTop) };
      })
    );
    expect(landing).toHaveLength(3);
    for (const reel of landing) {
      expect(reel.transform).toMatch(/^translate3d\(0(px)?,\s*-?0(\.0+)?px,\s*0/);
      expect(reel.drift).toBeLessThan(1);
    }
  });

  test('keeps symbols inside every reel window mid-spin', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('room-card-slot').click();
    await page.getByTestId('slot-spin').click();
    const reelGrid = page.locator('.slot-room .reel-grid');
    await expect(reelGrid).toHaveAttribute('data-slot-phase', 'spinning', { timeout: 2000 });
    await page.waitForTimeout(1200);

    const coverage = await page.evaluate(() =>
      [...document.querySelectorAll<HTMLElement>('.slot-room .reel-window')].map((windowNode) => {
        const box = windowNode.getBoundingClientRect();
        const visible = [...windowNode.querySelectorAll<HTMLElement>('.symbol')].filter((symbol) => {
          const rect = symbol.getBoundingClientRect();
          return rect.bottom > box.top && rect.top < box.bottom;
        });
        return visible.length;
      })
    );
    expect(coverage).toHaveLength(3);
    for (const visibleSymbols of coverage) {
      expect(visibleSymbols).toBeGreaterThanOrEqual(7);
    }
  });

  test('reduced motion freezes the confirmed grid immediately', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    await page.getByTestId('room-card-slot').click();
    await page.getByTestId('slot-spin').click();

    await expect(page.getByTestId('result-band')).toContainText('SERVER CONFIRMED · DEMO');
    await expect(page.getByTestId('slot-status')).toContainText('Сетка подтверждена');
  });
});
