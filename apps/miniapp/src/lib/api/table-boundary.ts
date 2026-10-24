import type { HoldemCard } from './holdem';

export function record(value: unknown): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new Error('Некорректные данные стола');
  return value as Record<string, unknown>;
}
export function integer(value: unknown, min = 0, max = Number.MAX_SAFE_INTEGER): number {
  if (!Number.isSafeInteger(value) || (value as number) < min || (value as number) > max) throw new Error('Некорректное число стола');
  return value as number;
}
export function seat(value: unknown, max: number): number { return integer(value, 0, max); }
export function deadline(value: unknown): string | null {
  if (value == null) return null;
  if (typeof value !== 'string' || !Number.isFinite(Date.parse(value))) throw new Error('Некорректный срок стола');
  return value;
}
const suits: Record<string, string> = { spades: 'S', hearts: 'H', diamonds: 'D', clubs: 'C' };
export function cards(value: unknown, max = 12): HoldemCard[] {
  if (!Array.isArray(value) || value.length > max) throw new Error('Некорректные карты стола');
  return value.map(card => {
    const p = record(card);
    if (p.hidden === true) {
      if (Object.keys(p).some(key => key !== 'hidden')) throw new Error('Закрытая карта содержит данные');
      return { hidden: true };
    }
    const suit = suits[String(p.suit)] ?? p.suit;
    if (!['2','3','4','5','6','7','8','9','10','J','Q','K','A'].includes(String(p.rank)) || !['S','H','D','C'].includes(String(suit))) throw new Error('Некорректная карта стола');
    return { rank: p.rank as string, suit: suit as string };
  });
}
export function nickname(value: unknown): string {
  if (value == null) return 'Игрок без ника';
  if (typeof value !== 'string' || !value || value.length > 256) throw new Error('Некорректный ник');
  return value;
}
export function legal(value: unknown, allowed: string[]): string[] {
  if (!Array.isArray(value) || value.some(action => typeof action !== 'string' || !allowed.includes(action)) || new Set(value).size !== value.length) throw new Error('Некорректные действия стола');
  return value as string[];
}
export function seatMap(value: unknown, seats: number[], signed = false): Record<string, number> {
  const p = record(value);
  if (Object.keys(p).length !== seats.length || seats.some(s => !(String(s) in p))) throw new Error('Некорректный расчёт мест');
  return Object.fromEntries(Object.entries(p).map(([s, n]) => [s, integer(n, signed ? -Number.MAX_SAFE_INTEGER : 0)]));
}
