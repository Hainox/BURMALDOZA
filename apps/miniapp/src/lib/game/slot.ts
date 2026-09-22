export const SLOT_REEL_COUNT = 3;
export const SLOT_ROW_COUNT = 7;
export const SLOT_REEL_COPIES = 3;
export const SLOT_FINAL_OFFSET_ROWS = SLOT_ROW_COUNT * SLOT_REEL_COPIES;
export const SLOT_SPIN_DURATION = 2_400;
export const SLOT_SPIN_CYCLE_DURATION = 840;
export const SLOT_SPIN_CYCLE_ROWS = SLOT_ROW_COUNT;
export const SLOT_LAUNCH_DURATION = 280;
export const SLOT_LAUNCH_STAGGER = 110;
export const SLOT_STOP_DURATION = 960;
export const SLOT_STOP_STAGGER = 170;
export const SLOT_REVEAL_DURATION = SLOT_STOP_DURATION + SLOT_STOP_STAGGER * 2 + 80;
export const SLOT_ACTION_ACCEPT_DELAY = 140;
export const SLOT_SERVER_RESULT_PRELUDE = 520;
export const SLOT_RESULT_DELAY =
  SLOT_SPIN_DURATION - SLOT_ACTION_ACCEPT_DELAY - SLOT_SERVER_RESULT_PRELUDE;

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

export function getSlotLaunchDelay(reelIndex: number) {
  return Math.max(0, reelIndex) * SLOT_LAUNCH_STAGGER;
}

export function getSlotSpinOffset(reelIndex: number, elapsedMs: number) {
  const elapsed = Math.max(0, elapsedMs - getSlotLaunchDelay(reelIndex));
  const cycleProgress = (elapsed % SLOT_SPIN_CYCLE_DURATION) / SLOT_SPIN_CYCLE_DURATION;
  return -SLOT_SPIN_CYCLE_ROWS * cycleProgress;
}

export function getSlotStopStart(reelIndex: number, elapsedMs = SLOT_SPIN_DURATION) {
  return getSlotSpinOffset(reelIndex, elapsedMs);
}

export function hasFreeSpins(outcome: SlotOutcome | null) {
  return (outcome?.freeSpinsRemaining ?? 0) > 0;
}
