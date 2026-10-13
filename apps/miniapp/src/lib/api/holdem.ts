import type { ApiClient, ApiRoomSnapshot } from './client';
import { mapRoomSnapshot } from './client';
import type { RoomSnapshot } from '$lib/state/room.svelte';

export type HoldemMode = 'bot' | 'pvp';
export type HoldemCard = { rank: string; suit: string } | { hidden: true };
export interface HoldemView {
  phase: 'waiting' | 'active' | 'settled' | 'cancelled';
  buyIn: number; seat: number; heroCode: string | null; street: string;
  pot: number; stacks: number[]; contributions: number[]; currentSeat: number;
  legal: string[]; minimumRaise: number; maximumRaise: number; call: number;
  board: HoldemCard[]; own: HoldemCard[]; opponent: HoldemCard[];
  deadline: string | null; balance: number | null;
  result: { winners: number[]; payout: number; net: number; outcome: string } | null;
}
const actions = ['fold', 'check', 'call', 'raise'];
function integer(value: unknown): number {
  if (!Number.isSafeInteger(value) || (value as number) < 0) throw new Error('Некорректное число Hold’em');
  return value as number;
}
function pair(value: unknown): number[] {
  if (!Array.isArray(value) || value.length !== 2) throw new Error('Некорректные места Hold’em');
  return value.map(integer);
}
function cards(value: unknown, count: number | null): HoldemCard[] {
  if (!Array.isArray(value) || (count !== null && value.length !== count) || value.length > 5) throw new Error('Некорректные карты Hold’em');
  return value.map(card => {
    if (typeof card !== 'object' || !card) throw new Error('Некорректная карта Hold’em');
    if (card.hidden === true) return { hidden: true };
    if (!['2','3','4','5','6','7','8','9','10','J','Q','K','A'].includes(card.rank) || !['S','H','D','C'].includes(card.suit)) throw new Error('Некорректная карта Hold’em');
    return { rank: card.rank, suit: card.suit };
  });
}
export function parseHoldem(p: Record<string, unknown>): HoldemView {
  if (!['waiting', 'active', 'settled', 'cancelled'].includes(String(p.phase))) throw new Error('Некорректная фаза Hold’em');
  const phase = p.phase as HoldemView['phase'];
  const buyIn = integer(p.buy_in);
  if (![100, 500, 1000].includes(buyIn)) throw new Error('Неизвестный стол Hold’em');
  const seat = integer(p.seat);
  if (seat > 1) throw new Error('Некорректное место Hold’em');
  const playing = phase === 'active' || phase === 'settled';
  const stacks = playing ? pair(p.stacks) : [buyIn, buyIn];
  const contributions = playing ? pair(p.street_contributions) : [0, 0];
  if (!Array.isArray(p.legal_actions) || p.legal_actions.some(a => !actions.includes(a))) throw new Error('Некорректные действия Hold’em');
  const deadline = p.turn_deadline ?? p.search_deadline ?? null;
  if (deadline !== null && (typeof deadline !== 'string' || !Number.isFinite(Date.parse(deadline)))) throw new Error('Некорректный срок Hold’em');
  let result: HoldemView['result'] = null;
  if (phase === 'settled') {
    const r = p.last_result as Record<string, unknown> | undefined;
    if (!r || !Array.isArray(r.winner_seats) || r.winner_seats.length < 1 || r.winner_seats.some(s => s !== 0 && s !== 1) || !Array.isArray(r.net_deltas) || r.net_deltas.length !== 2 || !r.net_deltas.every(Number.isSafeInteger) || !['fold','showdown'].includes(String(r.outcome))) throw new Error('Некорректный итог Hold’em');
    result = { winners: r.winner_seats, payout: pair(r.payouts)[seat], net: r.net_deltas[seat] as number, outcome: r.outcome as string };
  }
  return {
    phase, buyIn, seat, stacks, contributions,
    heroCode: typeof p.hero_code === 'string' ? p.hero_code : null,
    street: typeof p.game_phase === 'string' ? p.game_phase : '',
    currentSeat: playing ? integer(p.current_seat) : 0,
    pot: playing ? integer(p.pot) : 0, legal: p.legal_actions as string[],
    minimumRaise: playing ? integer(p.minimum_raise) : 0,
    maximumRaise: contributions[seat] + stacks[seat],
    call: playing ? integer(p.current_bet) - contributions[seat] : 0,
    board: playing ? cards(p.community_cards, null) : [],
    own: playing ? cards(p.hole_cards, 2) : [],
    opponent: playing && p.showdown === true ? cards(p.opponent_cards, 2) : [{ hidden: true }, { hidden: true }],
    deadline: deadline as string | null,
    balance: p.wallet_balance == null ? null : integer(p.wallet_balance), result
  };
}
export async function createHoldem(client: ApiClient, mode: HoldemMode, buyIn: number, actionId: string): Promise<RoomSnapshot> {
  const raw = await client.post<ApiRoomSnapshot>('/api/v1/rooms', { game_type: 'holdem', mode, buy_in: buyIn, action_id: actionId }, actionId);
  const snapshot = mapRoomSnapshot(raw);
  parseHoldem(snapshot.publicState);
  return snapshot;
}
