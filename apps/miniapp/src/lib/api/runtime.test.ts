import { describe, expect, it } from 'vitest';

import type { ApiEventEnvelope } from '$lib/api/client';
import {
  buildRoomActionPayload,
  isLiveApiEnabled,
  mapApiEventResult,
  mapApiPublicStateResult
} from '$lib/api/runtime';
import { getResultBalance } from '$lib/state/room.svelte';

describe('Mini App runtime mode', () => {
  it('builds the explicit default stakes for live spin and deal actions', () => {
    expect(buildRoomActionPayload('spin')).toEqual({ action: 'spin', bet: 10 });
    expect(buildRoomActionPayload('deal')).toEqual({ action: 'deal', bet: 25 });
    expect(buildRoomActionPayload('deal', { bet: 50 })).toEqual({ action: 'deal', bet: 50 });
    expect(buildRoomActionPayload('hit')).toEqual({ action: 'hit' });
  });

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

  it('maps the canonical blackjack settlement and restores it after reconnect', () => {
    const canonical = {
      outcome: 'win',
      player_total: 21,
      dealer_total: 18,
      gross_payout: 50,
      net_delta: 25,
      balance_after: 1_025,
      ruleset_version: 'blackjack-gfl-skeleton-1',
      final_bet: 25
    };
    const event: ApiEventEnvelope = {
      event_id: '00000000-0000-0000-0000-000000000002',
      room_id: 'room-blackjack',
      state_version: 2,
      type: 'blackjack.action.accepted',
      ruleset_version: 'blackjack-gfl-skeleton-1',
      server_time: '2026-09-23T00:00:00Z',
      payload: {
        action_id: '00000000-0000-0000-0000-000000000002',
        public_state: { game_phase: 'dealer_resolution' },
        result: canonical
      },
      animation_hint: 'blackjack.cards.deal.staged'
    };

    const eventResult = mapApiEventResult(event, 'blackjack');
    const reconnectResult = mapApiPublicStateResult({ last_result: canonical }, 'blackjack');

    if (!eventResult) throw new Error('expected a settled blackjack result');
    expect(eventResult.blackjackOutcome).toEqual({
      outcome: 'win',
      playerTotal: 21,
      dealerTotal: 18,
      grossPayout: 50,
      netDelta: 25,
      balanceAfter: 1_025,
      rulesetVersion: 'blackjack-gfl-skeleton-1',
      finalBet: 25
    });
    expect(eventResult.amount).toBe(50);
    expect(reconnectResult).toEqual(eventResult);
    expect(getResultBalance(eventResult)).toBe(1_025);
  });

  it('does not fabricate a blackjack payout while a hand is still active', () => {
    const event: ApiEventEnvelope = {
      event_id: '00000000-0000-0000-0000-000000000003',
      room_id: 'room-blackjack',
      state_version: 1,
      type: 'blackjack.action.accepted',
      ruleset_version: 'blackjack-gfl-skeleton-1',
      server_time: '2026-09-23T00:00:00Z',
      payload: {
        action_id: '00000000-0000-0000-0000-000000000003',
        public_state: { game_phase: 'player_turn', wallet_balance: 975 }
      },
      animation_hint: 'blackjack.cards.deal.staged'
    };

    expect(mapApiEventResult(event, 'blackjack')).toBeNull();
  });
});
