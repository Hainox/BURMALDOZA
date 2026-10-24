import { mapRoomSnapshot, type ApiClient, type ApiRoomSnapshot } from './client';
import { cards, deadline, integer, legal, nickname, record, seat } from './table-boundary';
import type { HoldemCard } from './holdem';
import type { RoomSnapshot } from '$lib/state/room.svelte';

export interface BlackjackTablePlayer {
  seat: number; nickname: string; cards: HoldemCard[]; total: number | null;
  bet: number; status: string; ready: boolean;
  outcome: { result: string; payout: number; net: number } | null;
}
export interface BlackjackTableView {
  phase: 'lobby' | 'active' | 'settled' | 'closed'; hostSeat: number | null;
  viewerSeat: number; activeSeat: number | null; players: BlackjackTablePlayer[];
  dealer: HoldemCard[]; dealerTotal: number | null; legal: string[];
  deadline: string | null; balance: number | null; roundId: string | null;
}
export function parseBlackjackTable(p: Record<string, unknown>): BlackjackTableView {
  if (!['lobby','active','settled','closed'].includes(String(p.phase)) || p.capacity !== 3) throw new Error('Неизвестный общий стол Blackjack');
  if (!Array.isArray(p.players) || p.players.length > 3 || (p.phase !== 'closed' && !p.players.length)) throw new Error('Некорректный состав Blackjack');
  const players = p.players.map(value => {
    const a = record(value);
    if (['user_id','telegram_user_id','display_name','wallet_balance'].some(key => key in a) || typeof a.ready !== 'boolean' || !['waiting','playing','finished','leaving'].includes(String(a.status))) throw new Error('Некорректный игрок Blackjack');
    let outcome: BlackjackTablePlayer['outcome'] = null;
    if (a.outcome != null) {
      const o = record(a.outcome);
      if (!['blackjack','win','push','loss'].includes(String(o.result))) throw new Error('Некорректный итог Blackjack');
      outcome = { result: String(o.result), payout: integer(o.payout), net: integer(o.net_delta, -Number.MAX_SAFE_INTEGER) };
    }
    return { seat: seat(a.seat, 2), nickname: nickname(a.nickname), cards: cards(a.cards), total: a.total == null ? null : integer(a.total, 0, 100), bet: integer(a.bet ?? 0, 0, 2000000), status: String(a.status), ready: a.ready, outcome };
  });
  const ids = players.map(player => player.seat);
  if (new Set(ids).size !== ids.length) throw new Error('Повтор места Blackjack');
  const viewerSeat = seat(p.viewer_seat, 2);
  if (p.phase !== 'closed' && !ids.includes(viewerSeat)) throw new Error('Нет своего места Blackjack');
  const nullableSeat = (value: unknown) => {
    if (value == null) return null;
    const s = seat(value, 2);
    if (!ids.includes(s)) throw new Error('Неизвестное место Blackjack');
    return s;
  };
  const dealer = cards(p.dealer_cards ?? record(p.dealer ?? {}).cards ?? []);
  const dealerTotal = p.dealer_total == null ? null : integer(p.dealer_total, 0, 100);
  if (dealer.some(card => 'hidden' in card) && dealerTotal !== null) throw new Error('Скрытый дилер раскрывает сумму');
  return { phase: p.phase as BlackjackTableView['phase'], hostSeat: nullableSeat(p.host_seat), viewerSeat, activeSeat: nullableSeat(p.active_seat), players, dealer, dealerTotal, legal: legal(p.legal_actions, ['ready','unready','start','hit','stand','double','leave']), deadline: deadline(p.turn_deadline), balance: p.wallet_balance == null ? null : integer(p.wallet_balance), roundId: p.round_id == null ? null : String(p.round_id) };
}
export async function createBlackjackTable(client: ApiClient, actionId: string) {
  const raw = await client.post<ApiRoomSnapshot>('/api/v1/rooms', { game_type: 'blackjack', mode: 'table', action_id: actionId }, actionId);
  const snapshot = mapRoomSnapshot(raw); parseBlackjackTable(snapshot.publicState); return snapshot;
}
export async function joinBlackjackTable(client: ApiClient, roomId: string, actionId: string) {
  const raw = await client.post<ApiRoomSnapshot>(`/api/v1/rooms/${encodeURIComponent(roomId)}/join`, { action_id: actionId }, actionId);
  const snapshot = mapRoomSnapshot(raw); parseBlackjackTable(snapshot.publicState); return snapshot;
}
/** A successful leave is a receipt, not a table snapshot available to a former member. */
export function resolveBlackjackTableAction(snapshot: RoomSnapshot, event: unknown, actionId: string, action: string): RoomSnapshot | null {
  const envelope = record(event); const payload = record(envelope.payload); const publicState = record(payload.public_state);
  if (envelope.room_id !== snapshot.roomId || envelope.event_id !== actionId || payload.action_id !== actionId) throw new Error('Ответ относится к другому запросу');
  const stateVersion = integer(envelope.state_version);
  if (action === 'leave') {
    if (publicState.phase !== 'left' || !Array.isArray(publicState.legal_actions) || publicState.legal_actions.length) throw new Error('Выход не подтверждён сервером');
    return null;
  }
  parseBlackjackTable(publicState);
  return { ...snapshot, stateVersion, publicState };
}
