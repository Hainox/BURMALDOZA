import {test,expect,type Page} from '@playwright/test';
import {openRoom} from './helpers';
const room='00000000-0000-0000-0000-000000000075';
async function recordHaptics(page: Page) {
  await page.addInitScript(() => {
    const record = (value: string) => {
      const calls = JSON.parse(sessionStorage.getItem('sound-haptics') ?? '[]') as string[];
      calls.push(value); sessionStorage.setItem('sound-haptics', JSON.stringify(calls));
    };
    const telegram = (window as unknown as { Telegram: { WebApp: Record<string, unknown> } }).Telegram;
    telegram.WebApp.HapticFeedback = {
      impactOccurred: (style: string) => record(`impact:${style}`),
      notificationOccurred: (style: string) => record(style),
      selectionChanged: () => record('selection')
    };
  });
}
async function stub(page:Page, options:{pvp?:boolean;conflict?:boolean;lost?:boolean;profile?:boolean}={}) {
  await page.addInitScript(() => { (window as unknown as {Telegram:unknown}).Telegram={WebApp:{initData:'query_id=verified-test',ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){}}}; });
  await page.route('**/api/v1/wallet',r=>r.fulfill({json:{balance:1000,currency_code:'JOKERGEM',version:1}}));
  await page.route('**/api/v1/wallet/ledger',r=>r.fulfill({json:[]}));
  await page.route('**/api/v1/leaderboard',r=>r.fulfill({json:{week_start:'2026-10-12T00:00:00+03:00',week_end:'2026-10-19T00:00:00+03:00',entries:[]}}));
  let p:Record<string,unknown>={};let v=1;let calls=0;
  const ids:string[]=[];
  const active=(buy:number)=>({phase:'active',game_phase:'pre_flop',buy_in:buy,seat:0,hero_code:options.pvp?null:'Kazuma_Kiryu',pot:buy*.15,current_seat:0,current_bet:buy/10,stacks:[buy*.95,buy*.9],street_contributions:[buy/20,buy/10],minimum_raise:buy/5,legal_actions:['fold','call','raise'],community_cards:[],hole_cards:[{rank:'A',suit:'S'},{rank:'K',suit:'S'}],opponent_cards:[{hidden:true},{hidden:true}],showdown:false,wallet_balance:1000-buy,turn_deadline:options.pvp?new Date(Date.now()+20000).toISOString():null});
  const snapshot=()=>({room_id:room,game_type:'holdem',mode:options.pvp?'pvp':'bot',status:p.phase,ruleset_version:'holdem-v1',state_version:v,public_state:options.profile && p.phase !== 'waiting' ? {...p,opponent_profile:{nickname:'@fixture_opponent',avatar_path:`/api/v1/rooms/${room}/opponent-avatar`}} : p});
  await page.route('**/api/v1/rooms',async r=>{const body=r.request().postDataJSON();expect(body.game_type).toBe('holdem');expect([100,500,1000]).toContain(body.buy_in);expect(body.action_id).toBe(r.request().headers()['x-request-id']);p=options.pvp?{phase:'waiting',buy_in:body.buy_in,seat:0,legal_actions:[],search_deadline:new Date(Date.now()+60000).toISOString(),wallet_balance:1000}:active(body.buy_in);await r.fulfill({json:snapshot()});});
  await page.route(`**/api/v1/rooms/${room}`,r=>r.fulfill({json:snapshot()}));
  await page.routeWebSocket(`**/api/v1/rooms/${room}/events`,()=>{});
  await page.route(`**/api/v1/rooms/${room}/actions`,async r=>{
    const request=r.request().postDataJSON();ids.push(request.action_id);calls++;
    if(options.lost && calls===1){await r.abort();return;}
    if(options.conflict && calls===1){v++;p={...p,legal_actions:['check','fold'],current_bet:0,street_contributions:[0,0],minimum_raise:10};await r.fulfill({status:409,json:{detail:'stale version'}});return;}
    v++;
    if(request.payload.action==='cancel'){p={...p,phase:'cancelled',search_deadline:null};}
    else {const buy=p.buy_in as number;p={...p,phase:'settled',game_phase:'showdown',legal_actions:[],turn_deadline:null,showdown:true,community_cards:[{rank:'Q',suit:'S'},{rank:'J',suit:'S'},{rank:'10',suit:'S'},{rank:'2',suit:'D'},{rank:'7',suit:'C'}],opponent_cards:[{rank:'9',suit:'H'},{rank:'9',suit:'D'}],wallet_balance:1000+buy,last_result:{winner_seats:[0],payouts:[buy*2,0],net_deltas:[buy,-buy],outcome:'showdown'}};}
    await r.fulfill({json:{event:{event_id:request.action_id,room_id:room,state_version:v,type:'holdem.action.accepted',payload:{public_state:p},server_time:new Date().toISOString()}}});
  });
  return {ids,match:()=>{v++;p=active(p.buy_in as number);},timeout:()=>{v++;p={...p,phase:'cancelled',search_deadline:null};},turnTimeout:()=>{const buy=p.buy_in as number;v++;p={...p,phase:'settled',game_phase:'settled',legal_actions:[],turn_deadline:null,showdown:false,wallet_balance:1000-buy/20,last_result:{winner_seats:[1],payouts:[buy-buy/20,buy+buy/20],net_deltas:[-buy/20,buy/20],outcome:'fold'}};}};
}
for(const buy of [100,500,1000])test(`bot table ${buy}: intro, private cards, raise and showdown`,async({page})=>{
  await stub(page);await page.setViewportSize({width:375,height:812});await page.goto('/');await openRoom(page,'holdem');
  await page.locator(`input[value="${buy}"]`).check();await page.getByTestId('holdem-start').click();
  await expect(page.getByTestId('holdem-intro')).toBeVisible();await page.getByRole('button',{name:'К столу'}).click();
  await expect(page.getByTestId('holdem-opponent').getByLabel('Закрытая карта')).toHaveCount(2);
  await expect(page.getByTestId('holdem-timer')).toHaveCount(0);
  if(buy === 100) await page.screenshot({path:'test-results/holdem375.png',fullPage:true});
  await page.getByLabel('Сумма рейза').fill(String(buy+1));await expect(page.getByTestId('holdem-raise')).toBeDisabled();
  await page.getByTestId('holdem-call').click();await expect(page.getByTestId('holdem-result')).toContainText('Победа');
  await expect(page.getByTestId('holdem-opponent').getByLabel('Закрытая карта')).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
test('restoring a settled hand does not replay result haptics or hero intro', async ({ page }) => {
  await stub(page); await recordHaptics(page);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/'); await openRoom(page, 'holdem');
  await page.getByTestId('holdem-start').click();
  await page.getByTestId('holdem-call').click();
  await expect(page.getByTestId('holdem-result')).toBeVisible();
  await expect.poll(() => page.evaluate(() => sessionStorage.getItem('sound-haptics'))).toContain('success');
  await page.getByRole('button', { name: 'Назад к комнатам' }).click();
  await page.evaluate(() => sessionStorage.setItem('sound-haptics', '[]'));
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await openRoom(page, 'holdem');
  await expect(page.getByTestId('holdem-result')).toBeVisible();
  await expect(page.getByTestId('holdem-intro')).toHaveCount(0);
  await page.waitForTimeout(1200);
  const calls = await page.evaluate(() => sessionStorage.getItem('sound-haptics'));
  expect(calls).not.toContain('success');
  expect(calls).not.toContain('impact:medium');
});
test('pvp cancel and server search timeout never charge entry',async({page})=>{
  const state=await stub(page,{pvp:true});await page.goto('/');await openRoom(page,'holdem');await page.getByLabel('Живой игрок').check();await page.getByTestId('holdem-start').click();
  await expect(page.getByText('Поиск соперника',{exact:true})).toBeVisible();await page.getByTestId('holdem-cancel').click();await expect(page.getByText('Поиск завершён. Вход не списан.')).toBeVisible();
  await page.getByRole('button',{name:'Выбрать стол'}).click();await page.getByTestId('holdem-start').click();state.timeout();await expect(page.getByText('Поиск завершён. Вход не списан.')).toBeVisible({timeout:6000});
});
test('pvp match uses server timer and no character intro',async({page})=>{
  const state=await stub(page,{pvp:true});await page.goto('/');await openRoom(page,'holdem');await page.getByLabel('Живой игрок').check();await page.getByTestId('holdem-start').click();await expect(page.getByTestId('holdem-cancel')).toBeVisible();state.match();await expect(page.getByTestId('holdem-timer')).toBeVisible({timeout:6000});await expect(page.getByTestId('holdem-intro')).toHaveCount(0);state.turnTimeout();await expect(page.getByTestId('holdem-result')).toContainText('Поражение',{timeout:6000});await expect(page.getByTestId('holdem-opponent').getByLabel('Закрытая карта')).toHaveCount(2);await expect(page.getByTestId('holdem-timer')).toHaveCount(0);
});
test('pvp profile loads authenticated blob, restores on reload and falls back on failure',async({page})=>{
  const state=await stub(page,{pvp:true,profile:true});
  await page.addInitScript(()=>{const revoke=URL.revokeObjectURL.bind(URL);URL.revokeObjectURL=(url)=>{sessionStorage.setItem('avatar-revoked',url);revoke(url);};});
  let requests=0;let fail=false;
  await page.route(`**/api/v1/rooms/${room}/opponent-avatar`,async r=>{
    requests++;
    expect(r.request().headers()['x-telegram-init-data']).toBe('query_id=verified-test');
    expect(r.request().url()).not.toContain('verified-test');
    if(fail){await r.fulfill({status:503});return;}
    await r.fulfill({contentType:'image/png',path:'tests/e2e/fixtures/opponent-avatar.png'});
  });
  await page.goto('/');await openRoom(page,'holdem');await page.getByLabel('Живой игрок').check();await page.getByTestId('holdem-start').click();
  expect(requests).toBe(0);state.match();
  await expect(page.getByTestId('holdem-opponent-nickname')).toHaveText('@fixture_opponent',{timeout:6000});
  await expect(page.getByAltText('Аватар соперника')).toBeVisible();
  const blobUrl=await page.getByAltText('Аватар соперника').getAttribute('src');expect(blobUrl).toMatch(/^blob:/);
  await page.waitForTimeout(2200);expect(requests).toBe(1);
  await page.getByRole('button',{name:'Назад к комнатам'}).click();
  // Выход из комнаты теперь анимирован: освобождение blob происходит после outro.
  await expect.poll(()=>page.evaluate(()=>sessionStorage.getItem('avatar-revoked'))).toBe(blobUrl);
  fail=true;await openRoom(page,'holdem');
  await expect(page.getByTestId('holdem-opponent-nickname')).toHaveText('@fixture_opponent');
  await expect(page.getByTestId('holdem-avatar-placeholder')).toBeVisible();
  await expect.poll(()=>requests).toBe(2);
  await page.reload();await openRoom(page,'holdem');
  await expect(page.getByTestId('holdem-opponent-nickname')).toHaveText('@fixture_opponent');
  await expect.poll(()=>requests).toBe(3);
});
test('conflict reloads and network retry keeps action UUID',async({page})=>{
  const state=await stub(page,{lost:true});await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/');await openRoom(page,'holdem');await page.getByTestId('holdem-start').click();await expect(page.getByTestId('holdem-intro')).toHaveCount(0);await page.getByTestId('holdem-call').click();await expect(page.getByRole('button',{name:'Повторить ход'})).toBeVisible();await page.reload();await openRoom(page,'holdem');await page.getByRole('button',{name:'Повторить ход'}).click();await expect(page.getByTestId('holdem-result')).toBeVisible();expect(state.ids.length).toBe(2);expect(state.ids[0]).toBe(state.ids[1]);
});
test('old version reloads legal actions instead of sending again',async({page})=>{
  await stub(page,{conflict:true});await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/');await openRoom(page,'holdem');await page.getByTestId('holdem-start').click();await page.getByTestId('holdem-call').click();await expect(page.getByTestId('holdem-check')).toBeVisible();await expect(page.getByTestId('holdem-call')).toHaveCount(0);
});
test('demo wide screen and reduced motion have no wallet side effects',async({page})=>{
  let avatarRequests=0;page.on('request',request=>{if(request.url().includes('opponent-avatar'))avatarRequests++;});
  await page.setViewportSize({width:1440,height:900});await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/');await openRoom(page,'holdem');await expect(page.getByText(/DEMO · записанная/)).toBeVisible();await page.getByTestId('holdem-start').click();await expect(page.getByTestId('holdem-intro')).toHaveCount(0);await page.getByTestId('holdem-call').click();await expect(page.getByTestId('holdem-result')).toContainText('Демонстрационная раздача');
  expect(avatarRequests).toBe(0);
});
