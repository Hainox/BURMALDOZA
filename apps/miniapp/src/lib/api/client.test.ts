import { describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api/client';

class FakeRoomSocket {
  readonly sent: string[] = [];
  closed = false;
  private listeners = new Map<string, ((event: Event | MessageEvent) => void)[]>();

  addEventListener(type: string, listener: (event: Event | MessageEvent) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.closed = true;
  }

  emit(type: string, event: Event | MessageEvent = new Event(type)) {
    for (const listener of this.listeners.get(type) ?? []) listener(event);
  }
}

const roomPayload = {
  room_id: 'room-1',
  game_type: 'slot',
  mode: 'solo',
  status: 'waiting',
  ruleset_version: 'slot-skeleton-1',
  state_version: 0,
  public_state: { phase: 'waiting', legal_actions: ['spin'] }
};

describe('ApiClient room transport', () => {
  it('creates a room with Telegram init data and maps the server snapshot', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(roomPayload), { status: 200 })
    );
    const client = new ApiClient('https://api.example.test', 'query_id=verified', fetcher);

    const snapshot = await client.createRoom('slot', 'solo');

    expect(snapshot).toEqual({
      roomId: 'room-1',
      gameType: 'slot',
      title: 'Однорукий бандит',
      rulesetVersion: 'slot-skeleton-1',
      stateVersion: 0,
      publicState: { phase: 'waiting', legal_actions: ['spin'] }
    });
    expect(fetcher).toHaveBeenCalledWith(
      'https://api.example.test/api/v1/rooms',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'X-Telegram-Init-Data': 'query_id=verified',
          'Content-Type': 'application/json'
        })
      })
    );
  });

  it('sends the expected state version and idempotency key for an action', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          event: {
            event_id: '00000000-0000-0000-0000-000000000001',
            room_id: 'room-1',
            state_version: 1,
            type: 'slot.action.accepted',
            ruleset_version: 'slot-skeleton-1',
            server_time: '2026-09-22T00:00:00Z',
            payload: {
              action_id: '00000000-0000-0000-0000-000000000001',
              public_state: { phase: 'active' }
            },
            animation_hint: 'slot.reels.stop.staggered'
          }
        }
      ))
    );
    const client = new ApiClient('https://api.example.test', 'verified', fetcher);

    const actionId = '00000000-0000-0000-0000-000000000001';
    const response = await client.applyAction('room-1', 0, actionId, { action: 'spin', bet: 10 });

    expect(response.event.state_version).toBe(1);
    expect(fetcher).toHaveBeenCalledWith(
      'https://api.example.test/api/v1/rooms/room-1/actions',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'X-Telegram-Init-Data': 'verified',
          'X-Request-ID': actionId
        }),
        body: JSON.stringify({
          action_id: actionId,
          expected_state_version: 0,
          payload: { action: 'spin', bet: 10 }
        })
      })
    );
  });

  it('claims wallet faucets with the idempotency request ID', async () => {
    const fetcher = vi.fn<typeof fetch>().mockImplementation(
      async () => new Response(JSON.stringify({ balance_after: 1250, delta: 250 }))
    );
    const client = new ApiClient('https://api.example.test', 'verified', fetcher);
    const requestId = '00000000-0000-0000-0000-000000000002';

    const daily = await client.claimDailyBonus(requestId);
    await client.claimReliefGrant(requestId);

    expect(daily.balance_after).toBe(1250);
    for (const path of ['daily-bonus', 'relief']) {
      expect(fetcher).toHaveBeenCalledWith(
        `https://api.example.test/api/v1/wallet/${path}/claim`,
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'X-Telegram-Init-Data': 'verified',
            'X-Request-ID': requestId
          })
        })
      );
    }
  });

  it('surfaces API status and response body for failed requests', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'state conflict' }), { status: 409 })
    );
    const client = new ApiClient('', 'verified', fetcher);

    await expect(client.getRoom('room-1')).rejects.toMatchObject({
      name: 'ApiError',
      status: 409,
      body: { detail: 'state conflict' }
    });
  });

  it('authenticates a room event stream and maps snapshot/event messages', () => {
    const socket = new FakeRoomSocket();
    const fetcher = vi.fn<typeof fetch>();
    const client = new ApiClient(
      'https://api.example.test',
      'verified',
      fetcher,
      () => socket
    );
    const onSnapshot = vi.fn();
    const onEvent = vi.fn();

    const close = client.subscribeToRoom('room-1', onSnapshot, onEvent);
    socket.emit('open');
    socket.emit(
      'message',
      new MessageEvent('message', {
        data: JSON.stringify({ type: 'snapshot', snapshot: roomPayload })
      })
    );
    socket.emit(
      'message',
      new MessageEvent('message', {
        data: JSON.stringify({ type: 'event', event: { state_version: 1 } })
      })
    );

    expect(socket.sent).toEqual([JSON.stringify({ type: 'auth', init_data: 'verified' })]);
    expect(onSnapshot).toHaveBeenCalledWith(expect.objectContaining({ roomId: 'room-1' }));
    expect(onEvent).toHaveBeenCalledWith({ state_version: 1 });
    close();
    expect(socket.closed).toBe(true);
  });
});
