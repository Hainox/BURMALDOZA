export type SlotReelPhase =
  | 'spinning'
  | 'stopping-left'
  | 'stopping-center'
  | 'stopping-right'
  | 'settled';

export type SlotReelIndex = 0 | 1 | 2;

export interface SlotReelStopPlan {
  phase: SlotReelPhase;
  reelStopsMs: [number, number, number];
  totalMs: number;
}

export interface SlotTimelineOptions {
  reducedMotion?: boolean;
}

export const SLOT_LAUNCH_OFFSETS_MS = [0, 110, 220] as const;

export const SLOT_SPIN_TRAVEL_MS = 2000;

export const SLOT_STOP_TAILS_MS = [320, 480, 640] as const;

export const SLOT_STOP_EXTRA_MS = [0, 200, 400] as const;

export const SLOT_SETTLE_MS = 300;

export const SLOT_SPIN_CYCLE_MS = 420;

/** Symbols on one reel strip; the track repeats the strip so the window never runs dry. */
export const SLOT_STRIP_LENGTH = 7;

export const SLOT_ACCEL_MS = 260;

/** Nominal cruise speed in symbols per millisecond. */
const SLOT_BASE_VELOCITY = SLOT_STRIP_LENGTH / SLOT_SPIN_CYCLE_MS;

interface SlotReelMotion {
  stopLocalMs: number;
  decelLocalMs: number;
  tailMs: number;
  velocity: number;
  distance: number;
}

export function slotReelLocalMs(elapsedMs: number, reelIndex: SlotReelIndex): number {
  return Math.max(0, elapsedMs - SLOT_LAUNCH_OFFSETS_MS[reelIndex]);
}

export function slotReelDecelStartMs(reelIndex: SlotReelIndex, plan: SlotReelStopPlan): number {
  return plan.reelStopsMs[reelIndex] - SLOT_STOP_TAILS_MS[reelIndex];
}

/**
 * Per-reel kinematics: accelerate linearly, cruise, then ease out with continuous velocity.
 * Cruise speed is nudged per reel so the total travel is a whole number of strips,
 * which lands every reel exactly on the confirmed grid.
 */
function slotReelMotion(reelIndex: SlotReelIndex, plan: SlotReelStopPlan): SlotReelMotion {
  const stopLocalMs = plan.reelStopsMs[reelIndex] - SLOT_LAUNCH_OFFSETS_MS[reelIndex];
  const tailMs = SLOT_STOP_TAILS_MS[reelIndex];
  const decelLocalMs = stopLocalMs - tailMs;
  const travelMs = decelLocalMs - SLOT_ACCEL_MS / 2 + tailMs / 2;
  const strips = Math.max(1, Math.round((SLOT_BASE_VELOCITY * travelMs) / SLOT_STRIP_LENGTH));
  const distance = strips * SLOT_STRIP_LENGTH;
  return { stopLocalMs, decelLocalMs, tailMs, velocity: distance / travelMs, distance };
}

/** Signed reel offset in symbols (negative = track moved up). Unbounded; wrap before painting. */
export function slotReelOffsetAt(
  elapsedMs: number,
  reelIndex: SlotReelIndex,
  plan: SlotReelStopPlan
): number {
  if (plan.totalMs === 0) return 0;
  const local = slotReelLocalMs(elapsedMs, reelIndex);
  if (local <= 0) return 0;
  const { stopLocalMs, decelLocalMs, tailMs, velocity, distance } = slotReelMotion(reelIndex, plan);
  if (local >= stopLocalMs) return -distance;
  if (local <= SLOT_ACCEL_MS) return -(velocity * local * local) / (2 * SLOT_ACCEL_MS);
  const cruise = velocity * (local - SLOT_ACCEL_MS / 2);
  if (local <= decelLocalMs) return -cruise;
  const tail = local - decelLocalMs;
  const cruiseEnd = velocity * (decelLocalMs - SLOT_ACCEL_MS / 2);
  return -(cruiseEnd + velocity * (tail - (tail * tail) / (2 * tailMs)));
}

/** Folds an unbounded offset into one strip: (-SLOT_STRIP_LENGTH, 0]. */
export function wrapSlotReelOffset(offsetSymbols: number): number {
  const folded = ((-offsetSymbols % SLOT_STRIP_LENGTH) + SLOT_STRIP_LENGTH) % SLOT_STRIP_LENGTH;
  return folded === 0 ? 0 : -folded;
}

/** Track translateY in px for the current frame, wrapped so the visible window stays filled. */
export function slotReelTrackShiftPx(
  elapsedMs: number,
  reelIndex: SlotReelIndex,
  plan: SlotReelStopPlan,
  symbolPx: number,
  gapPx: number
): number {
  if (plan.totalMs === 0 || symbolPx <= 0) return 0;
  const wrapped = wrapSlotReelOffset(slotReelOffsetAt(elapsedMs, reelIndex, plan));
  return wrapped * (symbolPx + gapPx);
}

export function slotReelMovingAt(
  elapsedMs: number,
  reelIndex: SlotReelIndex,
  plan: SlotReelStopPlan
): boolean {
  if (plan.totalMs === 0) return false;
  const local = slotReelLocalMs(elapsedMs, reelIndex);
  if (local <= 0) return false;
  const stopLocal = plan.reelStopsMs[reelIndex] - SLOT_LAUNCH_OFFSETS_MS[reelIndex];
  return local < stopLocal;
}

export function planSlotReelStops(options: SlotTimelineOptions = {}): SlotReelStopPlan {
  if (options.reducedMotion) {
    return { phase: 'settled', reelStopsMs: [0, 0, 0], totalMs: 0 };
  }
  const reelStopsMs: [number, number, number] = [
    SLOT_SPIN_TRAVEL_MS + SLOT_STOP_TAILS_MS[0] + SLOT_STOP_EXTRA_MS[0],
    SLOT_SPIN_TRAVEL_MS + SLOT_STOP_TAILS_MS[1] + SLOT_STOP_EXTRA_MS[1],
    SLOT_SPIN_TRAVEL_MS + SLOT_STOP_TAILS_MS[2] + SLOT_STOP_EXTRA_MS[2]
  ];
  return {
    phase: 'spinning',
    reelStopsMs,
    totalMs: reelStopsMs[2] + SLOT_SETTLE_MS
  };
}

export function slotReelPhaseAt(elapsedMs: number, plan: SlotReelStopPlan): SlotReelPhase {
  if (plan.totalMs === 0 || elapsedMs >= plan.totalMs) return 'settled';
  if (elapsedMs >= plan.reelStopsMs[2]) return 'stopping-right';
  if (elapsedMs >= plan.reelStopsMs[1]) return 'stopping-center';
  if (elapsedMs >= plan.reelStopsMs[0]) return 'stopping-left';
  return 'spinning';
}

export function stoppedReelCountAt(elapsedMs: number, plan: SlotReelStopPlan): number {
  return plan.reelStopsMs.filter((stopMs) => elapsedMs >= stopMs).length;
}

export function reelStopDelayMs(reelIndex: SlotReelIndex): number {
  return SLOT_LAUNCH_OFFSETS_MS[reelIndex];
}

export function isSlotSettled(elapsedMs: number, plan: SlotReelStopPlan): boolean {
  return slotReelPhaseAt(elapsedMs, plan) === 'settled';
}
