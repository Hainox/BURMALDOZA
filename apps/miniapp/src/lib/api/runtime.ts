import type { ApiEventEnvelope } from '$lib/api/client';
import type { GameType, RoomResult } from '$lib/state/room.svelte';

export function isLiveApiEnabled(baseUrl: string, initData: string) {
  return baseUrl.trim().length > 0 && initData.trim().length > 0;
}

export function mapApiEventResult(event: ApiEventEnvelope, _gameType: GameType): RoomResult {
  const serverResult = event.payload.result;
  const result = typeof serverResult === 'object' && serverResult !== null
    ? (serverResult as Record<string, unknown>)
    : undefined;

  return {
    headline: typeof result?.headline === 'string' ? result.headline : 'Действие подтверждено',
    detail:
      typeof result?.detail === 'string'
        ? result.detail
        : 'Сервер подтвердил действие; клиент показывает только его состояние.',
    ...(typeof result?.payout === 'number' ? { amount: result.payout } : {})
  };
}
