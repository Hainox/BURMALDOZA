import { describe, expect, it, vi } from 'vitest';
import { ApiClient } from '$lib/api/client';

const snapshot = { week_start: '2026-10-11T21:00:00Z', week_end: '2026-10-18T21:00:00Z',
  entries: [{ rank: 1, nickname: '@winner', net_result: -50 }] };

describe('weekly leaderboard transport', () => {
  it('authenticates and preserves the signed server result', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(snapshot)));
    const client = new ApiClient('https://api.example.test', 'verified', fetcher);
    expect(await client.getLeaderboard()).toEqual(snapshot);
    expect(fetcher).toHaveBeenCalledWith('https://api.example.test/api/v1/leaderboard',
      expect.objectContaining({ method: 'GET', headers: { 'X-Telegram-Init-Data': 'verified' } }));
  });
  it('accepts the caller own place outside the top', async () => {
    const withMe = { ...snapshot, me: { rank: 18, nickname: '@visitor', net_result: -25 } };
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(withMe)));
    expect(await new ApiClient('', 'verified', fetcher).getLeaderboard()).toEqual(withMe);
  });
  it.each([
    { ...snapshot, me: { rank: 3, nickname: '@visitor', net_result: 5 } },
    { ...snapshot, me: { rank: 18, nickname: '@visitor', net_result: 5, telegram_user_id: 1 } },
    { ...snapshot, entries: [{ rank: 1, nickname: '@winner', net_result: '50' }] },
    { ...snapshot, entries: Array.from({ length: 16 }, (_, index) => ({ rank: index + 1, nickname: 'a', net_result: 5 })) },
    { ...snapshot, week_start: 'invalid' },
    { ...snapshot, entries: [{ ...snapshot.entries[0], telegram_user_id: 123 }] },
    { ...snapshot, entries: [{ ...snapshot.entries[0], rank: 2 }] }
  ])('rejects malformed data at the transport boundary', async (payload) => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(payload)));
    await expect(new ApiClient('', 'verified', fetcher).getLeaderboard()).rejects.toThrow('Некорректный ответ рейтинга');
  });
});
