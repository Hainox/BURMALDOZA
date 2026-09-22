import type { ApiEventEnvelope } from '$lib/api/client';
import type { SlotOutcome, SlotWinningLine } from '$lib/game/slot';
import type { GameType, RoomResult } from '$lib/state/room.svelte';

export class ApiResultError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ApiResultError';
  }
}

export function isLiveApiEnabled(baseUrl: string, initData: string) {
  return baseUrl.trim().length > 0 && initData.trim().length > 0;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function numberField(result: Record<string, unknown>, key: string) {
  const value = result[key];
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new ApiResultError(`canonical slot result is missing numeric ${key}`);
  }
  return value;
}

function parseSlotOutcome(value: unknown): SlotOutcome {
  if (!isRecord(value)) throw new ApiResultError('canonical slot result is missing');

  const rawGrid = value.grid;
  if (
    !Array.isArray(rawGrid) ||
    rawGrid.length !== 3 ||
    rawGrid.some((column) => !Array.isArray(column) || column.length !== 7 || column.some((symbol) => typeof symbol !== 'string'))
  ) {
    throw new ApiResultError('canonical slot result has an invalid grid');
  }

  const rawStops = value.reel_stops;
  if (
    !Array.isArray(rawStops) ||
    rawStops.length !== 3 ||
    rawStops.some((stop) => typeof stop !== 'number' || !Number.isInteger(stop) || stop < 0)
  ) {
    throw new ApiResultError('canonical slot result has invalid reel stops');
  }

  const rawLines = value.winning_lines;
  if (!Array.isArray(rawLines)) {
    throw new ApiResultError('canonical slot result is missing winning lines');
  }

  const winningLines: SlotWinningLine[] = rawLines.map((rawLine) => {
    if (!isRecord(rawLine) || !Array.isArray(rawLine.rows) || rawLine.rows.length !== 3) {
      throw new ApiResultError('canonical slot result has an invalid winning line');
    }
    if (
      rawLine.rows.some((row) => typeof row !== 'number' || !Number.isInteger(row) || row < 0 || row >= 7) ||
      !Array.isArray(rawLine.symbols) ||
      rawLine.symbols.some((symbol) => typeof symbol !== 'string') ||
      typeof rawLine.match_symbol !== 'string'
    ) {
      throw new ApiResultError('canonical slot result has an invalid winning line');
    }
    return {
      paylineIndex: numberField(rawLine, 'payline_index'),
      rows: [...rawLine.rows] as number[],
      symbols: [...rawLine.symbols] as string[],
      matchSymbol: rawLine.match_symbol,
      matchedColumns: numberField(rawLine, 'matched_columns'),
      payout: numberField(rawLine, 'payout')
    };
  });

  const grossPayout = numberField(value, 'gross_payout');
  const balanceAfter = numberField(value, 'balance_after');
  numberField(value, 'net_delta');

  return {
    reels: rawGrid.map((column) => [...column] as string[]),
    winningRows: [...new Set(winningLines.flatMap((line) => line.rows))],
    payout: grossPayout,
    balance: balanceAfter,
    freeSpinsAwarded: 0,
    freeSpinsRemaining: 0,
    reelStops: [...rawStops] as number[],
    winningLines
  };
}

function mapResultValue(serverResult: unknown, gameType: GameType): RoomResult {
  const result = isRecord(serverResult) ? serverResult : undefined;
  if (gameType === 'slot') {
    const slotOutcome = parseSlotOutcome(result);
    return {
      headline: slotOutcome.payout > 0 ? 'Линия подтверждена' : 'Вращение подтверждено',
      detail: 'Сервер подтвердил сетку и выплату; клиент показывает только движение.',
      amount: slotOutcome.payout,
      slotOutcome
    };
  }

  return {
    headline: typeof result?.headline === 'string' ? result.headline : 'Действие подтверждено',
    detail:
      typeof result?.detail === 'string'
        ? result.detail
        : 'Сервер подтвердил действие; клиент показывает только его состояние.',
      ...(typeof result?.payout === 'number' ? { amount: result.payout } : {})
  };
}

export function mapApiEventResult(event: ApiEventEnvelope, gameType: GameType): RoomResult {
  return mapResultValue(event.payload.result, gameType);
}

export function mapApiPublicStateResult(
  publicState: Record<string, unknown>,
  gameType: GameType
): RoomResult | null {
  if (!('last_result' in publicState)) return null;
  return mapResultValue(publicState.last_result, gameType);
}
