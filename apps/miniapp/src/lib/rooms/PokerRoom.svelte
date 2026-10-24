<script lang="ts">
  import { getContext, onMount, onDestroy } from 'svelte';
  import { base } from '$app/paths';
  import type { ApiClient } from '$lib/api/client';
  import { createHoldem, parseHoldem, type HoldemMode, type HoldemView } from '$lib/api/holdem';
  import type { RoomSnapshot } from '$lib/state/room.svelte';
  import HandTable from '$lib/components/holdem/HandTable.svelte';
  import MultiplayerTable from '$lib/components/holdem/MultiplayerTable.svelte';
  import { createHoldemTable, parseHoldemTable, type HoldemTableView } from '$lib/api/holdem-table';
  import { sound } from '$lib/audio/sound';
  import heroes from '$lib/components/holdem/heroes.json';

  export let client: ApiClient | null = null;
  export let live = false;
  export let reducedMotion = false;
  const quiet = getContext<() => boolean>('room-motion-quiet') ?? (() => false);
  export let onBalance: (balance:number) => void = () => undefined;
  let mode: HoldemMode = 'bot';
  let buyIn = 100;
  let snapshot: RoomSnapshot | null = null;
  let view: HoldemView | null = null;
  let tableView: HoldemTableView | null = null;
  let tableAvatars: Record<number,string> = {};
  let tableAvatarRoom = '';
  let tableAvatarAttempts = new Set<number>();
  let tableAvatarRequests: AbortController[] = [];
  function clearTableAvatars() {
    for (const request of tableAvatarRequests) request.abort();
    tableAvatarRequests=[];
    for (const url of Object.values(tableAvatars)) URL.revokeObjectURL(url);
    tableAvatars={};tableAvatarAttempts.clear();tableAvatarRoom='';
  }
  function loadTableAvatars(roomId: string) {
    if(!client||!live||!tableView)return;
    // Seat IDs are reusable while waiting; load only the immutable active roster.
    if(tableView.phase!=='active'&&tableView.phase!=='settled'){clearTableAvatars();return;}
    if(tableAvatarRoom!==roomId){clearTableAvatars();tableAvatarRoom=roomId;}
    for(const player of tableView.players){
      if(!player.avatarPath||player.seat===tableView.viewerSeat||tableAvatarAttempts.has(player.seat))continue;
      tableAvatarAttempts.add(player.seat);const controller=new AbortController();tableAvatarRequests.push(controller);const seat=player.seat;
      void client.getPlayerAvatar(roomId,seat,controller.signal).then(blob=>{if(!disposed&&!controller.signal.aborted&&tableAvatarRoom===roomId&&blob)tableAvatars={...tableAvatars,[seat]:URL.createObjectURL(blob)};}).catch(()=>{/* Optional avatars never block the game. */});
    }
  }
  let busy = false;
  let error = '';
  let introRoom = '';
  let showIntro = false;
  let cancelIntroVoice: (() => void) | null = null;
  let seconds = 0;
  let stopStream: (() => void) | null = null;
  let polling = false;
  let disposed = false;
  let restoreRoomId: string | null = null;
  let avatarUrl = '';
  let avatarRoom = '';
  let avatarRequest: AbortController | null = null;
  function clearAvatar() {
    avatarRequest?.abort(); avatarRequest=null;
    if (avatarUrl) URL.revokeObjectURL(avatarUrl);
    avatarUrl=''; avatarRoom='';
  }
  async function loadAvatar(roomId:string, force=false) {
    if (!live || !client || mode !== 'pvp' || !view?.opponentProfile) {clearAvatar();return;}
    if (!force && avatarRoom === roomId) return;
    clearAvatar(); avatarRoom=roomId;
    const controller=new AbortController(); avatarRequest=controller;
    try {
      const blob=await client.getOpponentAvatar(roomId,controller.signal);
      if (!disposed && !controller.signal.aborted && snapshot?.roomId === roomId && blob) avatarUrl=URL.createObjectURL(blob);
    } catch { /* Optional photo failure leaves the neutral icon; resync retries explicitly. */ }
    finally {if(avatarRequest === controller)avatarRequest=null;}
  }
  let lastBalance: number | null = null;
  let pollTimer: ReturnType<typeof setInterval>;
  let clockTimer: ReturnType<typeof setInterval>;
  let pendingCreate: {mode:HoldemMode;buyIn:number;id:string;capacity?:6} | null = null;
  let pendingAction: {roomId:string;version:number;id:string;payload:Record<string,unknown>;rulesetVersion?:string} | null = null;
  $: hero = mode === 'bot' && view?.heroCode ? (heroes as Record<string,{name:string;avatar:string;intro:string;title:string}>)[view.heroCode] ?? null : null;

  function accept(next: RoomSnapshot, restored = false) {
    if (disposed || (snapshot?.roomId === next.roomId && next.stateVersion < snapshot.stateVersion)) return;
    if(next.rulesetVersion==='holdem-six-1'){
      const parsed=parseHoldemTable(next.publicState);cancelIntroVoice?.();cancelIntroVoice=null;showIntro=false;clearAvatar();snapshot=next;tableView=parsed;view=null;
      if(parsed.phase==='cancelled'){stopStream?.();stopStream=null;sessionStorage.removeItem('holdem-room');}
      loadTableAvatars(next.roomId);
      if(live&&parsed.balance!==null&&parsed.balance!==lastBalance){lastBalance=parsed.balance;onBalance(parsed.balance);}
      seconds=parsed.deadline?Math.max(0,Math.ceil((Date.parse(parsed.deadline)-Date.now())/1000)):0;return;
    }
    if(next.rulesetVersion!=='holdem-v1'&&next.rulesetVersion!=='holdem-demo-1')throw new Error('Неизвестная версия Hold’em');
    tableView=null;clearTableAvatars();
    const parsed = parseHoldem(next.publicState);
    if (snapshot?.roomId !== next.roomId || parsed.phase === 'settled') { cancelIntroVoice?.(); cancelIntroVoice = null; }
    snapshot = next; view = parsed;
    void loadAvatar(next.roomId);
    if (live && parsed.balance !== null && parsed.balance !== lastBalance) {lastBalance=parsed.balance;onBalance(parsed.balance);}
    seconds = parsed.deadline ? Math.max(0,Math.ceil((Date.parse(parsed.deadline)-Date.now())/1000)) : 0;
    const knownHero = mode === 'bot' && parsed.heroCode && parsed.heroCode in heroes;
    if (knownHero && introRoom !== next.roomId) {
      introRoom = next.roomId;
      showIntro = !restored && parsed.phase === 'active' && !reducedMotion && !quiet();
      if (showIntro) {
        const code = parsed.heroCode;
        cancelIntroVoice = sound.cue('intro', () => { if (code) sound.voice(code, 'quip'); });
      }
    }
  }
  function stream(roomId:string) {
    stopStream?.();
    stopStream = client?.subscribeToRoom(roomId, next => {if(snapshot?.roomId !== roomId)return;try{accept(next);}catch(e){error=String(e);}}, event => {
      if (snapshot?.roomId !== roomId) return;
      try { accept({...snapshot,stateVersion:event.state_version,publicState:event.payload.public_state as Record<string,unknown>}); } catch(e) {error=String(e);}
    }) ?? null;
  }
  async function refresh() {
    if (!live || !client || !snapshot || tableView?.phase==='cancelled' || polling || busy) return;
    polling = true;
    const id = snapshot.roomId;
    try { const next = await client.getRoom(id); if (snapshot?.roomId === id) accept(next); }
    catch { error = 'Не удалось обновить раздачу. Повторите синхронизацию.'; }
    finally { polling = false; }
  }
  export async function resync() {error='';if(restoreRoomId)await restoreRoom();else await refresh();if(snapshot && !disposed){stream(snapshot.roomId);void loadAvatar(snapshot.roomId,true);}}
  async function start() {
    if (busy || pendingAction || restoreRoomId) return;
    busy = true; error = ''; showIntro = false;
    try {
      if (live && client) {
        pendingCreate ??= {mode,buyIn,id:crypto.randomUUID(),...(mode==='pvp'?{capacity:6 as const}:{})};
        sessionStorage.setItem('holdem-create',JSON.stringify(pendingCreate));
        mode = pendingCreate.mode; buyIn = pendingCreate.buyIn;
        const next = mode==='pvp'&&pendingCreate.capacity===6 ? await createHoldemTable(client,buyIn,pendingCreate.id) : await createHoldem(client,mode,buyIn,pendingCreate.id);
        accept(next); pendingCreate = null;
        sessionStorage.removeItem('holdem-create');
        sessionStorage.setItem('holdem-room', JSON.stringify({id:next.roomId,mode}));
        if (!disposed) stream(next.roomId);
      } else {
        mode = 'bot';
        accept({roomId:`demo-${crypto.randomUUID()}`,gameType:'holdem',title:'Kamurocho 神室町',rulesetVersion:'holdem-demo-1',stateVersion:1,publicState:{phase:'active',buy_in:buyIn,seat:0,hero_code:'Kazuma_Kiryu',game_phase:'pre_flop',pot:buyIn*0.15,stacks:[buyIn*0.95,buyIn*0.9],street_contributions:[buyIn*0.05,buyIn*0.1],current_seat:0,current_bet:buyIn*0.1,minimum_raise:buyIn*0.2,legal_actions:['fold','call'],community_cards:[],hole_cards:[{rank:'A',suit:'S'},{rank:'K',suit:'S'}],showdown:false}});
      }
    } catch(e) {
      if (typeof e === 'object' && e !== null && 'status' in e && typeof e.status === 'number' && e.status >= 400 && e.status < 500) {pendingCreate=null;sessionStorage.removeItem('holdem-create');error='Сервер отклонил вход. Проверьте баланс и выберите стол.';}
      else error='Не удалось начать раздачу. «Повторить» отправит тот же запрос.';
    }
    finally {busy=false;}
  }
  async function action(name:string, fields:Record<string,unknown>={}) {
    if (busy || (!snapshot&&!pendingAction) || (!view&&!tableView&&!pendingAction)) return;
    if (!pendingAction && name !== 'cancel' && !(tableView??view)?.legal.includes(name)) return;
    busy=true; error='';
    try {
      if (live && client) {
        pendingAction ??= {roomId:snapshot!.roomId,version:snapshot!.stateVersion,id:crypto.randomUUID(),payload:{action:name,...fields},rulesetVersion:snapshot!.rulesetVersion};
        sessionStorage.setItem('holdem-action',JSON.stringify(pendingAction));
        const p = pendingAction;
        const response = await client.applyAction(p.roomId,p.version,p.id,p.payload);
        const previous=snapshot?.roomId===p.roomId?snapshot:null;
        const ruleset=response.event.ruleset_version??p.rulesetVersion??previous?.rulesetVersion;
        if(!ruleset)throw new Error('В ответе отсутствует версия игры');
        if(response.event.room_id&&response.event.room_id!==p.roomId)throw new Error('Ответ другой комнаты');
        if(response.event.event_id&&response.event.event_id!==p.id)throw new Error('Ответ другого запроса');
        accept({roomId:p.roomId,gameType:'holdem',title:'Kamurocho 神室町',rulesetVersion:ruleset,stateVersion:response.event.state_version,publicState:response.event.payload.public_state as Record<string,unknown>},!previous);
        restoreRoomId=null;
        if(tableView?.phase!=='cancelled'&&view?.phase!=='cancelled'){
          sessionStorage.setItem('holdem-room',JSON.stringify({id:p.roomId,mode}));
          if(!stopStream&&!disposed)stream(p.roomId);
        }
        pendingAction=null;
        sessionStorage.removeItem('holdem-action');
      } else {
        const p=snapshot!.publicState;
        // A fixed recorded scene, never a live outcome or a wallet update.
        accept({...snapshot!,stateVersion:snapshot!.stateVersion+1,publicState:{...p,phase:'settled',game_phase:'showdown',legal_actions:[],showdown:name !== 'fold',pot:buyIn,stacks:[buyIn/2,buyIn/2],street_contributions:[buyIn/2,buyIn/2],community_cards:name === 'fold' ? [] : [{rank:'Q',suit:'S'},{rank:'J',suit:'S'},{rank:'10',suit:'S'},{rank:'2',suit:'D'},{rank:'7',suit:'C'}],opponent_cards:[{rank:'9',suit:'H'},{rank:'9',suit:'D'}],last_result:{winner_seats:[name === 'fold' ? 1 : 0],payouts:name === 'fold' ? [buyIn/2,buyIn*1.5] : [buyIn*1.5,buyIn/2],net_deltas:name === 'fold' ? [-buyIn/2,buyIn/2] : [buyIn/2,-buyIn/2],outcome:name === 'fold' ? 'fold' : 'showdown'}}});
      }
    } catch (e) {
      const status = typeof e === 'object' && e !== null && 'status' in e ? e.status : null;
      if (typeof status === 'number' && status >= 400 && status < 500) {pendingAction=null;sessionStorage.removeItem('holdem-action');}
      error=pendingAction ? 'Ответ не получен. Повторите тот же запрос.' : 'Ход отклонён. Состояние перечитано; выберите доступное действие.';
      if (client && snapshot) {try{accept(await client.getRoom(snapshot.roomId));}catch{error+=' Синхронизация недоступна.';}}
    } finally {busy=false;}
  }
  function lobby() { cancelIntroVoice?.();cancelIntroVoice=null;sound.stopEffects();clearAvatar();stopStream?.();stopStream=null;snapshot=null;view=null;tableView=null;restoreRoomId=null;clearTableAvatars();pendingAction=null;sessionStorage.removeItem('holdem-room');sessionStorage.removeItem('holdem-action'); }
  function focusIntro(node:HTMLButtonElement) {node.focus();}
  function restoreAction(roomId?:string) {
    try {const p=JSON.parse(sessionStorage.getItem('holdem-action') ?? 'null');if(typeof p?.roomId==='string' && (!roomId||p.roomId===roomId) && typeof p.id === 'string' && Number.isSafeInteger(p.version) && ['fold','check','call','raise','cancel'].includes(p.payload?.action)){pendingAction=p;error='Остался неподтверждённый запрос. Повторите ход с тем же идентификатором.';}}
    catch {sessionStorage.removeItem('holdem-action');}
  }
  async function restoreRoom() {
    if(!client||!restoreRoomId||busy)return;
    const id=restoreRoomId;busy=true;
    try{const next=await client.getRoom(id);accept(next,true);restoreRoomId=null;if(!disposed)stream(id);if(pendingAction)error='Остался неподтверждённый запрос. Повторите ход с тем же идентификатором.';else error='';}
    catch(e){const status=typeof e==='object'&&e!==null&&'status'in e?e.status:null;
      if((status===403||status===404)&&!pendingAction){sessionStorage.removeItem('holdem-room');restoreRoomId=null;error='Предыдущая раздача недоступна. Выберите стол.';}
      else error=pendingAction?'Остался неподтверждённый запрос. Повторите ход с тем же идентификатором.':'Не удалось восстановить раздачу. Повторите синхронизацию.';
    }finally{busy=false;}
  }
  onMount(() => {
    pollTimer=setInterval(() => {void refresh();},2000);
    clockTimer=setInterval(() => {seconds=(tableView??view)?.deadline ? Math.max(0,Math.ceil((Date.parse((tableView??view)!.deadline!)-Date.now())/1000)) : 0;},250);
    if (live && client) {
      try {const pending=JSON.parse(sessionStorage.getItem('holdem-create') ?? 'null');if(pending && ['bot','pvp'].includes(pending.mode) && [100,500,1000].includes(pending.buyIn) && typeof pending.id === 'string') {pendingCreate=pending;void start();return;}} catch {sessionStorage.removeItem('holdem-create');}
      restoreAction();
      try {const stored=JSON.parse(sessionStorage.getItem('holdem-room')??'null');if(stored?.id&&['bot','pvp'].includes(stored.mode)){mode=stored.mode;restoreRoomId=stored.id;}else if(pendingAction)restoreRoomId=pendingAction.roomId;}catch{if(pendingAction)restoreRoomId=pendingAction.roomId;else sessionStorage.removeItem('holdem-room');}
      if(pendingAction?.payload.action==='cancel'){error='Остался неподтверждённый запрос. Повторите ход с тем же идентификатором.';return;}
      if(restoreRoomId)void restoreRoom();
    }
  });
  onDestroy(() => {disposed=true;cancelIntroVoice?.();sound.stopEffects();clearAvatar();clearTableAvatars();stopStream?.();clearInterval(pollTimer);clearInterval(clockTimer);});
