import { describe, expect, it } from 'vitest';
import { parseHoldem, createHoldem } from './holdem';
import { ApiClient } from './client';

const waiting = { phase: 'waiting', buy_in: 100, seat: 0, legal_actions: [], wallet_balance: 1000 };
describe('Hold’em boundary', () => {
  it('accepts optional public profiles without identifiers or external URLs', () => {
    expect(parseHoldem(waiting).opponentProfile).toBeNull();
    const avatar_path='/api/v1/rooms/00000000-0000-0000-0000-000000000081/opponent-avatar';
    expect(parseHoldem({...waiting,opponent_profile:{nickname:'@fixture',avatar_path}}).opponentProfile).toEqual({nickname:'@fixture',avatarPath:avatar_path});
    for (const profile of [{nickname:'@fixture',avatar_path:'https://example.org/photo'}, {nickname:'@fixture',avatar_path,telegram_user_id:42}, {nickname:'',avatar_path}]) {
      expect(() => parseHoldem({...waiting,opponent_profile:profile})).toThrow();
    }
  });
  it('fetches avatar bytes with auth header, never auth in the URL', async () => {
    let url='';let headers:HeadersInit | undefined;
    const client=new ApiClient('https://api.example','verified',async (input,init) => {
      url=String(input);headers=init?.headers;
      return new Response(new Uint8Array([255,216,255,217]),{headers:{'Content-Type':'image/jpeg'}});
    });
    expect((await client.getOpponentAvatar('room'))?.size).toBe(4);
    expect(url).toBe('https://api.example/api/v1/rooms/room/opponent-avatar');
    expect(headers).toEqual({'X-Telegram-Init-Data':'verified'});
    const absent=new ApiClient('', 'verified', async () => new Response(null,{status:204}));
    expect(await absent.getOpponentAvatar('room')).toBeNull();
    const bad=new ApiClient('', 'verified', async () => new Response('<svg />',{headers:{'Content-Type':'image/svg+xml'}}));
    await expect(bad.getOpponentAvatar('room')).rejects.toThrow();
  });
  it('requires supported tables, seats, integer balance and server phase', () => {
    for (const invalid of [{buy_in: 200}, {seat: 2}, {wallet_balance: 1.5}, {phase: 'win'}, {legal_actions: ['double']}]) {
      expect(() => parseHoldem({...waiting, ...invalid})).toThrow();
    }
    expect(parseHoldem(waiting).phase).toBe('waiting');
  });
  it('uses the same creation UUID in body and header', async () => {
    let request: RequestInit | undefined;
    const client = new ApiClient('', 'verified', async (_url, init) => {
      request = init;
      return new Response(JSON.stringify({room_id:'room', game_type:'holdem', state_version:1, public_state:waiting}));
    });
    await createHoldem(client, 'pvp', 100, 'same-uuid');
    expect(JSON.parse(String(request?.body))).toEqual({game_type:'holdem', mode:'pvp', buy_in:100, action_id:'same-uuid'});
    expect(request?.headers).toMatchObject({'X-Request-ID':'same-uuid'});
  });
  it('keeps opponent cards hidden until the explicit server showdown flag', () => {
    const active = {...waiting,phase:'active',stacks:[95,90],street_contributions:[5,10],current_seat:0,pot:15,current_bet:10,minimum_raise:20,community_cards:[],hole_cards:[{rank:'A',suit:'S'},{rank:'K',suit:'S'}],opponent_cards:[{rank:'9',suit:'D'},{rank:'9',suit:'H'}]};
    expect(parseHoldem(active).opponent).toEqual([{hidden:true},{hidden:true}]);
    expect(parseHoldem({...active,showdown:true}).opponent).toEqual(active.opponent_cards);
  });
});
