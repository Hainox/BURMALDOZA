export const SLOT_REEL_COUNT = 3;
export const SLOT_ROW_COUNT = 7;
export const SLOT_REEL_COPIES = 3;
export const SLOT_SPIN_DURATION = 2_400;
export const SLOT_SPIN_CYCLE_DURATION = 840;
export const SLOT_LAUNCH_DURATION = 280;
export const SLOT_LAUNCH_STAGGER = 110;
export const SLOT_STOP_DURATION = 680;
export const SLOT_STOP_STAGGER = 170;
export const SLOT_REVEAL_DURATION = SLOT_STOP_DURATION + SLOT_STOP_STAGGER * 2 + 60;

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

export function getSlotStopStart(reelIndex: number) {
  const elapsed = Math.max(0, SLOT_SPIN_DURATION - getSlotLaunchDelay(reelIndex));
  const cycleProgress = (elapsed % SLOT_SPIN_CYCLE_DURATION) / SLOT_SPIN_CYCLE_DURATION;
  return -(SLOT_ROW_COUNT * SLOT_REEL_COPIES) * cycleProgress;
}

export function hasFreeSpins(outcome: SlotOutcome | null) {
  return (outcome?.freeSpinsRemaining ?? 0) > 0;
}
