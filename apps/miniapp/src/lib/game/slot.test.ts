import { describe, expect, it } from 'vitest';
import {
  SLOT_ACTION_ACCEPT_DELAY,
  SLOT_FINAL_OFFSET_ROWS,
  SLOT_LAUNCH_STAGGER,
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
