import { describe, expect, it } from 'vitest';

import type { ApiEventEnvelope } from '$lib/api/client';
import { isLiveApiEnabled, mapApiEventResult, mapApiPublicStateResult } from '$lib/api/runtime';

describe('Mini App runtime mode', () => {
  it('uses the live API only when both endpoint and verified init data exist', () => {
    expect(isLiveApiEnabled('https://api.example.test', 'query_id=verified')).toBe(true);
    expect(isLiveApiEnabled('', 'query_id=verified')).toBe(false);
    expect(isLiveApiEnabled('https://api.example.test', '')).toBe(false);
    expect(isLiveApiEnabled('   ', '   ')).toBe(false);
  });

  it('keeps generic non-slot events free of invented payout data', () => {
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

    expect(mapApiEventResult(event, 'holdem')).toEqual({
      headline: 'Действие подтверждено',
      detail: 'Сервер подтвердил действие; клиент показывает только его состояние.'
    });
  });

  it('maps the canonical slot result into the existing reel presentation model', () => {
    const event: ApiEventEnvelope = {
      event_id: '00000000-0000-0000-0000-000000000001',
      room_id: 'room-1',
      state_version: 1,
      type: 'slot.action.accepted',
      ruleset_version: 'slot-skeleton-1',
      server_time: '2026-09-22T00:00:00Z',
      payload: {
        action_id: '00000000-0000-0000-0000-000000000001',
        public_state: {},
        result: {
          grid: [
            ['A', 'A', 'A', 'B', 'B', 'C', 'C'],
            ['A', 'A', 'A', 'B', 'B', 'C', 'C'],
            ['A', 'A', 'A', 'B', 'B', 'C', 'C']
          ],
          reel_stops: [0, 4, 7],
          winning_lines: [
            {
              payline_index: 0,
              rows: [3, 3, 3],
              symbols: ['B', 'B', 'B'],
              match_symbol: 'B',
              matched_columns: 3,
              payout: 20
            }
          ],
          gross_payout: 20,
          net_delta: 10,
          balance_after: 1_010,
          ruleset_version: 'slot-skeleton-1'
        }
      },
      animation_hint: 'slot.reels.stop.staggered'
    };

    expect(mapApiEventResult(event, 'slot')).toEqual({
      headline: 'Линия подтверждена',
      detail: 'Сервер подтвердил сетку и выплату; клиент показывает только движение.',
      amount: 20,
      slotOutcome: {
        reels: event.payload.result && (event.payload.result as Record<string, unknown>).grid,
        winningRows: [3],
        payout: 20,
        balance: 1_010,
        freeSpinsAwarded: 0,
        freeSpinsRemaining: 0,
        reelStops: [0, 4, 7],
        winningLines: [
          {
            paylineIndex: 0,
            rows: [3, 3, 3],
            symbols: ['B', 'B', 'B'],
            matchSymbol: 'B',
            matchedColumns: 3,
            payout: 20
          }
        ]
      }
    });
  });

  it('rejects a slot event without a canonical server result', () => {
    const event: ApiEventEnvelope = {
      event_id: '00000000-0000-0000-0000-000000000001',
      room_id: 'room-1',
      state_version: 1,
      type: 'slot.action.accepted',
      ruleset_version: 'slot-skeleton-1',
      server_time: '2026-09-22T00:00:00Z',
      payload: { action_id: 'action-1', public_state: {} },
      animation_hint: 'slot.reels.stop.staggered'
    };

    expect(() => mapApiEventResult(event, 'slot')).toThrow('canonical slot result');
  });

  it('rebuilds a slot result from the reconnect snapshot last_result', () => {
    const result = mapApiPublicStateResult(
      {
        last_result: {
          grid: [
            ['A', 'A', 'A', 'B', 'B', 'C', 'C'],
            ['A', 'A', 'A', 'B', 'B', 'C', 'C'],
            ['A', 'A', 'A', 'B', 'B', 'C', 'C']
          ],
          reel_stops: [2, 3, 4],
          winning_lines: [],
          gross_payout: 0,
          net_delta: -10,
          balance_after: 990,
          ruleset_version: 'slot-skeleton-1'
        }
      },
      'slot'
    );

    expect(result?.slotOutcome?.reelStops).toEqual([2, 3, 4]);
    expect(result?.slotOutcome?.balance).toBe(990);
  });
});
