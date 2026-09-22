import { describe, expect, it } from 'vitest';

import type { ApiEventEnvelope } from '$lib/api/client';
import { isLiveApiEnabled, mapApiEventResult } from '$lib/api/runtime';

describe('Mini App runtime mode', () => {
  it('uses the live API only when both endpoint and verified init data exist', () => {
    expect(isLiveApiEnabled('https://api.example.test', 'query_id=verified')).toBe(true);
    expect(isLiveApiEnabled('', 'query_id=verified')).toBe(false);
    expect(isLiveApiEnabled('https://api.example.test', '')).toBe(false);
    expect(isLiveApiEnabled('   ', '   ')).toBe(false);
  });

  it('turns a confirmed server event into a room result without inventing a payout', () => {
    const event: ApiEventEnvelope = {
      event_id: '00000000-0000-0000-0000-000000000001',
      room_id: 'room-1',
      state_version: 1,
      type: 'slot.action.accepted',
      ruleset_version: 'slot-skeleton-1',
      server_time: '2026-09-22T00:00:00Z',
      payload: {
        action_id: '00000000-0000-0000-0000-000000000001',
        public_state: { last_action: 'spin' }
      },
      animation_hint: 'slot.reels.stop.staggered'
    };

    expect(mapApiEventResult(event, 'slot')).toEqual({
      headline: 'Действие подтверждено',
      detail: 'Сервер подтвердил действие; клиент показывает только его состояние.'
    });
  });
});
