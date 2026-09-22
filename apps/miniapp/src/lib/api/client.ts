import { getTelegramWebApp } from '$lib/telegram/webapp';
import type { GameType, RoomSnapshot } from '$lib/state/room.svelte';

export interface ApiRoomSnapshot {
  room_id: string;
  game_type: GameType;
  mode: string;
  status: string;
  ruleset_version: string;
  state_version: number;
  public_state: Record<string, unknown>;
}

export interface ApiEventEnvelope {
  event_id: string;
  room_id: string;
  state_version: number;
  type: string;
  ruleset_version: string;
  server_time: string;
  payload: Record<string, unknown>;
  animation_hint: string;
}

export interface ApiActionResponse {
  event: ApiEventEnvelope;
}

export interface ApiWalletSnapshot {
  user_id: number;
  balance: number;
  currency_code: string;
  version: number;
}

export interface ApiCurrentUser {
  user_id: number;
  telegram_user_id: number;
  display_name: string;
  username?: string | null;
}

type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export interface RoomEventSocket {
  addEventListener(type: string, listener: (event: Event | MessageEvent) => void): void;
  send(data: string): void;
  close(): void;
}

type SocketFactory = (url: string) => RoomEventSocket;

const roomTitles: Record<GameType, string> = {
  slot: 'Однорукий бандит',
  blackjack: 'Blackjack',
  holdem: 'Hold’em'
};

export function mapRoomSnapshot(snapshot: ApiRoomSnapshot): RoomSnapshot {
  return {
    roomId: snapshot.room_id,
    gameType: snapshot.game_type,
    title: roomTitles[snapshot.game_type],
    rulesetVersion: snapshot.ruleset_version,
    stateVersion: snapshot.state_version,
    publicState: snapshot.public_state
  };
}

export function buildRoomEventUrl(baseUrl: string, roomId: string) {
  const fallbackOrigin = typeof window === 'undefined' ? 'http://localhost' : window.location.origin;
  const url = new URL(`/api/v1/rooms/${encodeURIComponent(roomId)}/events`, baseUrl || fallbackOrigin);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  return url.toString();
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly body?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export class ApiClient {
  private readonly baseUrl: string;

  constructor(
    baseUrl = '',
    private readonly initData = getTelegramWebApp().initData,
    private readonly fetcher: Fetcher = globalThis.fetch.bind(globalThis),
    private readonly socketFactory: SocketFactory = (url) => new WebSocket(url)
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  async get<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'GET' });
  }

  async post<T>(path: string, body: unknown, actionId?: string): Promise<T> {
    return this.request<T>(path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(actionId ? { 'X-Request-ID': actionId } : {})
      },
      body: JSON.stringify(body)
    });
  }

  async createRoom(gameType: GameType, mode: string): Promise<RoomSnapshot> {
    const snapshot = await this.post<ApiRoomSnapshot>('/api/v1/rooms', { game_type: gameType, mode });
    return mapRoomSnapshot(snapshot);
  }

  async getRoom(roomId: string): Promise<RoomSnapshot> {
    const snapshot = await this.get<ApiRoomSnapshot>(`/api/v1/rooms/${encodeURIComponent(roomId)}`);
    return mapRoomSnapshot(snapshot);
  }

  async applyAction(
    roomId: string,
    expectedStateVersion: number,
    actionId: string,
    payload: Record<string, unknown>
  ): Promise<ApiActionResponse> {
    return this.post<ApiActionResponse>(
      `/api/v1/rooms/${encodeURIComponent(roomId)}/actions`,
      { action_id: actionId, expected_state_version: expectedStateVersion, payload },
      actionId
    );
  }

  async getWallet(): Promise<ApiWalletSnapshot> {
    return this.get<ApiWalletSnapshot>('/api/v1/wallet');
  }

  async getCurrentUser(): Promise<ApiCurrentUser> {
    return this.get<ApiCurrentUser>('/api/v1/me');
  }

  subscribeToRoom(
    roomId: string,
    onSnapshot: (snapshot: RoomSnapshot) => void,
    onEvent: (event: ApiEventEnvelope) => void
  ) {
    const socket = this.socketFactory(buildRoomEventUrl(this.baseUrl, roomId));
    socket.addEventListener('open', () => {
      socket.send(JSON.stringify({ type: 'auth', init_data: this.initData }));
    });
    socket.addEventListener('message', (message) => {
      let payload: unknown;
      try {
        payload = JSON.parse(String((message as MessageEvent).data));
      } catch {
        return;
      }
      if (typeof payload !== 'object' || payload === null) return;
      const envelope = payload as { type?: unknown; snapshot?: ApiRoomSnapshot; event?: ApiEventEnvelope };
      if (envelope.type === 'snapshot' && envelope.snapshot) onSnapshot(mapRoomSnapshot(envelope.snapshot));
      if (envelope.type === 'event' && envelope.event) onEvent(envelope.event);
    });
    return () => socket.close();
  }

  private async request<T>(path: string, init: RequestInit): Promise<T> {
    const response = await this.fetcher(`${this.baseUrl}${path}`, {
      ...init,
      headers: {
        'X-Telegram-Init-Data': this.initData,
        ...init.headers
      }
    });
    const body = await response.json().catch(() => undefined);
    if (!response.ok) {
      throw new ApiError(response.status, `API request failed with ${response.status}`, body);
    }
    return body as T;
  }
}
