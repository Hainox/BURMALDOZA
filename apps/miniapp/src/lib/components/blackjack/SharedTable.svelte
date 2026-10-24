<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { base } from '$app/paths';
  import type { ApiClient } from '$lib/api/client';
  import type { RoomSnapshot } from '$lib/state/room.svelte';
  import { parseBlackjackTable, createBlackjackTable, joinBlackjackTable, resolveBlackjackTableAction, type BlackjackTableView } from '$lib/api/blackjack-table';
  import BetPicker from '$lib/components/BetPicker.svelte';
  import TableCard from './TableCard.svelte';
  export let client: ApiClient | null = null;
  export let live = false;
  export let reducedMotion = false;
  export let balance = 0;
  export let onBalance: (balance: number) => void = () => undefined;
  let snapshot: RoomSnapshot | null = null;
  let view: BlackjackTableView | null = null;
  let busy = false;
  let polling = false;
  let error = '';
  let code = '';
  let bet = 25;
  let seconds = 0;
  let disposed = false;
  let stopStream: (() => void) | null = null;
  let pollTimer: ReturnType<typeof setInterval>;
  let clockTimer: ReturnType<typeof setInterval>;
  type Pending = {kind:'create';id:string} | {kind:'join';id:string;room:string} | {kind:'action';id:string;room:string;version:number;payload:Record<string,unknown>};
  let pending: Pending | null = null;
  const labels: Record<string,string> = {blackjack:'Блэкджек · 3:2',win:'Победа',push:'Пуш · возврат',loss:'Поражение'};
  const actionLabels: Record<string,string> = {ready:'Готов',unready:'Снять готовность',start:'Начать раздачу',hit:'Ещё',stand:'Хватит',double:'Удвоить'};
  $: betMax = Math.max(25,Math.min(1000000,view?.balance??balance));
  $: betValid = Number.isSafeInteger(bet)&&bet>=25&&bet<=betMax&&bet<=(view?.balance??balance);
  function accept(next: RoomSnapshot) {
    if (disposed || (snapshot?.roomId===next.roomId&&next.stateVersion<snapshot.stateVersion)) return;
    if (next.rulesetVersion!=='blackjack-gfl-table-1') throw new Error('Неизвестная версия общего стола');
    const parsed=parseBlackjackTable(next.publicState);
    snapshot=next;view=parsed;
    if(parsed.balance!==null)onBalance(parsed.balance);
    seconds=parsed.deadline?Math.max(0,Math.ceil((Date.parse(parsed.deadline)-Date.now())/1000)):0;
  }
  function stream(id: string) {
    stopStream?.();
    stopStream=client?.subscribeToRoom(id,next=>{if(snapshot?.roomId===id)try{accept(next);}catch{error='Не удалось прочитать состояние общего стола.';}},event=>{
      if(snapshot?.roomId!==id||!snapshot)return;
      try{accept({...snapshot,stateVersion:event.state_version,publicState:event.payload.public_state as Record<string,unknown>});}catch{error='Не удалось прочитать событие общего стола.';}
    })??null;
  }
  async function refresh() {
    if(!client||!snapshot||busy||polling)return;
    polling=true;const id=snapshot.roomId;
    try{const next=await client.getRoom(id);if(snapshot?.roomId===id)accept(next);}
    catch(e){const status=typeof e==='object'&&e!==null&&'status'in e?e.status:null;if(status===403){stopStream?.();stopStream=null;error='Вы покинули стол. Доступ к его обновлениям закрыт.';}else error='Связь прервалась. Повторите синхронизацию.';}
    finally{polling=false;}
  }
  export async function resync(){error='';await refresh();if(snapshot&&!disposed)stream(snapshot.roomId);}
  function savePending(){if(pending)sessionStorage.setItem('blackjack-table-pending',JSON.stringify(pending));else sessionStorage.removeItem('blackjack-table-pending');}
  function leaveConfirmed() {stopStream?.();stopStream=null;snapshot=null;view=null;sessionStorage.removeItem('blackjack-table-room');}
  async function send() {
    if(!client||!live||!pending||busy)return;
    busy=true;error='';savePending();const p=pending;
    try{
      if(p.kind==='create'||p.kind==='join'){
        const next=p.kind==='create'?await createBlackjackTable(client,p.id):await joinBlackjackTable(client,p.room,p.id);
        accept(next);sessionStorage.setItem('blackjack-table-room',next.roomId);if(!disposed)stream(next.roomId);
      }else{
        const response=await client.applyAction(p.room,p.version,p.id,p.payload);
        if(!snapshot||snapshot.roomId!==p.room)throw new Error('Комната изменилась');
        const next=resolveBlackjackTableAction(snapshot,response.event,p.id,String(p.payload.action));
        if(next)accept(next);else leaveConfirmed();
      }
      pending=null;savePending();
    }catch(e){
      const status=typeof e==='object'&&e!==null&&'status'in e?e.status:null;
      if(typeof status==='number'&&status>=400&&status<500){pending=null;savePending();error=status===409?'Стол изменился или действие недоступно. Состояние обновлено.':status===403?'Нет доступа к этому столу.':'Сервер отклонил запрос. Проверьте код, ставку и доступные действия.';if(snapshot)try{accept(await client.getRoom(snapshot.roomId));}catch{/* Keep the last confirmed state. */}}
      else error='Ответ не получен. Повторите тот же запрос.';
    }finally{busy=false;}
  }
  function create(){if(!pending)pending={kind:'create',id:crypto.randomUUID()};void send();}
  function join(){if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(code.trim())){error='Введите полный код стола из приглашения.';return;}if(!pending)pending={kind:'join',id:crypto.randomUUID(),room:code.trim()};void send();}
  function action(name:string){if(!snapshot||!view||busy||pending||!view.legal.includes(name)||(name==='ready'&&!betValid))return;pending={kind:'action',id:crypto.randomUUID(),room:snapshot.roomId,version:snapshot.stateVersion,payload:{action:name,...(name==='ready'?{bet}:{})}};void send();}
  async function copyCode(){if(!snapshot)return;try{await navigator.clipboard.writeText(snapshot.roomId);error='Код стола скопирован.';}catch{error='Выделите и скопируйте код стола ниже.';}}
  onMount(()=>{
    pollTimer=setInterval(()=>{void refresh();},2000);
    clockTimer=setInterval(()=>{seconds=view?.deadline?Math.max(0,Math.ceil((Date.parse(view.deadline)-Date.now())/1000)):0;},250);
    if(!live||!client)return;const api=client;
    try{const raw=JSON.parse(sessionStorage.getItem('blackjack-table-pending')??'null');if(raw&&['create','join','action'].includes(raw.kind)&&typeof raw.id==='string'&&(raw.kind==='create'||typeof raw.room==='string')&&(raw.kind!=='action'||(Number.isSafeInteger(raw.version)&&['ready','unready','start','hit','stand','double','leave'].includes(raw.payload?.action))))pending=raw;else sessionStorage.removeItem('blackjack-table-pending');}catch{sessionStorage.removeItem('blackjack-table-pending');}
    const id=sessionStorage.getItem('blackjack-table-room');
    if(id){busy=true;api.getRoom(id).then(next=>{accept(next);if(!disposed)stream(id);if(pending)error='Остался неподтверждённый запрос. Повторите его с тем же идентификатором.';}).catch(()=>{sessionStorage.removeItem('blackjack-table-room');error='Предыдущий стол недоступен.';}).finally(()=>{busy=false;});}
    else if(pending)void send();
  });
  onDestroy(()=>{disposed=true;stopStream?.();clearInterval(pollTimer);clearInterval(clockTimer);});
