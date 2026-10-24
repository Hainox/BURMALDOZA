import { describe, it, expect } from 'vitest';
import { parseHoldemTable, createHoldemTable, payableHoldemCall } from './holdem-table';
import { ApiClient } from './client';
const cards = [{rank:'A',suit:'spades'},{rank:'K',suit:'hearts'}];
const players = [0,2,5].map(seat => ({seat,stack:90,committed:10,street_committed:10,folded:false,all_in:false,nickname:`@seat${seat}`,cards:seat===0?cards:[{hidden:true},{hidden:true}]}));
const fixture = {phase:'active',capacity:6,buy_in:100,viewer_seat:0,players,game_phase:'pre_flop',current_seat:0,button_seat:0,small_blind_seat:2,big_blind_seat:5,pot:30,current_bet:10,last_full_raise_size:10,legal_actions:['fold','check','raise'],min_raise_to:20,max_raise_to:100,to_call:0,community_cards:[],hole_cards:cards,turn_deadline:'2026-10-22T20:00:00Z',wallet_balance:900,revealed_seats:[]};
describe('six-player Holdem boundary', () => {
  it('preserves physical sparse seats and authoritative bounds', () => {
    const v=parseHoldemTable(fixture); expect(v.players.map(p=>p.seat)).toEqual([0,2,5]); expect(v.own[0]).toEqual({rank:'A',suit:'S'}); expect(v.minimumRaise).toBe(20); expect(v.currentSeat).toBe(0);
  });
  it('rejects duplicate seats, absent current seat, unsafe sums and external avatar paths', () => {
    for (const p of [{players:[players[0],players[0]]},{current_seat:1},{pot:Number.MAX_SAFE_INTEGER+1},{players:[{...players[0],avatar_path:'https://evil.invalid/avatar'},...players.slice(1)]},{legal_actions:['double']},{min_raise_to:null}]) expect(()=>parseHoldemTable({...fixture,...p})).toThrow();
  });
  it('distinguishes separate bank winners and validates result maps', () => {
    const last_result={outcome:'showdown',pots:[{amount:60,eligible_seats:[0,2,5],winner_seats:[5],shares:{5:60}},{amount:80,eligible_seats:[0,2],winner_seats:[2],shares:{2:80}}],refunds:{0:40,2:0,5:0},cashouts:{0:40,2:80,5:60},net_deltas:{0:-60,2:-20,5:-40}};
    const v=parseHoldemTable({...fixture,phase:'settled',current_seat:null,legal_actions:[],min_raise_to:null,last_result}); expect(v.result?.pots[0].winners).toEqual([5]); expect(v.result?.pots[1].winners).toEqual([2]); expect(v.result?.refunds['0']).toBe(40);
    expect(()=>parseHoldemTable({...fixture,phase:'settled',current_seat:null,legal_actions:[],min_raise_to:null,last_result:{...last_result,cashouts:{0:40,2:80,4:60}}})).toThrow();
  });
  it('explicitly opts in only new PvP creates and preserves request identity', async () => {
    let request:RequestInit|undefined;
    const c=new ApiClient('','verified',async(_,init)=>{request=init;return new Response(JSON.stringify({room_id:'r',game_type:'holdem',ruleset_version:'holdem-six-1',state_version:1,public_state:fixture}));});
    await createHoldemTable(c,100,'uuid'); expect(JSON.parse(String(request?.body))).toEqual({game_type:'holdem',mode:'pvp',buy_in:100,table_capacity:6,action_id:'uuid'}); expect(request?.headers).toMatchObject({'X-Request-ID':'uuid'});
  });
  it('loads a seat avatar with auth and rejects an invalid seat before fetch', async () => {
    let url='';let headers:HeadersInit|undefined;
    const c=new ApiClient('https://api.example','verified',async(input,init)=>{url=String(input);headers=init?.headers;return new Response(new Uint8Array([255,216,255,217]),{headers:{'Content-Type':'image/jpeg'}});});
    expect((await c.getPlayerAvatar('room',5))?.size).toBe(4);expect(url).toBe('https://api.example/api/v1/rooms/room/players/5/avatar');expect(headers).toEqual({'X-Telegram-Init-Data':'verified'});await expect(c.getPlayerAvatar('room',6)).rejects.toThrow();
  });
  it('accepts departed cancellation without reassigning a physical seat',()=>{const v=parseHoldemTable({phase:'cancelled',capacity:6,buy_in:100,players:[],viewer_seat:null,legal_actions:[],search_deadline:null,turn_deadline:null});expect(v.phase).toBe('cancelled');expect(v.players).toEqual([]);});
  it('accepts sparse refunds but never a refund for a foreign seat',()=>{
    const last_result={outcome:'fold',pots:[{amount:20,eligible_seats:[0],winner_seats:[0],shares:{0:20}}],refunds:{0:10},cashouts:{0:110,2:90,5:100},net_deltas:{0:10,2:-10,5:0}};
    expect(parseHoldemTable({...fixture,phase:'settled',current_seat:null,legal_actions:[],min_raise_to:null,last_result}).result?.refunds).toEqual({0:10,2:0,5:0});expect(()=>parseHoldemTable({...fixture,phase:'settled',current_seat:null,legal_actions:[],min_raise_to:null,last_result:{...last_result,refunds:{1:10}}})).toThrow();
  });
  it('rejects malformed active card counts and controls for another turn',()=>{for(const p of [{hole_cards:[]},{players:players.map(v=>({...v,cards:[]}))},{current_seat:2,legal_actions:['check']},{community_cards:[{hidden:true}]}])expect(()=>parseHoldemTable({...fixture,...p})).toThrow();});
  it('shows only the callable stack for a short all-in',()=>{const v=parseHoldemTable({...fixture,players:players.map(p=>p.seat===0?{...p,stack:7}:p),to_call:40,legal_actions:['call','fold'],min_raise_to:null});expect(payableHoldemCall(v)).toEqual({amount:7,allIn:true});expect(payableHoldemCall({...v,call:5})).toEqual({amount:5,allIn:false});});
});
