import { mapRoomSnapshot, type ApiClient, type ApiRoomSnapshot } from './client';
import { cards, deadline, integer, legal, nickname, record, seat, seatMap } from './table-boundary';
import type { HoldemCard } from './holdem';
export interface HoldemTablePlayer { seat: number; stack: number; committed: number; contribution: number; folded: boolean; allIn: boolean; nickname: string; cards: HoldemCard[]; avatarPath: string | null; }
export interface TablePot { amount: number; eligible: number[]; winners: number[]; shares: Record<string, number>; }
export interface HoldemTableView {
  phase: 'waiting' | 'active' | 'settled' | 'cancelled'; buyIn: number; viewerSeat: number; players: HoldemTablePlayer[];
  street: string; currentSeat: number | null; buttonSeat: number | null; smallBlindSeat: number | null; bigBlindSeat: number | null;
  pot: number; legal: string[]; minimumRaise: number | null; maximumRaise: number; call: number; board: HoldemCard[]; own: HoldemCard[];
  deadline: string | null; balance: number | null;
  result: { pots: TablePot[]; refunds: Record<string, number>; cashouts: Record<string, number>; netDeltas: Record<string, number>; outcome: string } | null;
}
export function parseHoldemTable(p: Record<string, unknown>): HoldemTableView {
  if (!['waiting','active','settled','cancelled'].includes(String(p.phase)) || p.capacity !== 6) throw new Error('Неизвестный стол Hold’em');
  const phase = p.phase as HoldemTableView['phase']; const playing = phase === 'active' || phase === 'settled'; const buyIn = integer(p.buy_in);
  if (![100,500,1000].includes(buyIn)) throw new Error('Неизвестный вход');
  if (!Array.isArray(p.players) || p.players.length > 6 || p.players.length < (playing ? 2 : phase === 'cancelled' ? 0 : 1)) throw new Error('Некорректный состав стола');
  const players = p.players.map(value => {
    const a = record(value); const s = seat(a.seat, 5);
    if (['user_id','telegram_user_id','display_name','wallet_balance'].some(key => key in a)) throw new Error('Недопустимые данные игрока');
    const path = a.avatar_path ?? null;
    if (path !== null && (typeof path !== 'string' || !new RegExp(`^/api/v1/rooms/[0-9a-f-]{36}/players/${s}/avatar$`).test(path))) throw new Error('Некорректный аватар');
    if (typeof a.folded !== 'boolean' || typeof a.all_in !== 'boolean') throw new Error('Некорректный статус места');
    return { seat: s, stack: integer(a.stack), committed: integer(a.committed), contribution: integer(a.street_committed), folded: a.folded, allIn: a.all_in, nickname: nickname(a.nickname), cards: cards(a.cards ?? [], 2), avatarPath: path as string | null };
  });
  const ids = players.map(player => player.seat);
  if (new Set(ids).size !== ids.length) throw new Error('Повтор места');
  const viewerSeat = phase === 'cancelled' && p.viewer_seat == null ? -1 : seat(p.viewer_seat ?? p.seat, 5);
  if (phase !== 'cancelled' && !ids.includes(viewerSeat)) throw new Error('Нет своего места');
  const nullableSeat = (value: unknown) => {
    if (value == null) return null; const s = seat(value, 5);
    if (!ids.includes(s)) throw new Error('Неизвестное место'); return s;
  };
  const currentSeat = nullableSeat(p.current_seat);
  if (phase === 'active' && currentSeat === null) throw new Error('Нет текущего хода');
  const board = cards(p.community_cards ?? [], 5); const own = cards(p.hole_cards ?? [], 2);
  if (board.some(card => 'hidden' in card) || (playing && (own.length !== 2 || own.some(card => 'hidden' in card) || players.some(player => player.cards.length !== 2)))) throw new Error('Неполные карты стола');
  const actions = legal(p.legal_actions, ['fold','check','call','raise','cancel']);
  if (phase === 'active' && currentSeat !== viewerSeat && actions.some(action => action !== 'cancel')) throw new Error('Действия чужого хода');
  const minimumRaise = p.min_raise_to == null ? null : integer(p.min_raise_to, 1);
  if (actions.includes('raise') && minimumRaise === null) throw new Error('Нет границы рейза');
  const maximumRaise = integer(p.max_raise_to ?? 0);
  if (actions.includes('raise') && maximumRaise < 1) throw new Error('Нет доступного рейза');
  let result: HoldemTableView['result'] = null;
  if (phase === 'settled') {
    const r = record(p.last_result);
    if (!['fold','showdown'].includes(String(r.outcome)) || !Array.isArray(r.pots)) throw new Error('Некорректный итог');
    const pots = r.pots.map(value => {
      const b = record(value);
      if (!Array.isArray(b.eligible_seats) || !Array.isArray(b.winner_seats) || !b.winner_seats.length) throw new Error('Некорректный банк');
      const eligible = b.eligible_seats.map(s => seat(s, 5)); const winners = b.winner_seats.map(s => seat(s, 5));
      if (eligible.some(s => !ids.includes(s)) || winners.some(s => !eligible.includes(s))) throw new Error('Чужое место в банке');
      const amount = integer(b.amount); const shares = seatMap(b.shares, winners);
      if (Object.values(shares).reduce((a,b) => a+b, 0) !== amount) throw new Error('Неверное деление банка');
      return { amount, eligible, winners, shares };
    });
    const refundsRaw = record(r.refunds);
    if (Object.keys(refundsRaw).some(s => !ids.map(String).includes(s))) throw new Error('Чужой возврат');
    const refunds = seatMap({ ...Object.fromEntries(ids.map(s => [s, 0])), ...refundsRaw }, ids);
    result = { pots, refunds, cashouts: seatMap(r.cashouts, ids), netDeltas: seatMap(r.net_deltas, ids, true), outcome: String(r.outcome) };
  }
  return { phase, buyIn, viewerSeat, players, street: typeof p.game_phase === 'string' ? p.game_phase : '', currentSeat, buttonSeat: nullableSeat(p.button_seat), smallBlindSeat: nullableSeat(p.small_blind_seat), bigBlindSeat: nullableSeat(p.big_blind_seat), pot: integer(p.pot ?? 0), legal: actions, minimumRaise, maximumRaise, call: integer(p.to_call ?? 0), board, own, deadline: deadline(p.turn_deadline ?? p.search_deadline), balance: p.wallet_balance == null ? null : integer(p.wallet_balance), result };
}
export async function createHoldemTable(client: ApiClient, buyIn: number, actionId: string) {
  const raw = await client.post<ApiRoomSnapshot>('/api/v1/rooms', { game_type: 'holdem', mode: 'pvp', buy_in: buyIn, table_capacity: 6, action_id: actionId }, actionId);
  const snapshot = mapRoomSnapshot(raw);
  if (snapshot.rulesetVersion !== 'holdem-six-1') throw new Error('Сервер не поддерживает стол на шестерых');
  parseHoldemTable(snapshot.publicState); return snapshot;
}
export function payableHoldemCall(view: HoldemTableView): { amount: number; allIn: boolean } {
  const stack = view.players.find(player => player.seat === view.viewerSeat)?.stack ?? 0;
  return { amount: Math.min(view.call, stack), allIn: view.call > 0 && stack <= view.call };
}