</script>
<section class="shared-table" aria-label="Общий стол Blackjack" aria-busy={busy}>
  <header><h3><img src={`${base}/icons/table-users.svg`} alt="" /> Общий стол · до 3 игроков</h3><p>Один дилер, отдельная ставка и результат для каждого. На решение — 20 секунд.</p></header>
  {#if error}<div class="error" role="status">{error}{#if pending}<button on:click={send} disabled={busy}>Повторить запрос</button>{/if}</div>{/if}
  {#if !live||!client}<p role="status">Общий стол доступен в Telegram при подключении к игровому серверу. В DEMO можно играть с ботом.</p>
  {:else if !view}
    <div class="entrance"><button class="primary" data-testid="blackjack-table-create" on:click={create} disabled={busy||!!pending}>Создать стол</button><div class="join"><label for="blackjack-table-code">Код стола</label><input id="blackjack-table-code" bind:value={code} placeholder="UUID из приглашения" disabled={busy||!!pending} autocapitalize="none" spellcheck="false" /><button on:click={join} disabled={busy||!!pending}>Войти по коду</button></div></div>
  {:else}
    <div class="invitation"><label for="blackjack-invite-code">Пригласить за стол</label><div><input id="blackjack-invite-code" readonly value={snapshot?.roomId??''} /><button on:click={copyCode}>Копировать</button></div><small>Передайте код друзьям. Telegram-авторизация обязательна.</small></div>
    <div class="dealer"><img class="scene" src={`${base}/blackjack/room.webp`} alt="" /><b>Общий дилер{view.dealerTotal!==null?` · ${view.dealerTotal}`:''}</b><div class="cards">{#each view.dealer as card}<TableCard {card} {reducedMotion} />{/each}{#if !view.dealer.length}<p>Карты появятся после старта</p>{/if}</div></div>
    <div class="players">{#each view.players as player(player.seat)}<article class="player" class:own={player.seat===view.viewerSeat} class:active={view.phase==='active'&&view.activeSeat===player.seat} data-testid={`blackjack-seat-${player.seat}`}><div class="identity"><b>{player.seat===view.viewerSeat?'Вы':player.nickname}</b><small>Место {player.seat+1}{player.seat===view.hostSeat?' · Создатель':''}</small></div><div class="cards">{#each player.cards as card}<TableCard {card} {reducedMotion} />{/each}</div><p>{player.total!==null?`Очки ${player.total} · `:''}Ставка {player.bet} JG</p><small>{player.status==='leaving'?'Покинул стол · расчёт после раздачи':player.ready?'Готов':view.phase==='active'?(player.status==='waiting'?'Ждёт следующую раздачу':player.status==='finished'?'Ход завершён':'В игре'):'Не готов'}</small>{#if player.outcome}<p class="outcome" data-testid={`blackjack-result-${player.seat}`}>{labels[player.outcome.result]} · {player.outcome.net>0?'+':''}{player.outcome.net} JG<br /><small>Выплата {player.outcome.payout} JG</small></p>{/if}</article>{/each}</div>
    {#if view.phase==='active'&&view.deadline}<p class="timer" role="status" data-testid="blackjack-table-timer"><img src={`${base}/icons/table-timer.svg`} alt="" /><b>{seconds} с</b> · {view.activeSeat===view.viewerSeat?'Ваш ход':`Ход места ${(view.activeSeat??0)+1}`}. Затем — Stand.</p>{/if}
    {#if view.legal.includes('ready')}<BetPicker bind:value={bet} min={25} max={betMax} presets={[25,50,100,250,500].map(value=>({value}))} disabled={busy||!!pending} inputId="blackjack-table-bet" inputLabel="Ставка общего стола" /><p class="hint">Готовность не списывает ставку. Создатель запускает раздачу, когда готовы все.</p>{/if}
    <div class="actions">{#each view.legal.filter(action=>action!=='leave') as name}<button data-testid={`blackjack-table-${name}`} class:primary={name==='start'||name==='ready'} disabled={busy||!!pending||(name==='ready'&&!betValid)} on:click={()=>action(name)}>{actionLabels[name]}</button>{/each}</div>
    <div class="footer"><button on:click={resync} disabled={busy}>Синхронизировать стол</button>{#if view.legal.includes('leave')}<button data-testid="blackjack-table-leave" on:click={()=>action('leave')} disabled={busy||!!pending}><img src={`${base}/icons/table-log-out.svg`} alt="" />Выйти из стола</button>{/if}</div>
    {#if view.phase==='active'}<p class="hint">Выход не возвращает ставку: рука завершится по тайм-ауту и будет рассчитана сервером.</p>{/if}
  {/if}
</section>
<style>
  .shared-table{display:grid;gap:14px;color:#eef0f5;padding-bottom:max(8px,env(safe-area-inset-bottom));--bet-ink:#eef0f5;--bet-line:#9aa7ba77;--bet-accent:#d3b279}.shared-table header h3{display:flex;gap:8px;align-items:center;font:600 18px Georgia,serif;margin:4px 0}.shared-table header img,.timer img,.footer img{width:20px;height:20px;filter:invert(1)}p{font-size:12px;line-height:1.6;margin:5px 0}small{font-size:10px;color:#c4c9d3}.entrance,.join{display:grid;gap:10px}.join{padding:14px;border:1px solid #8b9db755;border-radius:14px}.join label,.invitation label{font-size:12px}.shared-table input{min-width:0;min-height:44px;box-sizing:border-box;border:1px solid #8b9db766;border-radius:8px;background:#101722;color:#f3f3f3;font:12px monospace;padding:8px;width:100%}.shared-table button{min-height:46px;padding:10px 14px;border:1px solid #9da8ba88;border-radius:10px;background:linear-gradient(#303e53,#141d2b);color:#f0f0f5;font:600 12px system-ui;cursor:pointer;transition:transform .18s}.shared-table button:active{transform:scale(.98)}.shared-table button:focus-visible,.shared-table input:focus-visible{outline:3px solid #e6c892;outline-offset:3px}.shared-table button:disabled{opacity:.4;cursor:default}.shared-table button.primary{border-color:#dfc08e;background:linear-gradient(#755634,#382818)}.invitation{display:grid;gap:7px}.invitation>div{display:flex;gap:6px}.invitation>div button{flex-shrink:0}.dealer{position:relative;isolation:isolate;overflow:hidden;text-align:center;min-height:130px;display:grid;align-content:center;justify-items:center;gap:12px;border:1px solid #8b9db755;border-radius:18px;background:#111a25}.scene{position:absolute;z-index:-1;inset:0;width:100%;height:100%;object-fit:cover;opacity:.3}.dealer>b{font-size:13px}.cards{display:flex;gap:5px;justify-content:center;flex-wrap:wrap}.players{display:grid;gap:8px;grid-template-columns:repeat(3,minmax(0,1fr))}.player{padding:10px 7px;min-width:0;text-align:center;border:1px solid #8b9db755;border-radius:13px;background:#121b28}.player.own{border-color:#d3b27999}.player.active{border-color:#ffe1a1;box-shadow:0 0 0 2px #d3b27944;background:#302a20}.player .cards{margin:10px 0}.player .cards :global(.card){width:42px}.identity{display:grid;gap:4px}.identity b{font-size:12px;overflow-wrap:anywhere}.outcome{padding:8px 4px;border-radius:8px;color:#ffe2ab;background:#5a422955}.actions,.footer{display:flex;flex-wrap:wrap;gap:8px}.actions button{flex:1}.footer{justify-content:space-between}.footer button{display:flex;align-items:center;gap:6px}.hint{color:#bac4d5}.timer{display:flex;justify-content:center;align-items:center;gap:6px;flex-wrap:wrap}.error{padding:12px;border:1px solid #e7a79a;border-radius:10px;font-size:12px}.error button{display:block;margin-top:8px}@media(max-width:540px){.players{grid-template-columns:1fr}.player{display:grid;grid-template-columns:1fr 1fr;align-items:center;gap:5px;text-align:left}.player .cards{margin:3px 0;justify-content:flex-end}.player .outcome{grid-column:1/-1}.invitation>div{flex-wrap:wrap}.invitation>div button{width:100%}}@media(prefers-reduced-motion:reduce){.shared-table button{transition:none}}
</style>
