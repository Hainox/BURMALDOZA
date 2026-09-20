import { describe, expect, it } from 'vitest';
import { reduceMotionState, type MotionEvent, type MotionState } from './motion';

const event = (type: MotionEvent['type']): MotionEvent => ({ type });

describe('motion contract', () => {
  it('walks through the confirmed result choreography', () => {
    let state: MotionState = 'idle';

    state = reduceMotionState(state, event('USER_INTENT'), false);
    state = reduceMotionState(state, event('ACTION_ACCEPTED'), false);
    state = reduceMotionState(state, event('RESULT_CONFIRMED'), false);
    state = reduceMotionState(state, event('SETTLE_COMPLETE'), false);

    expect(state).toBe('settle');
  });

  it('rejects an event that is not legal for the current state', () => {
    expect(reduceMotionState('idle', event('RESULT_CONFIRMED'), false)).toBe('idle');
  });

  it('collapses resolving to settle under reduced motion', () => {
    expect(reduceMotionState('resolving', event('RESULT_CONFIRMED'), true)).toBe('settle');
  });

  it('keeps settlement idempotent and resets on reconnect', () => {
    expect(reduceMotionState('settle', event('SETTLE_COMPLETE'), false)).toBe('settle');
    expect(reduceMotionState('outcome', event('RECONNECTED'), false)).toBe('idle');
  });
});
