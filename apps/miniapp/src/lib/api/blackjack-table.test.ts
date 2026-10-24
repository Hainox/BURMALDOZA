import { describe, it, expect } from 'vitest';
import { parseBlackjackTable, createBlackjackTable, joinBlackjackTable, resolveBlackjackTableAction } from './blackjack-table';
import { ApiClient } from './client';
const player = { seat: 0, nickname: '@fixture', cards: [], total: null, bet: 25, status: 'waiting', ready: true, outcome: null };
const fixture = { phase: 'lobby', capacity: 3, viewer_seat: 0, host_seat: 0, active_seat: null, players: [player], dealer_cards: [], dealer_total: null, legal_actions: ['start','unready','leave'], wallet_balance: 1000, turn_deadline: null, round_id: null };
describe('shared blackjack boundary', () => {
  it('accepts lobby and all three server hands with hidden dealer', () => {
    expect(parseBlackjackTable(fixture).hostSeat).toBe(0);
    const v = parseBlackjackTable({ ...fixture, phase: 'active', players: [0,1,2].map(seat => ({ ...player, seat, cards: [{rank:'A',suit:'spades'},{rank:'5',suit:'hearts'}], total: 16, status: 'playing' })), active_seat: 1, dealer_cards: [{rank:'K',suit:'clubs'},{hidden:true}], legal_actions: ['leave'] });
    expect(v.players).toHaveLength(3); expect(v.dealer[1]).toEqual({hidden:true});
  });
  it('rejects wrong phase, duplicate seats, impossible turn and hidden dealer total', () => {
    for (const p of [{phase:'demo'},{players:[player,player]},{active_seat:2},{dealer_cards:[{hidden:true}],dealer_total:21},{wallet_balance:1.2},{players:[{...player,user_id:42}]}]) expect(() => parseBlackjackTable({...fixture,...p})).toThrow();
  });
  it('create and join carry the same durable UUID in body/header', async () => {
    const requests: RequestInit[] = [];
    const c = new ApiClient('', 'verified', async (_,init) => { requests.push(init!); return new Response(JSON.stringify({room_id:'r',game_type:'blackjack',ruleset_version:'blackjack-gfl-table-1',state_version:1,public_state:fixture})); });
    await createBlackjackTable(c,'first'); await joinBlackjackTable(c,'room','second');
    expect(JSON.parse(String(requests[0].body))).toEqual({game_type:'blackjack',mode:'table',action_id:'first'});
    expect(JSON.parse(String(requests[1].body))).toEqual({action_id:'second'}); expect(requests[1].headers).toMatchObject({'X-Request-ID':'second'});
  });
  it('handles a leave receipt without parsing it as a table snapshot', () => {
    const snapshot = {roomId:'room',gameType:'blackjack' as const,title:'Blackjack',rulesetVersion:'blackjack-gfl-table-1',stateVersion:5,publicState:fixture};
    const event = {room_id:'room',event_id:'request',state_version:6,payload:{action_id:'request',public_state:{phase:'left',legal_actions:[]}}};
    expect(resolveBlackjackTableAction(snapshot,event,'request','leave')).toBeNull();
    expect(() => resolveBlackjackTableAction(snapshot,{...event,event_id:'other'},'request','leave')).toThrow();
    expect(() => resolveBlackjackTableAction(snapshot,{...event,room_id:'other'},'request','leave')).toThrow();
    expect(() => resolveBlackjackTableAction(snapshot,event,'request','hit')).toThrow();
  });
});
it('validates a replayed leave receipt with the saved room identity and no readable snapshot',()=>{const event={room_id:'room',event_id:'request',state_version:6,payload:{action_id:'request',public_state:{phase:'left',legal_actions:[]}}};expect(resolveBlackjackTableAction(null,event,'request','leave','room')).toBeNull();expect(()=>resolveBlackjackTableAction(null,event,'request','leave','other')).toThrow();});
