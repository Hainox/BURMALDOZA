import { reduceMotionState, type MotionEvent, type MotionState } from '$lib/game/motion';
import type { SlotOutcome } from '$lib/game/slot';

export type GameType = 'slot' | 'blackjack' | 'holdem';

export interface RoomSnapshot {
  roomId: string;
  gameType: GameType;
  title: string;
  rulesetVersion: string;
  stateVersion: number;
  publicState: Record<string, unknown>;
}

export interface RoomResult {
  headline: string;
  detail: string;
  amount?: number;
  slotOutcome?: SlotOutcome;
}

export class RoomState {
  snapshot = $state<RoomSnapshot | null>(null);
  motion = $state<MotionState>('idle');
  result = $state<RoomResult | null>(null);

  setSnapshot(snapshot: RoomSnapshot, reconnected = false) {
    this.snapshot = snapshot;
    if (reconnected) this.motion = reduceMotionState(this.motion, { type: 'RECONNECTED' }, false);
  }

  transition(event: MotionEvent, reducedMotion: boolean) {
    this.motion = reduceMotionState(this.motion, event, reducedMotion);
  }

  setResult(result: RoomResult | null) {
    this.result = result;
  }

  restoreConfirmedResult(result: RoomResult) {
    this.result = result;
    this.motion = 'settle';
  }

  reset() {
    this.motion = reduceMotionState(this.motion, { type: 'NAVIGATED' }, false);
    this.result = null;
  }
}
