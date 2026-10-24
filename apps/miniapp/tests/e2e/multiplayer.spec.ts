import { test, expect, type Page } from '@playwright/test';
import { openRoom } from './helpers';
const room = '00000000-0000-0000-0000-000000000126';
async function auth(page: Page) {
  await page.addInitScript(() => { (window as unknown as {Telegram:unknown}).Telegram={WebApp:{initData:'query_id=verified-test',ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){}}}; });
  await page.route('**/api/v1/wallet', r => r.fulfill({json:{balance:1000,currency_code:'JOKERGEM',version:1}}));
  await page.route('**/api/v1/wallet/ledger', r => r.fulfill({json:[]}));
  await page.route('**/api/v1/leaderboard', r => r.fulfill({json:{week_start:'2026-10-19T00:00:00Z',week_end:'2026-10-26T00:00:00Z',entries:[]}}));
  await page.routeWebSocket('**/events', () => {});
}
const ownCards = [{rank:'A',suit:'spades'},{rank:'K',suit:'hearts'}];
function activePoker() {
  return {phase:'active',capacity:6,buy_in:100,viewer_seat:0,
    players:Array.from({length:6},(_,seat)=>({seat,stack:90,committed:10,street_committed:10,folded:false,all_in:false,nickname:`@player${seat}`,cards:seat===0?ownCards:[{hidden:true},{hidden:true}],avatar_path:`/api/v1/rooms/${room}/players/${seat}/avatar`})),
    game_phase:'pre_flop',current_seat:0,button_seat:0,small_blind_seat:1,big_blind_seat:2,pot:60,current_bet:10,last_full_raise_size:10,legal_actions:['fold','check','raise'],min_raise_to:20,max_raise_to:100,to_call:0,
    hole_cards:ownCards,community_cards:[],turn_deadline:new Date(Date.now()+20000).toISOString(),wallet_balance:900};
}
for (const width of [320,390,1440]) test(`six seats, private hands, server bounds, avatars and restore at ${width}px`, async ({page}) => {
  await auth(page); await page.setViewportSize({width,height:900}); await page.emulateMedia({reducedMotion:'reduce'});
  let version=1;
  let p:Record<string,unknown>={phase:'waiting',capacity:6,buy_in:100,viewer_seat:0,players:[{seat:0,stack:100,committed:0,street_committed:0,folded:false,all_in:false,nickname:'@own',cards:[],avatar_path:`/api/v1/rooms/${room}/players/0/avatar`},{seat:1,stack:100,committed:0,street_committed:0,folded:false,all_in:false,nickname:'@old_occupant',cards:[],avatar_path:`/api/v1/rooms/${room}/players/1/avatar`}],legal_actions:['cancel'],search_deadline:new Date(Date.now()+60000).toISOString(),wallet_balance:1000};
  const snapshot=()=>({room_id:room,game_type:'holdem',mode:'pvp',status:p.phase,ruleset_version:'holdem-six-1',state_version:version,public_state:p});
  let avatarRequests=0;
  await page.route(`**/api/v1/rooms/${room}/players/*/avatar`,async r=>{avatarRequests++;expect(r.request().headers()['x-telegram-init-data']).toBe('query_id=verified-test');await r.fulfill({contentType:'image/png',path:'tests/e2e/fixtures/opponent-avatar.png'});});
  await page.route('**/api/v1/rooms', async r=>{const body=r.request().postDataJSON();expect(body.table_capacity).toBe(6);expect(body.mode).toBe('pvp');await r.fulfill({json:snapshot()});});
  await page.route(`**/api/v1/rooms/${room}`, r=>r.fulfill({json:snapshot()}));
  await page.route(`**/api/v1/rooms/${room}/actions`, async r=>{
    const body=r.request().postDataJSON();expect(body.action_id).toBe(r.request().headers()['x-request-id']);version++;
    p={...p,phase:'settled',current_seat:null,legal_actions:[],min_raise_to:null,turn_deadline:null,last_result:{outcome:'fold',pots:[{amount:60,eligible_seats:[0],winner_seats:[0],shares:{0:60}}],refunds:{0:20},cashouts:{0:150,1:90,2:90,3:90,4:90,5:90},net_deltas:{0:50,1:-10,2:-10,3:-10,4:-10,5:-10}}};
    await r.fulfill({json:{event:{state_version:version,payload:{public_state:p}}}});
  });
  await page.goto('/');await openRoom(page,'holdem');await page.getByLabel('Живой игрок').check();await page.getByTestId('holdem-start').click();await expect(page.getByText('Собираем общий стол')).toBeVisible();
  await page.waitForTimeout(300);expect(avatarRequests).toBe(0);
  // The old waiting occupant left; the immutable active roster owns seat1 now.
  version++;p=activePoker();
  await expect(page.getByTestId('holdem-multiplayer')).toBeVisible({timeout:7000});
  for(let seat=0;seat<6;seat++)await expect(page.getByTestId(`holdem-seat-${seat}`)).toBeVisible();
  await expect(page.getByLabel('Закрытая карта')).toHaveCount(10);await expect(page.getByTestId('holdem-timer')).toContainText('Ваш ход');
  await expect.poll(()=>avatarRequests).toBe(5);
  await page.getByLabel('Сумма рейза').fill('101');await expect(page.getByTestId('holdem-raise')).toBeDisabled();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.reload();await openRoom(page,'holdem');await expect(page.getByTestId('holdem-multiplayer')).toBeVisible();
  await page.getByTestId('holdem-check').click();await expect(page.getByTestId('holdem-result')).toContainText('+50 JG');await expect(page.getByTestId('holdem-result')).toContainText('Непокрытая ставка');
  await page.screenshot({path:`test-results/poker-six-${width}.png`,fullPage:true});
});
test('short stack call displays the actual all-in amount',async({page})=>{
  await auth(page);let p:Record<string,unknown>=activePoker();p={...p,players:activePoker().players.map(player=>player.seat===0?{...player,stack:7}:player),to_call:40,legal_actions:['call','fold'],min_raise_to:null};
  const snapshot=()=>({room_id:room,game_type:'holdem',mode:'pvp',ruleset_version:'holdem-six-1',state_version:1,public_state:p});
  await page.route('**/api/v1/rooms',r=>r.fulfill({json:snapshot()}));await page.route(`**/api/v1/rooms/${room}`,r=>r.fulfill({json:snapshot()}));await page.route('**/avatar',r=>r.fulfill({status:204}));
  await page.goto('/');await openRoom(page,'holdem');await page.getByLabel('Живой игрок').check();await page.getByTestId('holdem-start').click();
  await expect(page.getByTestId('holdem-call')).toContainText('ва-банк');await expect(page.getByTestId('holdem-call')).toContainText('7 JG');await expect(page.getByTestId('holdem-call')).not.toContainText('40 JG');
});
test('blackjack three clients ready, start, turns, results, next readiness and fourth refusal', async ({browser})=>{
  const contexts=await Promise.all(Array.from({length:4},()=>browser.newContext({viewport:{width:390,height:900},reducedMotion:'reduce'})));
  const pages=await Promise.all(contexts.map(context=>context.newPage()));
  let version=1;let phase='lobby';let players:Array<Record<string,unknown>>=[];let active:number|null=null;
  const publicState=(seat:number)=>({phase,capacity:3,viewer_seat:seat,host_seat:0,active_seat:active,players:players.map(player=>({...player,nickname:`@player${player.seat}`})),dealer_cards:phase==='lobby'?[]:phase==='active'?[{rank:'K',suit:'clubs'},{hidden:true}]:[{rank:'K',suit:'clubs'},{rank:'8',suit:'hearts'}],dealer_total:phase==='settled'?18:null,legal_actions:phase==='lobby'||phase==='settled'?['leave',players[seat]?.ready?'unready':'ready',...(seat===0&&players.every(player=>player.ready)?['start']:[])]:['leave',...(active===seat?['hit','stand','double']:[])],wallet_balance:phase==='lobby'?1000:975,turn_deadline:phase==='active'?new Date(Date.now()+20000).toISOString():null,round_id:phase==='lobby'?null:room});
  const snapshot=(seat:number)=>({room_id:room,game_type:'blackjack',mode:'table',status:phase,ruleset_version:'blackjack-gfl-table-1',state_version:version,public_state:publicState(seat)});
  for(let seat=0;seat<4;seat++){
    const page=pages[seat];await auth(page);
    await page.route('**/api/v1/rooms',async r=>{
      const body=r.request().postDataJSON();
      if(body.mode==='solo'){await r.fulfill({json:{room_id:'solo',game_type:'blackjack',ruleset_version:'blackjack-skeleton-1',state_version:0,public_state:{phase:'waiting',legal_actions:['deal'],wallet_balance:1000}}});return;}
      players.push({seat:0,cards:[],total:null,bet:0,status:'waiting',ready:false,outcome:null});await r.fulfill({json:snapshot(0)});
    });
    await page.route('**/api/v1/rooms/solo',r=>r.fulfill({json:{room_id:'solo',game_type:'blackjack',ruleset_version:'blackjack-skeleton-1',state_version:0,public_state:{phase:'waiting',legal_actions:['deal']}}}));
    await page.route(`**/api/v1/rooms/${room}`,r=>r.fulfill({json:snapshot(seat)}));
    await page.route(`**/api/v1/rooms/${room}/join`,async r=>{
      if(seat===3){await r.fulfill({status:409,json:{detail:'table full'}});return;}
      players.push({seat,cards:[],total:null,bet:0,status:'waiting',ready:false,outcome:null});version++;await r.fulfill({json:snapshot(seat)});
    });
    await page.route(`**/api/v1/rooms/${room}/actions`,async r=>{
      const body=r.request().postDataJSON();const name=body.payload.action;version++;
      if(name==='ready')players[seat]={...players[seat],ready:true,bet:body.payload.bet};
      if(name==='start'){phase='active';active=0;players=players.map(player=>({...player,ready:false,status:'playing',cards:[{rank:'10',suit:'spades'},{rank:'7',suit:'hearts'}],total:17}));}
      if(name==='stand'){players[seat]={...players[seat],status:'finished'};active=seat<2?seat+1:null;if(active===null){phase='settled';players=players.map(player=>({...player,outcome:{result:'loss',payout:0,net_delta:-25}}));}}
      const state=name==='leave'?{phase:'left',legal_actions:[]}:publicState(seat);
      await r.fulfill({json:{event:{room_id:room,event_id:body.action_id,state_version:version,payload:{action_id:body.action_id,public_state:state}}}});
    });
    await page.goto('/');await openRoom(page,'blackjack');await page.getByRole('button',{name:'Общий стол · до 3',exact:true}).click();
    if(seat===0)await page.getByTestId('blackjack-table-create').click();else{await page.getByLabel('Код стола',{exact:true}).fill(room);await page.getByRole('button',{name:'Войти по коду'}).click();}
    if(seat<3)await expect(page.getByTestId(`blackjack-seat-${seat}`)).toBeVisible();
  }
  await expect(pages[3].getByText('Стол изменился или действие недоступно. Состояние обновлено.')).toBeVisible();
  for(let seat=0;seat<3;seat++)await pages[seat].getByTestId('blackjack-table-ready').click();
  await expect(pages[0].getByTestId('blackjack-table-start')).toBeVisible({timeout:7000});await pages[0].getByTestId('blackjack-table-start').click();await expect(pages[0].getByLabel('Закрытая карта')).toHaveCount(1);
  for(let seat=0;seat<3;seat++){await expect(pages[seat].getByTestId('blackjack-table-stand')).toBeVisible({timeout:7000});await pages[seat].getByTestId('blackjack-table-stand').click();}
  for(let seat=0;seat<3;seat++){await expect(pages[seat].getByTestId(`blackjack-result-${seat}`)).toContainText('Поражение',{timeout:7000});await expect(pages[seat].getByTestId('blackjack-table-ready')).toBeVisible();expect(await pages[seat].evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);}
  await pages[0].screenshot({path:'test-results/blackjack-three-390.png',fullPage:true});
  await pages[0].getByTestId('blackjack-table-leave').click();await expect(pages[0].getByTestId('blackjack-table-create')).toBeVisible();
  expect(await pages[0].evaluate(()=>sessionStorage.getItem('blackjack-table-pending'))).toBeNull();
  expect(await pages[0].evaluate(()=>sessionStorage.getItem('blackjack-table-room'))).toBeNull();
  await Promise.all(contexts.map(context=>context.close()));
});
test('lost Blackjack leave response replays the same UUID after remount despite forbidden snapshot',async({page})=>{
  await auth(page);let left=false;let calls=0;const ids:string[]=[];
  const publicState={phase:'lobby',capacity:3,viewer_seat:0,host_seat:0,active_seat:null,players:[{seat:0,nickname:'@fixture',cards:[],total:null,bet:0,status:'waiting',ready:false,outcome:null}],dealer_cards:[],dealer_total:null,legal_actions:['ready','leave'],wallet_balance:1000,turn_deadline:null,round_id:null};
  const snapshot={room_id:room,game_type:'blackjack',mode:'table',ruleset_version:'blackjack-gfl-table-1',state_version:1,public_state:publicState};
  await page.route('**/api/v1/rooms',r=>r.fulfill({json:r.request().postDataJSON().mode==='solo'?{...snapshot,room_id:'solo',mode:'solo',ruleset_version:'blackjack-skeleton-1',public_state:{phase:'waiting',legal_actions:['deal']}}:snapshot}));
  await page.route(`**/api/v1/rooms/${room}`,r=>left?r.fulfill({status:403,json:{detail:'not member'}}):r.fulfill({json:snapshot}));
  await page.route(`**/api/v1/rooms/${room}/actions`,async r=>{const body=r.request().postDataJSON();ids.push(body.action_id);calls++;left=true;if(calls===1){await r.abort();return;}await r.fulfill({json:{event:{room_id:room,event_id:body.action_id,ruleset_version:'blackjack-gfl-table-1',state_version:2,payload:{action_id:body.action_id,public_state:{phase:'left',legal_actions:[]}}}}});});
  await page.goto('/');await openRoom(page,'blackjack');await page.getByRole('button',{name:'Общий стол · до 3',exact:true}).click();await page.getByTestId('blackjack-table-create').click();await page.getByTestId('blackjack-table-leave').click();await expect(page.getByRole('button',{name:'Повторить запрос'})).toBeVisible();
  await page.reload();await openRoom(page,'blackjack');
  // Pending leave must be deliverable without membership or a successful snapshot read.
  if(await page.getByRole('button',{name:'Повторить запрос'}).isVisible())await page.getByRole('button',{name:'Повторить запрос'}).click();
  await expect(page.getByTestId('blackjack-table-create')).toBeEnabled({timeout:7000});expect(ids).toHaveLength(2);expect(ids[0]).toBe(ids[1]);expect(await page.evaluate(()=>sessionStorage.getItem('blackjack-table-pending'))).toBeNull();
});
test('lost poker cancellation survives denied restore and retries its original UUID',async({page})=>{
  await auth(page);let cancelled=false;let calls=0;const ids:string[]=[];
  const waiting={phase:'waiting',capacity:6,buy_in:100,viewer_seat:0,players:[{seat:0,stack:100,committed:0,street_committed:0,folded:false,all_in:false,nickname:'@own',cards:[]}],legal_actions:['cancel'],search_deadline:new Date(Date.now()+60000).toISOString(),wallet_balance:1000};
  const snapshot={room_id:room,game_type:'holdem',mode:'pvp',ruleset_version:'holdem-six-1',state_version:1,public_state:waiting};
  await page.route('**/api/v1/rooms',r=>r.fulfill({json:snapshot}));await page.route(`**/api/v1/rooms/${room}`,r=>cancelled?r.fulfill({status:403,json:{detail:'not member'}}):r.fulfill({json:snapshot}));
  await page.route(`**/api/v1/rooms/${room}/actions`,async r=>{const body=r.request().postDataJSON();ids.push(body.action_id);calls++;cancelled=true;if(calls===1){await r.abort();return;}await r.fulfill({json:{event:{room_id:room,event_id:body.action_id,ruleset_version:'holdem-six-1',state_version:2,payload:{action_id:body.action_id,public_state:{phase:'cancelled',capacity:6,buy_in:100,viewer_seat:null,players:[],legal_actions:[],search_deadline:null,turn_deadline:null}}}}});});
  await page.goto('/');await openRoom(page,'holdem');await page.getByLabel('Живой игрок').check();await page.getByTestId('holdem-start').click();await page.getByTestId('holdem-cancel').click();await expect(page.getByRole('button',{name:'Повторить ход'})).toBeVisible();
  await page.reload();await openRoom(page,'holdem');await expect(page.getByRole('button',{name:'Повторить ход'})).toBeVisible();await page.getByRole('button',{name:'Повторить ход'}).click();await expect(page.getByText('Поиск завершён. Вход не списан.')).toBeVisible();expect(ids).toHaveLength(2);expect(ids[0]).toBe(ids[1]);expect(await page.evaluate(()=>sessionStorage.getItem('holdem-action'))).toBeNull();
});
test('lost poker action survives a transient snapshot failure and blocks a fresh entry',async({page})=>{
  await auth(page);let failed=false;let calls=0;const ids:string[]=[];const active=activePoker();
  const settled={...active,phase:'settled',current_seat:null,legal_actions:[],min_raise_to:null,turn_deadline:null,last_result:{outcome:'fold',pots:[{amount:60,eligible_seats:[0],winner_seats:[0],shares:{0:60}}],refunds:{},cashouts:{0:150,1:90,2:90,3:90,4:90,5:90},net_deltas:{0:50,1:-10,2:-10,3:-10,4:-10,5:-10}}};
  const snapshot={room_id:room,game_type:'holdem',mode:'pvp',ruleset_version:'holdem-six-1',state_version:1,public_state:active};
  await page.route('**/api/v1/rooms',r=>r.fulfill({json:snapshot}));await page.route('**/avatar',r=>r.fulfill({status:204}));
  await page.route(`**/api/v1/rooms/${room}`,r=>failed?r.fulfill({status:503,json:{detail:'temporary'}}):r.fulfill({json:snapshot}));
  await page.route(`**/api/v1/rooms/${room}/actions`,async r=>{const body=r.request().postDataJSON();ids.push(body.action_id);calls++;failed=true;if(calls===1){await r.abort();return;}await r.fulfill({json:{event:{room_id:room,event_id:body.action_id,ruleset_version:'holdem-six-1',state_version:2,payload:{action_id:body.action_id,public_state:settled}}}});});
  await page.goto('/');await openRoom(page,'holdem');await page.getByLabel('Живой игрок').check();await page.getByTestId('holdem-start').click();await page.getByTestId('holdem-check').click();await expect(page.getByRole('button',{name:'Повторить ход'})).toBeVisible();
  await page.reload();await openRoom(page,'holdem');await expect(page.getByRole('button',{name:'Повторить ход'})).toBeVisible();await expect(page.getByTestId('holdem-start')).toBeDisabled();
  expect(await page.evaluate(()=>JSON.parse(sessionStorage.getItem('holdem-room')!).id)).toBe(room);
  await page.getByRole('button',{name:'Повторить ход'}).click();await expect(page.getByTestId('holdem-result')).toContainText('+50 JG');expect(ids).toHaveLength(2);expect(ids[0]).toBe(ids[1]);
});
test('temporary restore failure keeps the room token and offers retry instead of a new game',async({page})=>{
  await auth(page);let failed=false;const active=activePoker();const snapshot={room_id:room,game_type:'holdem',mode:'pvp',ruleset_version:'holdem-six-1',state_version:1,public_state:active};
  await page.route('**/api/v1/rooms',r=>r.fulfill({json:snapshot}));await page.route('**/avatar',r=>r.fulfill({status:204}));await page.route(`**/api/v1/rooms/${room}`,r=>failed?r.fulfill({status:503,json:{detail:'temporary'}}):r.fulfill({json:snapshot}));
  await page.goto('/');await openRoom(page,'holdem');await page.getByLabel('Живой игрок').check();await page.getByTestId('holdem-start').click();await expect(page.getByTestId('holdem-multiplayer')).toBeVisible();failed=true;
  await page.reload();await openRoom(page,'holdem');await expect(page.getByRole('button',{name:'Восстановить раздачу'})).toBeVisible();await expect(page.getByTestId('holdem-start')).toBeDisabled();expect(await page.evaluate(()=>JSON.parse(sessionStorage.getItem('holdem-room')!).id)).toBe(room);
  failed=false;await page.getByRole('button',{name:'Восстановить раздачу'}).click();await expect(page.getByTestId('holdem-multiplayer')).toBeVisible();
});
