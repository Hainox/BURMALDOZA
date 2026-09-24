import { describe, expect, it } from 'vitest';
import {
  SLOT_LAUNCH_OFFSETS_MS,
  SLOT_SETTLE_MS,
  SLOT_SPIN_TRAVEL_MS,
  SLOT_STRIP_LENGTH,
  isSlotSettled,
  planSlotReelStops,
  reelStopDelayMs,
  slotReelDecelStartMs,
  slotReelMovingAt,
  slotReelOffsetAt,
  slotReelPhaseAt,
  slotReelTrackShiftPx,
  stoppedReelCountAt,
  wrapSlotReelOffset
} from './slot';

describe('slot stop continuity', () => {
  it('keeps full vertical travel before the first reel stops', () => {
    const plan = planSlotReelStops();
    expect(plan.reelStopsMs[0]).toBeGreaterThanOrEqual(SLOT_SPIN_TRAVEL_MS);
    expect(plan.reelStopsMs).toEqual([2320, 2680, 3040]);
    expect(plan.totalMs).toBe(3040 + SLOT_SETTLE_MS);
  });

  it('staggers launches left-center-right without overlap on the first frames', () => {
    expect([...SLOT_LAUNCH_OFFSETS_MS]).toEqual([0, 110, 220]);
    expect(reelStopDelayMs(0)).toBe(0);
    expect(reelStopDelayMs(1)).toBe(110);
    expect(reelStopDelayMs(2)).toBe(220);
  });

  it('walks spinning through ordered stops into settle without jumps', () => {
    const plan = planSlotReelStops();
    const phases = [
      slotReelPhaseAt(0, plan),
      slotReelPhaseAt(plan.reelStopsMs[0], plan),
      slotReelPhaseAt(plan.reelStopsMs[1], plan),
      slotReelPhaseAt(plan.reelStopsMs[2], plan),
      slotReelPhaseAt(plan.totalMs, plan)
    ];
    expect(phases).toEqual(['spinning', 'stopping-left', 'stopping-center', 'stopping-right', 'settled']);
    expect(plan.reelStopsMs[0]).toBeLessThan(plan.reelStopsMs[1]);
    expect(plan.reelStopsMs[1]).toBeLessThan(plan.reelStopsMs[2]);
  });

  it('counts stopped reels monotonically and reports settle only at the end', () => {
    const plan = planSlotReelStops();
    expect(stoppedReelCountAt(0, plan)).toBe(0);
    expect(stoppedReelCountAt(plan.reelStopsMs[0], plan)).toBe(1);
    expect(stoppedReelCountAt(plan.reelStopsMs[1], plan)).toBe(2);
    expect(stoppedReelCountAt(plan.reelStopsMs[2], plan)).toBe(3);
    expect(isSlotSettled(plan.totalMs - 1, plan)).toBe(false);
    expect(isSlotSettled(plan.totalMs, plan)).toBe(true);
  });

  it('collapses to an immediate settled grid under reduced motion', () => {
    const plan = planSlotReelStops({ reducedMotion: true });
    expect(plan.totalMs).toBe(0);
    expect(slotReelPhaseAt(0, plan)).toBe('settled');
    expect(isSlotSettled(0, plan)).toBe(true);
  });

  it('moves each reel offset continuously without position snapping', () => {
    const plan = planSlotReelStops();
    for (const reel of [0, 1, 2] as const) {
      let previous = slotReelOffsetAt(0, reel, plan);
      for (let elapsed = 16; elapsed <= plan.totalMs; elapsed += 16) {
        const current = slotReelOffsetAt(elapsed, reel, plan);
        expect(Math.abs(current - previous)).toBeLessThan(0.35);
        previous = current;
      }
      const decelStart = slotReelDecelStartMs(reel, plan);
      expect(slotReelMovingAt(decelStart - 1, reel, plan)).toBe(true);
      expect(slotReelMovingAt(plan.reelStopsMs[reel], reel, plan)).toBe(false);
      expect(slotReelOffsetAt(plan.reelStopsMs[reel], reel, plan)).toBe(
        slotReelOffsetAt(plan.totalMs, reel, plan)
      );
    }
  });

  it('staggers deceleration waves without overlapping stops', () => {
    const plan = planSlotReelStops();
    const waves = [0, 1, 2].map((reel) => slotReelDecelStartMs(reel as 0 | 1 | 2, plan));
    expect(waves[0]).toBeLessThan(waves[1]);
    expect(waves[1]).toBeLessThan(waves[2]);
    expect(waves[0]).toBeGreaterThanOrEqual(1500);
  });

  it('makes several full strip passes and lands exactly on the confirmed grid', () => {
    const plan = planSlotReelStops();
    for (const reel of [0, 1, 2] as const) {
      const landed = slotReelOffsetAt(plan.totalMs, reel, plan);
      expect(-landed).toBeGreaterThanOrEqual(SLOT_STRIP_LENGTH * 4);
      expect(Math.abs(landed % SLOT_STRIP_LENGTH)).toBe(0);
      expect(slotReelTrackShiftPx(plan.totalMs, reel, plan, 40, 5)).toBe(0);
    }
  });

  it('decelerates without a velocity jump at the start of the stop tail', () => {
    const plan = planSlotReelStops();
    const step = 4;
    for (const reel of [0, 1, 2] as const) {
      const decel = slotReelDecelStartMs(reel, plan);
      const before = slotReelOffsetAt(decel, reel, plan) - slotReelOffsetAt(decel - step, reel, plan);
      const after = slotReelOffsetAt(decel + step, reel, plan) - slotReelOffsetAt(decel, reel, plan);
      expect(Math.abs(after - before)).toBeLessThan(Math.abs(before) * 0.05);
      const last = slotReelOffsetAt(plan.reelStopsMs[reel], reel, plan) -
        slotReelOffsetAt(plan.reelStopsMs[reel] - step, reel, plan);
      expect(Math.abs(last)).toBeLessThan(Math.abs(before) * 0.05);
    }
  });

  it('wraps the painted shift inside one strip so the reel window never empties', () => {
    const plan = planSlotReelStops();
    const symbolPx = 40;
    const gapPx = 5;
    const stripPx = SLOT_STRIP_LENGTH * (symbolPx + gapPx);
    for (let elapsed = 0; elapsed <= plan.totalMs; elapsed += 16) {
      for (const reel of [0, 1, 2] as const) {
        const shift = slotReelTrackShiftPx(elapsed, reel, plan, symbolPx, gapPx);
        expect(shift).toBeLessThanOrEqual(0);
        expect(shift).toBeGreaterThan(-stripPx);
      }
    }
    expect(slotReelTrackShiftPx(1000, 0, plan, 0, gapPx)).toBe(0);
    const reduced = planSlotReelStops({ reducedMotion: true });
    expect(slotReelTrackShiftPx(1000, 0, reduced, symbolPx, gapPx)).toBe(0);
  });

  it('folds offsets into a single strip', () => {
    expect(wrapSlotReelOffset(0)).toBe(0);
    expect(wrapSlotReelOffset(-SLOT_STRIP_LENGTH * 3)).toBe(0);
    expect(wrapSlotReelOffset(-8.5)).toBeCloseTo(-1.5);
    expect(wrapSlotReelOffset(-6.25)).toBeCloseTo(-6.25);
  });
});
