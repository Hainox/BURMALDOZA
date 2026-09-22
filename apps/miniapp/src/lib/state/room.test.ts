import { describe, expect, it } from 'vitest';

import { getResultBalance, RoomState, type RoomResult } from './room.svelte';

const restoredResult: RoomResult = {
  headline: 'Линия подтверждена',
  detail: 'Сервер восстановил последний результат.',
  amount: 20
};

describe('room reconnect state', () => {
  it('restores a server result as already settled', () => {
    const state = new RoomState();

    state.restoreConfirmedResult(restoredResult);

    expect(state.result).toBe(restoredResult);
    expect(state.motion).toBe('settle');
  });

  it('exposes the canonical balance only for a slot result', () => {
    expect(getResultBalance({ slotOutcome: { balance: 1_010 } } as RoomResult)).toBe(1_010);
    expect(getResultBalance({ headline: 'Подтверждено', detail: 'Без баланса' })).toBeNull();
  });
});
