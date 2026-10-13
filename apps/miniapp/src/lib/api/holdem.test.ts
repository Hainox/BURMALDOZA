import { describe, expect, it } from 'vitest';
import { parseHoldem, createHoldem } from './holdem';
import { ApiClient } from './client';

const waiting = { phase: 'waiting', buy_in: 100, seat: 0, legal_actions: [], wallet_balance: 1000 };
describe('Hold’em boundary', () => {
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
  it('accepts the server card format with full suit names', () => {
    // Так карты приходят из domain (holdem-v1 на production): масть словом.
    const server = {...waiting,phase:'active',stacks:[95,90],street_contributions:[5,10],current_seat:0,pot:15,current_bet:10,minimum_raise:20,community_cards:[{rank:'10',suit:'clubs'}],hole_cards:[{rank:'K',suit:'hearts'},{rank:'A',suit:'spades'}],opponent_cards:[{hidden:true},{hidden:true}]};
    const view = parseHoldem(server);
    expect(view.own).toEqual([{rank:'K',suit:'H'},{rank:'A',suit:'S'}]);
    expect(view.board).toEqual([{rank:'10',suit:'C'}]);
    expect(() => parseHoldem({...server,hole_cards:[{rank:'K',suit:'stars'},{rank:'A',suit:'spades'}]})).toThrow();
  });
});
