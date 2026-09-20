export type MotionState = 'idle' | 'primed' | 'resolving' | 'outcome' | 'settle';

export type MotionEvent =
  | { type: 'USER_INTENT' }
  | { type: 'ACTION_ACCEPTED' }
  | { type: 'RESULT_CONFIRMED' }
  | { type: 'SETTLE_COMPLETE' }
  | { type: 'RECONNECTED' }
  | { type: 'NAVIGATED' };

const transitions: Partial<Record<MotionState, Partial<Record<MotionEvent['type'], MotionState>>>> = {
  idle: { USER_INTENT: 'primed' },
  primed: { ACTION_ACCEPTED: 'resolving' },
  resolving: { RESULT_CONFIRMED: 'outcome' },
  outcome: { SETTLE_COMPLETE: 'settle' },
  settle: { USER_INTENT: 'primed', SETTLE_COMPLETE: 'settle' }
};

export function reduceMotionState(
  current: MotionState,
  event: MotionEvent,
  reducedMotion: boolean
): MotionState {
  if (event.type === 'RECONNECTED' || event.type === 'NAVIGATED') {
    return 'idle';
  }

  if (reducedMotion && (event.type === 'RESULT_CONFIRMED' || event.type === 'ACTION_ACCEPTED')) {
    if (current === 'resolving' || current === 'primed') return 'settle';
  }

  return transitions[current]?.[event.type] ?? current;
}

export function motionDuration(state: MotionState, reducedMotion: boolean): number {
  if (reducedMotion || state === 'idle' || state === 'settle') return 0;
  return {
    primed: 140,
    resolving: 480,
    outcome: 360
  }[state];
}
