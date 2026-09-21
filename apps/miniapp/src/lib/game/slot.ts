export const SLOT_REEL_COUNT = 3;
export const SLOT_ROW_COUNT = 7;
export const SLOT_REEL_COPIES = 3;
export const SLOT_STOP_DURATION = 620;
export const SLOT_STOP_STAGGER = 120;
export const SLOT_REVEAL_DURATION = SLOT_STOP_DURATION + SLOT_STOP_STAGGER * 2 + 40;

export interface SlotOutcome {
  reels: string[][];
  winningRows: number[];
  payout: number;
  balance: number;
  freeSpinsAwarded: number;
  freeSpinsRemaining: number;
}

export function buildReelTrack(baseSymbols: string[], confirmedSymbols: string[], copies = SLOT_REEL_COPIES) {
  return [...Array.from({ length: copies }, () => baseSymbols).flat(), ...confirmedSymbols];
}

export function getSlotStopDelay(reelIndex: number) {
  return Math.max(0, reelIndex) * SLOT_STOP_STAGGER;
}

export function hasFreeSpins(outcome: SlotOutcome | null) {
  return (outcome?.freeSpinsRemaining ?? 0) > 0;
}
