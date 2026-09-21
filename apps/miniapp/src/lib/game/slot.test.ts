import { describe, expect, it } from 'vitest';
import {
  SLOT_REVEAL_DURATION,
  buildReelTrack,
  getSlotStopDelay,
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
    expect(getSlotStopDelay(1)).toBeGreaterThan(getSlotStopDelay(0));
    expect(getSlotStopDelay(2)).toBeGreaterThan(getSlotStopDelay(1));
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
