export const SLOT_REEL_COUNT = 3;
export const SLOT_ROW_COUNT = 7;
export const SLOT_REEL_COPIES = 3;
export const SLOT_FINAL_OFFSET_ROWS = SLOT_ROW_COUNT * SLOT_REEL_COPIES;

export const SLOT_ACTION_ACCEPT_DELAY = 140;
export const SLOT_SERVER_RESULT_PRELUDE = 520;
export const SLOT_LAUNCH_DURATION = 280;
export const SLOT_LAUNCH_STAGGER = 110;
export const SLOT_RAMP_DURATION = 260;
export const SLOT_TRAVEL_DURATION = 2_000;
export const SLOT_LANDING_TAILS = [320, 480, 640] as const;
export const SLOT_LANDING_DURATION = SLOT_LANDING_TAILS[0];
export const SLOT_SETTLE_DURATION = 300;
export const SLOT_REEL_TRAVEL_DURATION = SLOT_TRAVEL_DURATION + SLOT_LANDING_TAILS[0];
export const SLOT_TOTAL_DURATION = SLOT_TRAVEL_DURATION + SLOT_LANDING_TAILS[2] + SLOT_SETTLE_DURATION;
export const SLOT_SPIN_DURATION = SLOT_TOTAL_DURATION;

export type SlotPhase =
  | 'idle'
  | 'spinning'
  | 'stopping-left'
  | 'stopping-center'
  | 'stopping-right'
  | 'settled';

export type SlotReelPhase = 'idle' | 'travel' | 'landing' | 'landed';

export interface SlotWinningLine {
  paylineIndex: number;
  rows: number[];
  symbols: string[];
  matchSymbol: string;
  matchedColumns: number;
  payout: number;
}

export interface SlotOutcome {
  reels: string[][];
  winningRows: number[];
  payout: number;
  balance: number;
  freeSpinsAwarded: number;
  freeSpinsRemaining: number;
  reelStops?: number[];
  winningLines?: SlotWinningLine[];
}

export function buildReelTrack(baseSymbols: string[], confirmedSymbols: string[], copies = SLOT_REEL_COPIES) {
  return [...Array.from({ length: copies }, () => baseSymbols).flat(), ...confirmedSymbols];
}

function clamp(value: number, minimum = 0, maximum = 1) {
  return Math.min(maximum, Math.max(minimum, value));
}

export function getSlotLaunchDelay(reelIndex: number) {
  return Math.max(0, reelIndex) * SLOT_LAUNCH_STAGGER;
}

export function getSlotStopDelay(reelIndex: number) {
  const normalizedIndex = Math.min(SLOT_REEL_COUNT - 1, Math.max(0, reelIndex));
  return normalizedIndex === 0
    ? 0
    : SLOT_LANDING_TAILS[normalizedIndex] - SLOT_LANDING_TAILS[0];
}

export function getSlotStopStart(reelIndex: number) {
  return SLOT_TRAVEL_DURATION + getSlotStopDelay(reelIndex);
}

export function getSlotStopEnd(reelIndex: number) {
  return getSlotStopStart(reelIndex) + SLOT_LANDING_DURATION;
}

export function getSlotReelCruiseVelocityRowsPerMs(reelIndex: number) {
  const cruiseWindow =
    getSlotStopStart(reelIndex) - getSlotLaunchDelay(reelIndex) - SLOT_RAMP_DURATION;
  return SLOT_FINAL_OFFSET_ROWS / (SLOT_RAMP_DURATION / 2 + cruiseWindow + SLOT_LANDING_DURATION / 3);
}

export function getSlotReelVelocityRowsPerMs(
  reelIndex: number,
  elapsedMs: number,
  reducedMotion = false
) {
  if (reducedMotion || elapsedMs >= getSlotStopEnd(reelIndex)) return 0;
  const launchDelay = getSlotLaunchDelay(reelIndex);
  const localMs = elapsedMs - launchDelay;
  if (localMs <= 0) return 0;
  const cruiseVelocity = getSlotReelCruiseVelocityRowsPerMs(reelIndex);
  if (localMs < SLOT_RAMP_DURATION) return (cruiseVelocity * localMs) / SLOT_RAMP_DURATION;
  const landingStart = getSlotStopStart(reelIndex);
  if (elapsedMs < landingStart) return cruiseVelocity;
  const landingProgress = clamp((elapsedMs - landingStart) / SLOT_LANDING_DURATION);
  return cruiseVelocity * (1 - landingProgress) ** 2;
}

export function getSlotPhase(elapsedMs: number, reducedMotion = false): SlotPhase {
  if (reducedMotion || elapsedMs >= SLOT_TOTAL_DURATION) return 'settled';
  if (elapsedMs < SLOT_TRAVEL_DURATION) return 'spinning';
  if (elapsedMs < getSlotStopStart(1)) return 'stopping-left';
  if (elapsedMs < getSlotStopStart(2)) return 'stopping-center';
  return 'stopping-right';
}

export function getSlotReelPhase(
  reelIndex: number,
  elapsedMs: number,
  reducedMotion = false
): SlotReelPhase {
  if (reducedMotion || elapsedMs >= SLOT_TOTAL_DURATION || elapsedMs >= getSlotStopEnd(reelIndex)) {
    return 'landed';
  }
  return elapsedMs < getSlotStopStart(reelIndex) ? 'travel' : 'landing';
}

export function getSlotReelOffsetRows(
  reelIndex: number,
  elapsedMs: number,
  reducedMotion = false
) {
  const finalOffset = -SLOT_FINAL_OFFSET_ROWS;
  if (reducedMotion || elapsedMs >= getSlotStopEnd(reelIndex)) return finalOffset;

  const launchDelay = getSlotLaunchDelay(reelIndex);
  const localMs = elapsedMs - launchDelay;
  if (localMs <= 0) return 0;

  const cruiseVelocity = getSlotReelCruiseVelocityRowsPerMs(reelIndex);
  const landingStart = getSlotStopStart(reelIndex);

  if (localMs < SLOT_RAMP_DURATION) {
    return -(0.5 * cruiseVelocity * localMs * localMs) / SLOT_RAMP_DURATION;
  }

  const rampDistance = (cruiseVelocity * SLOT_RAMP_DURATION) / 2;

  if (elapsedMs < landingStart) {
    return -(rampDistance + cruiseVelocity * (localMs - SLOT_RAMP_DURATION));
  }

  const travelledBeforeLanding = rampDistance + cruiseVelocity * (landingStart - launchDelay - SLOT_RAMP_DURATION);
  const landingProgress = clamp((elapsedMs - landingStart) / SLOT_LANDING_DURATION);
  const landingDistance = cruiseVelocity * SLOT_LANDING_DURATION * (landingProgress - landingProgress ** 2 + landingProgress ** 3 / 3);
  return -(travelledBeforeLanding + landingDistance);
}

export function hasFreeSpins(outcome: SlotOutcome | null) {
  return (outcome?.freeSpinsRemaining ?? 0) > 0;
}
