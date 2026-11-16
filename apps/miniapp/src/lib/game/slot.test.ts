import { describe, expect, it } from 'vitest';
import {
  SLOT_ACTION_ACCEPT_DELAY,
  SLOT_FINAL_OFFSET_ROWS,
  SLOT_LAUNCH_STAGGER,
  SLOT_LANDING_DURATION,
  SLOT_LANDING_TAILS,
  SLOT_RAMP_DURATION,
  SLOT_SERVER_RESULT_PRELUDE,
  SLOT_SPIN_DURATION,
  SLOT_SETTLE_DURATION,
  SLOT_TOTAL_DURATION,
  SLOT_TRAVEL_DURATION,
  buildReelTrack,
  getSlotPhase,
  getSlotReelOffsetRows,
  getSlotReelPhase,
  getSlotReelVelocityRowsPerMs,
  getSlotLaunchDelay,
  getSlotStopDelay,
  getSlotStopEnd,
  getSlotStopStart,
  hasFreeSpins,
  type SlotOutcome
} from './slot';

describe('slot v2 motion contract', () => {
  it('brakes gradually for at least 700 ms without a sudden acceleration change', () => {
    for (let reel = 0; reel < 3; reel += 1) {
      const start = getSlotStopStart(reel);
      const end = getSlotStopEnd(reel);
      expect(end - start).toBeGreaterThanOrEqual(700);
      const cruise = getSlotReelVelocityRowsPerMs(reel, start);
      // At 60 Hz, entering the brake must not immediately shed a visible chunk of speed.
      expect(getSlotReelVelocityRowsPerMs(reel, start + 16) / cruise).toBeGreaterThan(0.995);
      expect(getSlotReelVelocityRowsPerMs(reel, end - 16) / cruise).toBeLessThan(0.005);
      expect(getSlotReelVelocityRowsPerMs(reel, start + (end - start) / 2) / cruise).toBeCloseTo(0.5, 5);
    }
  });

  it('builds a long reel track that ends with the confirmed symbols', () => {
    expect(buildReelTrack(['A', 'B'], ['X', 'Y'], 3)).toEqual([
      'A',
      'B',
      'A',
      'B',
      'A',
      'B',
      'X',
      'Y'
    ]);
  });

  it('preserves the launch window while keeping varied cruising symbols', () => {
    expect(buildReelTrack(['A', 'B'], ['Y', 'Z'], 3, ['X', 'X'])).toEqual([
      'X', 'X', 'A', 'B', 'A', 'B', 'Y', 'Z'
    ]);
  });

  it('keeps the server-confirmed timeline deterministic', () => {
    expect(getSlotStopDelay(0)).toBe(0);
    expect(getSlotStopDelay(1)).toBe(SLOT_LANDING_TAILS[1] - SLOT_LANDING_TAILS[0]);
    expect(getSlotStopDelay(2)).toBe(SLOT_LANDING_TAILS[2] - SLOT_LANDING_TAILS[0]);
    expect(getSlotLaunchDelay(0)).toBe(0);
    expect(getSlotLaunchDelay(1)).toBe(SLOT_LAUNCH_STAGGER);
    expect(getSlotLaunchDelay(2)).toBe(SLOT_LAUNCH_STAGGER * 2);
    expect(getSlotStopStart(0)).toBe(SLOT_TRAVEL_DURATION);
    expect(getSlotStopStart(1)).toBeGreaterThan(getSlotStopStart(0));
    expect(getSlotStopStart(2)).toBeGreaterThan(getSlotStopStart(1));
    expect(SLOT_SPIN_DURATION).toBe(SLOT_TOTAL_DURATION);
    expect(SLOT_TOTAL_DURATION).toBe(SLOT_TRAVEL_DURATION + SLOT_LANDING_TAILS[2] + SLOT_SETTLE_DURATION);
  });

  it('walks through left, center, right and settled phases', () => {
    expect(getSlotPhase(0)).toBe('spinning');
    expect(getSlotPhase(SLOT_TRAVEL_DURATION)).toBe('stopping-left');
    expect(getSlotPhase(getSlotStopStart(1))).toBe('stopping-center');
    expect(getSlotPhase(getSlotStopStart(2))).toBe('stopping-right');
    expect(getSlotPhase(SLOT_TOTAL_DURATION)).toBe('settled');
    expect(SLOT_ACTION_ACCEPT_DELAY + SLOT_TOTAL_DURATION).toBe(3_080);
    expect(SLOT_SERVER_RESULT_PRELUDE).toBe(520);
  });

  it('keeps velocity continuous across each stop-start without an early stall', () => {
    for (let reelIndex = 0; reelIndex < 3; reelIndex += 1) {
      const landingStart = getSlotStopStart(reelIndex);
      const cruiseVelocity = getSlotReelVelocityRowsPerMs(reelIndex, landingStart - 64);
      expect(cruiseVelocity).toBeGreaterThan(0);

      const expectedCruiseVelocity =
        SLOT_FINAL_OFFSET_ROWS /
        (SLOT_RAMP_DURATION / 2 +
          (landingStart - getSlotLaunchDelay(reelIndex) - SLOT_RAMP_DURATION) +
          SLOT_LANDING_DURATION / 2);
      expect(cruiseVelocity).toBeCloseTo(expectedCruiseVelocity, 8);

      const velocityBefore = getSlotReelVelocityRowsPerMs(reelIndex, landingStart - 8);
      const velocityAfter = getSlotReelVelocityRowsPerMs(reelIndex, landingStart + 8);
      expect(Math.abs(velocityBefore - velocityAfter)).toBeLessThanOrEqual(0.15 * cruiseVelocity);
      expect(velocityAfter).toBeGreaterThanOrEqual(0.8 * cruiseVelocity);

      for (let elapsedMs = getSlotLaunchDelay(reelIndex) + SLOT_RAMP_DURATION; elapsedMs < landingStart; elapsedMs += 16) {
        expect(getSlotReelVelocityRowsPerMs(reelIndex, elapsedMs)).toBeGreaterThanOrEqual(
          0.8 * cruiseVelocity
        );
      }

      expect(getSlotReelVelocityRowsPerMs(reelIndex, landingStart)).toBeCloseTo(cruiseVelocity, 6);
      expect(getSlotReelOffsetRows(reelIndex, getSlotStopEnd(reelIndex))).toBe(-SLOT_FINAL_OFFSET_ROWS);
      expect(getSlotReelOffsetRows(reelIndex, getSlotStopEnd(reelIndex) - 1)).toBeCloseTo(
        -SLOT_FINAL_OFFSET_ROWS,
        4
      );
    }
  });

  it('integrates the visible track without jumps, reversal or endpoint overshoot', () => {
    for (let reel = 0; reel < 3; reel += 1) {
      let previous = 0;
      for (let ms = 0; ms <= SLOT_TOTAL_DURATION; ms += 8) {
        const position = getSlotReelOffsetRows(reel, ms);
        expect(position).toBeLessThanOrEqual(previous + 1e-10);
        expect(position).toBeGreaterThanOrEqual(-SLOT_FINAL_OFFSET_ROWS - 1e-10);
        if (ms > getSlotLaunchDelay(reel) + 1 && ms < getSlotStopEnd(reel) - 1) {
          const actualVelocity = -(getSlotReelOffsetRows(reel, ms + 0.1) - getSlotReelOffsetRows(reel, ms - 0.1)) / 0.2;
          expect(actualVelocity).toBeCloseTo(getSlotReelVelocityRowsPerMs(reel, ms), 6);
        }
        previous = position;
      }
    }
  });

  it('collapses every reel to landed under reduced motion', () => {
    expect(getSlotPhase(0, true)).toBe('settled');
    expect(getSlotReelPhase(0, 0, true)).toBe('landed');
    expect(getSlotReelOffsetRows(0, 0, true)).toBeLessThan(0);
  });

  it('exposes free spins only when the server outcome confirms them', () => {
    const outcome: SlotOutcome = {
      reels: [[], [], []],
      winningRows: [3],
      payout: 40,
      balance: 1_030,
      freeSpinsAwarded: 5,
      freeSpinsRemaining: 5
    };

    expect(hasFreeSpins(outcome)).toBe(true);
    expect(hasFreeSpins({ ...outcome, freeSpinsRemaining: 0 })).toBe(false);
    expect(hasFreeSpins(null)).toBe(false);
  });
});
