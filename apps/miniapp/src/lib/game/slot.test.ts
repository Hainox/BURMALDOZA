import { describe, expect, it } from 'vitest';
import {
  SLOT_LAUNCH_STAGGER,
  SLOT_REVEAL_DURATION,
  SLOT_SPIN_DURATION,
  SLOT_STOP_DURATION,
  SLOT_STOP_STAGGER,
  buildReelTrack,
  getSlotLaunchDelay,
  getSlotStopDelay,
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

  it('stops reels from left to right with a deterministic stagger', () => {
    expect(getSlotStopDelay(0)).toBe(0);
    expect(getSlotStopDelay(1)).toBe(SLOT_STOP_STAGGER);
    expect(getSlotStopDelay(2)).toBe(SLOT_STOP_STAGGER * 2);
    expect(getSlotLaunchDelay(0)).toBe(0);
    expect(getSlotLaunchDelay(1)).toBe(SLOT_LAUNCH_STAGGER);
    expect(getSlotLaunchDelay(2)).toBe(SLOT_LAUNCH_STAGGER * 2);
    expect(getSlotStopStart(0)).toBeLessThan(getSlotStopStart(1));
    expect(getSlotStopStart(1)).toBeLessThan(getSlotStopStart(2));
    expect(SLOT_SPIN_DURATION).toBeGreaterThanOrEqual(2_000);
    expect(SLOT_SPIN_DURATION).toBeLessThanOrEqual(3_000);
    expect(SLOT_STOP_DURATION).toBeGreaterThanOrEqual(900);
    expect(SLOT_REVEAL_DURATION).toBeGreaterThan(getSlotStopDelay(2));
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
