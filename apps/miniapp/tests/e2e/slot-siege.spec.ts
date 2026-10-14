import {test,expect,type Page} from '@playwright/test';
import {openRoom} from './helpers';
const id='00000000-0000-0000-0000-000000000077';
const grid=[['D1','D2','D3','D4','A1','A2','A3'],['D2','A1','D1','D4','W','A3','D3'],['D3','W','A1','D4','D1','A2','D2']];
async function stub(page:Page) {
  await page.addInitScript(()=>{(window as unknown as {Telegram:unknown}).Telegram={WebApp:{initData:'query_id=verified-slot',ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){}}};});
  await page.route('**/api/v1/wallet',r=>r.fulfill({json:{balance:1000,currency_code:'JOKERGEM',version:1}}));
  await page.route('**/api/v1/wallet/ledger',r=>r.fulfill({json:[]}));
  await page.route('**/api/v1/leaderboard',r=>r.fulfill({json:{week_start:'2026-10-12T00:00:00+03:00',week_end:'2026-10-19T00:00:00+03:00',entries:[]}}));
  let version=0;let operation='op1';
  const metadata=()=>({operation_id:operation,next_operation_id:operation==='op1'?'op2':'op3',operation_changes_at:new Date(Date.now()+3600000).toISOString()});
  let publicState:Record<string,unknown>={phase:'waiting',legal_actions:['spin'],...metadata()};
  const snapshot=()=>({room_id:id,game_type:'slot',mode:'solo',status:'active',ruleset_version:'slot-siege-1',state_version:version,public_state:publicState});
  const sockets:Array<{send:(message:string)=>void}>=[];
  await page.routeWebSocket(`**/api/v1/rooms/${id}/events`,ws=>{sockets.push(ws);});
  await page.route('**/api/v1/rooms',r=>r.fulfill({json:snapshot()}));
  await page.route(`**/api/v1/rooms/${id}`,r=>r.fulfill({json:snapshot()}));
  await page.route(`**/api/v1/rooms/${id}/actions`,r=>{
    version++;
    const result={grid,reel_stops:[0,0,0],winning_lines:[{payline_index:0,rows:[3,3,3],symbols:['D4','D4','D4'],match_symbol:'D4',matched_columns:3,payout:40}],gross_payout:40,net_delta:30,balance_after:1000+version*30,ruleset_version:'slot-siege-1',...metadata()};
    publicState={phase:'active',legal_actions:['spin'],...metadata(),last_result:result};
    return r.fulfill({json:{event:{event_id:r.request().postDataJSON().action_id,room_id:id,state_version:version,type:'slot.action.accepted',ruleset_version:'slot-siege-1',server_time:new Date().toISOString(),payload:{public_state:publicState,result}}}});
  });
  return {rotate:()=>{operation='op2';publicState={...publicState,...metadata()};for(const ws of sockets)ws.send(JSON.stringify({type:'snapshot',snapshot:snapshot()}));}};
}
test('server faces stay with immutable spin and switch on next operation',async({page})=>{
  const state=await stub(page);await page.setViewportSize({width:375,height:812});await page.goto('/');await openRoom(page,'slot');
  await expect(page.getByTestId('slot-operation')).toHaveAttribute('data-operation-id','op1');await expect(page.getByTestId('slot-next-operation')).toContainText('Красный сигнал');
  const response=page.waitForResponse(r=>r.url().endsWith('/actions'));
  await page.getByTestId('slot-spin').click();await response;await expect(page.getByTestId('slot-machine')).toHaveAttribute('data-spin-seq','1');state.rotate();
  await expect(page.getByTestId('slot-operation')).toHaveAttribute('data-operation-id','op1');await expect(page.getByTestId('slot-next-operation')).toContainText('Красный сигнал');await expect(page.getByTestId('slot-winning-beams')).toHaveCount(0);
  await expect(page.getByTestId('slot-machine')).toHaveAttribute('data-slot-phase','settled',{timeout:7000});await expect(page.getByTestId('slot-winning-beams')).toBeVisible();
  const face=page.getByTestId('slot-reel-track-0').locator('[data-symbol="D1"] img').last();await expect(face).toHaveAttribute('src',/Pulse\.webp$/);
  await page.screenshot({path:'test-results/slot375.png',fullPage:true});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await expect(page.getByTestId('slot-spin')).toBeEnabled();await page.getByTestId('slot-spin').click();await expect(page.getByTestId('slot-machine')).toHaveAttribute('data-slot-phase','settled',{timeout:7000});
  await expect(page.getByTestId('slot-operation')).toHaveAttribute('data-operation-id','op2');await expect(face).toHaveAttribute('src',/Kaid\.webp$/);
  const finalSymbols=await page.getByTestId('slot-reel-track-0').locator('[data-symbol]').evaluateAll(nodes=>nodes.slice(-7).map(node=>node.getAttribute('data-symbol')));expect(finalSymbols).toEqual(grid[0]);
});
test('demo portraits and immediate reduced motion have attribution and no server claim',async({page})=>{
  await page.emulateMedia({reducedMotion:'reduce'});await page.setViewportSize({width:1440,height:900});await page.goto('/');await openRoom(page,'slot');await page.getByTestId('slot-spin').click();
  await expect(page.getByTestId('slot-machine')).toHaveAttribute('data-stopped-reels','3');await expect(page.getByTestId('slot-confirmed-grid')).toContainText('ДЕМО · исход без сервера');await expect(page.locator('.slot-room')).not.toContainText('SERVER CONFIRMED');
  await expect(page.getByTestId('slot-free-spins')).toHaveCount(0);await expect(page.locator('.operator-face').first()).toHaveAttribute('src',/\/slot\/faces\//);
  await page.getByText('Источники изображений',{exact:true}).click();await expect(page.getByRole('link',{name:'Оперативники и источники портретов'})).toBeVisible();
});