</script>
<svelte:head><link rel="stylesheet" href={`${base}/holdem/font.css`} /></svelte:head>
<div class="poker-room" aria-busy={busy}>
  <header><h2 class="neon">Kamurocho <span class="kanji">神室町</span></h2><p>{live ? 'С ботом или за общим столом до шести игроков. Итог с сервера.' : 'DEMO · записанная демонстрационная раздача. Баланс не меняется.'}</p></header>
  {#if error}<div class="error" role="alert">{error} {#if pendingCreate}<button on:click={start} disabled={busy}>Повторить</button>{/if}{#if pendingAction}<button on:click={() => action('retry')} disabled={busy}>Повторить ход</button>{/if}{#if restoreRoomId&&!pendingAction}<button on:click={restoreRoom} disabled={busy}>Восстановить раздачу</button>{:else if snapshot}<button on:click={refresh} disabled={busy}>Синхронизировать</button>{/if}</div>{/if}
  {#if tableView}
    {#if tableView.phase==='waiting'}<section class="search" role="status"><h3>Собираем общий стол</h3><p>{tableView.players.length} / 6 игроков · {seconds} с</p><p>При шести игроках начнём сразу. По окончании поиска достаточно двоих. Вход списывается только на старте.</p><button data-testid="holdem-cancel" on:click={()=>action('cancel')} disabled={busy||!!pendingAction}>Отменить поиск</button></section>
    {:else if tableView.phase==='cancelled'}<p role="status">Поиск завершён. Вход не списан.</p><button on:click={lobby}>Выбрать стол</button>
    {:else}<MultiplayerTable view={tableView} busy={busy||!!pendingAction} {seconds} {reducedMotion} avatars={tableAvatars} onAction={action} />{#if tableView.phase==='settled'}<button on:click={lobby}>Выбрать стол</button>{/if}{/if}
  {:else if !view}
    <section class="lobby" aria-label="Лобби Hold’em">
      <fieldset disabled={busy || !!pendingCreate || !!pendingAction || !!restoreRoomId}><legend>Соперник</legend><label><input type="radio" bind:group={mode} value="bot" /> Против бота</label><label><input type="radio" bind:group={mode} value="pvp" disabled={!live} /> Живой игрок · до 6</label></fieldset>
      <fieldset disabled={busy || !!pendingCreate || !!pendingAction || !!restoreRoomId}><legend>Вход в раздачу</legend>{#each [100,500,1000] as table}<label><input type="radio" bind:group={buyIn} value={table} /> <b>{table.toLocaleString('ru')} <em>JG</em></b> <small>Блайнды {table/20}/{table/10}</small></label>{/each}</fieldset>
      <button class="primary" data-testid="holdem-start" on:click={() => { sound.cue('confirm'); void start(); }} disabled={busy || !!pendingAction || !!restoreRoomId}>{busy ? 'Подключаемся…' : mode === 'pvp' ? 'Найти общий стол' : 'Начать раздачу'}</button>
    </section>
  {:else if view.phase === 'waiting'}
    <section class="search" role="status"><h3>Поиск соперника</h3><p>Стол {view.buyIn} JG · {seconds} с</p><p>Вход списывается при начале раздачи.</p><button data-testid="holdem-cancel" on:click={() => action('cancel')} disabled={busy}>Отменить поиск</button></section>
  {:else if view.phase === 'cancelled'}
    <p role="status">Поиск завершён. Вход не списан.</p><button on:click={lobby}>Выбрать стол</button>
  {:else}
    <div inert={showIntro}><HandTable {view} roomId={snapshot?.roomId ?? ''} {hero} {avatarUrl} busy={busy || !!pendingAction} {seconds} {live} onAction={action} /></div>
    {#if view.phase === 'settled'}<button on:click={lobby}>Выбрать стол</button>{/if}
    {#if showIntro && hero}<section class="intro" data-testid="holdem-intro" aria-label="Ваш соперник"><img src={`${base}/holdem/${hero.intro}`} alt="" /><div><h3>{hero.name}</h3><p>{hero.title}</p><button use:focusIntro on:click={() => showIntro=false}>К столу</button></div></section>{/if}
  {/if}
  <details class="sources"><summary>Источники изображений</summary><p>© SEGA / Ryu Ga Gotoku Studio. Некоммерческий фанатский интерфейс по решению владельца. Общая лицензия на изображения не заявляется.</p><a href={`${base}/holdem/sources.json`} target="_blank" rel="noreferrer">Источники персонажей и сцены</a><p>Шрифт Permanent Marker — Google Fonts.</p></details>
</div>
<style>
  .poker-room{position:relative;display:grid;gap:16px;background:#171313;color:#f3ede2;padding:16px;border:1px solid #c9a24a55;padding-bottom:max(16px,env(safe-area-inset-bottom))}h2{font:32px Georgia,serif;margin:8px 0}p{font-size:12px;line-height:1.5;margin:4px 0;color:inherit}.lobby{display:grid;gap:16px}fieldset{display:grid;gap:8px;border:1px solid #c9a24a55;padding:12px}legend{color:#e9cd84;font-size:12px}label{padding:8px;font-size:14px}label small{display:block;margin:4px 0 0 22px;color:#ccc3b4;font-size:11px}input{accent-color:#b8141f}button{min-height:44px;border:1px solid #c9a24a;background:#321014;color:#f3ede2;padding:8px 16px;font:inherit;cursor:pointer}button:disabled{opacity:.5;cursor:default}button:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #fff1b8;outline-offset:3px}.primary{background:#7a0b13}.error{padding:12px;border:1px solid #ea8e8e;font-size:13px}.error button{margin-top:8px}.search{text-align:center;padding:24px 8px}.sources{font-size:11px;color:#d4cbbd}.sources summary{min-height:44px;display:flex;align-items:center;cursor:pointer}.sources a{color:#e9cd84}.intro{position:absolute;z-index:4;inset:0;display:grid;align-content:center;background:#0c0a0af5;overflow:hidden;padding:16px}.intro>img{width:100%;aspect-ratio:4/5;object-fit:cover;filter:grayscale(1);mask-image:linear-gradient(transparent,#000 15%,#000 80%,transparent)}.intro>div{margin-top:-80px;z-index:1;text-align:center}.intro h3,.intro p{font-family:Permanent Marker,cursive;color:#b8141f;-webkit-text-stroke:1px #fff;paint-order:stroke fill;text-shadow:2px 2px #000}.intro h3{font-size:clamp(24px,7vw,42px);margin:8px 0}.intro p{font-size:16px;margin:8px 0}.intro button{margin-top:16px}@media(min-width:768px){.lobby fieldset:last-of-type{grid-template-columns:repeat(3,1fr)}.intro>img{max-height:520px;object-fit:contain}.poker-room{max-width:720px;margin:auto;width:100%;box-sizing:border-box}}@media(prefers-reduced-motion:reduce){.intro{display:none}}

  /* Kamurocho в стиле хаба: стекло над воротами, неоновая вывеска, карточки-таблички вместо переключателей. */
  .poker-room{background:rgb(23 19 19 / 86%);border-radius:18px;border-color:rgb(201 162 74 / 45%);box-shadow:0 18px 50px rgb(0 0 0 / 55%),0 0 40px rgb(255 46 96 / 8%)}
  .neon{color:#ffe9ee;text-shadow:0 0 6px #ff2e60,0 0 18px #ff2e6099,0 0 34px #ff2e6055;animation:sign 7s linear infinite}
  .lobby fieldset{border:0;padding:0;margin:0;grid-template-columns:repeat(auto-fit,minmax(0,1fr));gap:8px}
  .lobby legend{margin-bottom:8px;padding:0;letter-spacing:.14em;text-transform:uppercase;font-size:10px}
  .lobby label{position:relative;display:grid;align-content:center;justify-items:center;gap:4px;min-height:64px;padding:10px 6px;border:1px solid rgb(201 162 74 / 35%);border-radius:14px;background:rgb(12 9 9 / 62%);text-align:center;cursor:pointer;transition:transform .18s ease,opacity .18s ease}
  .lobby label:hover{transform:translateY(-2px);border-color:rgb(233 205 132 / 70%)}
  .lobby label:has(input:checked){border-color:#e9cd84;background:linear-gradient(180deg,rgb(122 11 19 / 55%),rgb(12 9 9 / 70%));box-shadow:0 0 22px rgb(255 46 96 / 28%),inset 0 0 0 1px rgb(233 205 132 / 40%)}
  .lobby label:has(input:disabled){opacity:.45;cursor:not-allowed}
  .lobby label:has(input:focus-visible){outline:2px solid #fff1b8;outline-offset:3px}
  .lobby input[type=radio]{position:absolute;inset:0;opacity:0;margin:0;cursor:inherit}
  .lobby label b{font:600 20px/1 Georgia,serif;color:#fff1ca}
  .lobby label b em{font-style:normal;font-size:11px;color:#e9cd84}
  .lobby label small{color:#cdbfa8}
  .primary{min-height:56px;border:1px solid #ff8aa5;border-radius:14px;background:linear-gradient(180deg,#a3121f,#6b0911);box-shadow:0 0 26px rgb(255 46 96 / 35%);transition:transform .18s ease,opacity .18s ease}
  .primary:hover:not(:disabled){transform:translateY(-2px);box-shadow:0 0 36px rgb(255 46 96 / 55%)}
  .primary:active:not(:disabled){transform:translateY(1px) scale(.98)}
  .neon .kanji{font-size:.62em;letter-spacing:.08em;vertical-align:.18em}
  @keyframes sign{0%,100%{opacity:1}61%{opacity:1}62%{opacity:.55}63%{opacity:1}66%{opacity:.7}67%{opacity:1}}
  @media(prefers-reduced-motion:reduce){.neon{animation:none}.lobby label,.primary{transition:none}}

  .poker-room button { border-radius: 14px; min-height: 48px; border-color: #e9cd8499; background: linear-gradient(180deg,#63151e,#260c12); box-shadow: inset 0 1px #ffb7c02b,0 0 16px #ff2e601c; transition: transform .18s ease, opacity .18s ease; }
  .poker-room button:active:not(:disabled) { transform: scale(.97); }
  .poker-room { gap: 10px; }

</style>
