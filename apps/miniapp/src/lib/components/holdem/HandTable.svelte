<script lang="ts">
  import { base } from '$app/paths';
  import PlayingCard from './PlayingCard.svelte';
  import BetPicker from '$lib/components/BetPicker.svelte';
  import type { HoldemView } from '$lib/api/holdem';
  export let view: HoldemView;
  export let hero: {name:string;avatar:string;intro:string;title:string} | null = null;
  export let busy = false;
  export let seconds = 0;
  export let live = false;
  export let avatarUrl = '';
  export let onAction: (action:string, fields?:Record<string,unknown>) => void;
  let raise = 0;
  let previousBounds = '';
  function updateBounds(minimum:number, maximum:number) {
    const bounds=`${minimum}:${maximum}`;
    if(bounds !== previousBounds) {raise=minimum;previousBounds=bounds;}
  }
  $: updateBounds(view.minimumRaise,view.maximumRaise);
  // Рейз «до» суммы: текущая ставка + доля банка после колла; BetPicker отбросит выходящие за границы.
  function raiseTo(share:number) {const current=view.call+view.contributions[view.seat];return current+Math.round(share*(view.pot+view.call));}
  $: raisePresets = [{label:'Мин',value:view.minimumRaise},{label:'½ банка',value:raiseTo(0.5)},{label:'¾ банка',value:raiseTo(0.75)},{label:'Банк',value:raiseTo(1)},{label:'Ва-банк',value:view.maximumRaise}];
  $: stamp = !view.result ? '' : view.result.winners.length === 2 ? '分' : view.result.winners.includes(view.seat) ? '勝' : '負';
  $: verdict = !view.result ? '' : view.result.winners.length === 2 ? 'Ничья' : view.result.winners.includes(view.seat) ? 'Победа' : 'Поражение';
  const names: Record<string,string> = {fold:'Пас',check:'Чек',call:'Колл',raise:'Рейз'};
  const streets: Record<string,string> = {pre_flop:'Префлоп',flop:'Флоп',turn:'Тёрн',river:'Ривер',showdown:'Шоудаун',settled:'Завершено'};
</script>
<section class="table" aria-label="Стол Hold’em" data-testid="holdem-table">
  <img class="scene" src={`${base}/holdem/scene/room.webp`} alt="" />
  <div class="seat opponent">
    <div class="avatar-ring" class:active={!!view.deadline && view.phase === 'active' && view.currentSeat !== view.seat} style={`--remaining:${Math.min(1,seconds/20)}`}>
    {#if hero}<img class="avatar" src={`${base}/holdem/${hero.avatar}`} alt="" />{:else if avatarUrl}<img class="avatar" src={avatarUrl} alt="Аватар соперника" on:error={() => avatarUrl=''} />{:else}<span class="avatar placeholder" data-testid="holdem-avatar-placeholder" aria-hidden="true">♟</span>{/if}
    </div>
    <div><b data-testid="holdem-opponent-nickname">{hero?.name ?? view.opponentProfile?.nickname ?? 'Живой игрок'}</b><small>Стек {view.stacks[1-view.seat]} JG</small></div>
    <div class="hand" data-testid="holdem-opponent">{#each view.opponent as card, i}<PlayingCard {card} delay={i*90} />{/each}</div>
  </div>
  <div class="pot">{#key view.pot}<div class="pot-chips" aria-hidden="true"><i></i><i></i><i></i></div>{/key}<small>{streets[view.street] ?? view.street}</small><span>БАНК</span><strong>{view.pot} <small>JG</small></strong></div>
  <div class="board" data-testid="holdem-board">{#each Array(5) as _, i}{#if view.board[i]}<PlayingCard card={view.board[i]} delay={i < 3 ? i*150 : 0} />{:else}<span class="empty" aria-label="Карта борда ещё не открыта"></span>{/if}{/each}</div>
  <div class="seat own"><div class="avatar-ring" class:active={!!view.deadline && view.phase === 'active' && view.currentSeat === view.seat} style={`--remaining:${Math.min(1,seconds/20)}`}><span class="avatar own-avatar" aria-hidden="true">♠</span></div><div><b>Ваше место</b><small>Стек {view.stacks[view.seat]} JG</small></div><div class="hand" data-testid="holdem-own">{#each view.own as card, i}<PlayingCard {card} delay={i*90} />{/each}</div></div>
  {#if view.deadline && view.phase === 'active'}<div class="turn" style={`--remaining:${Math.min(1,seconds/20)}`} data-testid="holdem-timer"><b>{seconds}</b><span>{view.currentSeat === view.seat ? 'Ваш ход' : 'Ход соперника'}</span></div>{/if}
</section>
{#if view.phase === 'active'}
  <div class="actions" aria-label="Действия Hold’em">
    {#each view.legal as action}<button data-testid={`holdem-${action}`} disabled={busy || (action === 'raise' && (!Number.isInteger(raise) || raise < view.minimumRaise || raise > view.maximumRaise))} on:click={() => onAction(action, action === 'raise' ? {amount:raise} : {})}>{names[action]}{#if action === 'call'} <small>{view.call} JG</small>{/if}</button>{/each}
  </div>
  {#if view.legal.includes('raise')}<div class="raise"><BetPicker bind:value={raise} min={view.minimumRaise} max={view.maximumRaise} presets={raisePresets} disabled={busy} label="Рейз до" inputId="holdem-raise-amount" inputLabel="Сумма рейза" /></div>{/if}
  {#if !view.legal.length}<p role="status">Ожидаем ход соперника.</p>{/if}
{/if}
{#if view.result}<div class="result" role="status" data-testid="holdem-result"><span class="stamp" aria-hidden="true">{stamp}</span><div><h3>{verdict}</h3><p>{view.result.outcome === 'fold' ? 'Раздача завершена пасом.' : 'Карты открыты на шоудауне.'}</p><p>Возвращено {view.result.payout} JG · результат {view.result.net > 0 ? '+' : ''}{view.result.net} JG</p><small>{live ? 'Итог подтверждён сервером' : 'Демонстрационная раздача'}</small></div></div>{/if}
<style>
  .table{position:relative;isolation:isolate;display:grid;gap:18px;padding:24px 16px;overflow:hidden;border:1px solid #c9a24a;border-radius:40% / 12%;background:#100c0d;min-height:370px;box-shadow:inset 0 0 40px #000}.scene{position:absolute;z-index:-1;inset:0;width:100%;height:100%;object-fit:cover;opacity:.24;filter:grayscale(.4)}.table:before{content:'';position:absolute;inset:12px;border:1px solid #c9a24a55;border-radius:inherit;pointer-events:none}.seat{display:flex;gap:8px;align-items:center;z-index:1;min-width:0}.seat div:not(.hand){display:grid;gap:4px;min-width:0}.seat b{font-size:12px;overflow-wrap:anywhere}.seat small,.pot>small{color:#ccc3b4;font-size:11px}.avatar{width:40px;height:48px;object-fit:cover;border:1px solid #c9a24a;flex-shrink:0}.placeholder{display:grid;place-items:center;font-size:24px}.hand{display:flex;gap:4px;margin-left:auto}.pot{text-align:center;display:grid;gap:4px}.pot>span{letter-spacing:.2em;font-size:10px}.pot strong{font-size:28px;color:#e9cd84}.pot strong small{font-size:11px}.board{display:flex;justify-content:center;gap:6px}.empty{width:clamp(34px,9vw,56px);aspect-ratio:5/7;border:1px dashed #ece3cf55;border-radius:4px}.turn{display:flex;align-items:center;justify-content:center;gap:8px;font-size:12px}.turn b{display:grid;place-items:center;width:40px;height:40px;border-radius:50%;background:radial-gradient(circle,#181212 62%,transparent 65%),conic-gradient(#c9a24a calc(var(--remaining)*360deg),#555 0)}.actions{display:flex;flex-wrap:wrap;gap:8px}.actions button{flex:1;min-height:48px;padding:8px 12px;border:1px solid #c9a24a66;background:#48141a;color:#f3ede2;font:inherit;cursor:pointer;transform:skew(-5deg)}.actions button small{display:block;font-size:10px}.actions button:disabled{opacity:.4;cursor:default}.raise{--bet-accent:#e2c06b;--bet-line:#c9a24a88;--bet-ink:#f3ede2}.result{display:flex;align-items:center;gap:16px;padding:16px;background:#ece3cf;color:#1c1716}.result h3,.result p{margin:4px 0}.result p,.result small{font-size:12px}.stamp{font:64px Georgia,serif;color:#a0111d;border:3px solid #a0111d;padding:4px;animation:stamp .3s ease-out;transform:rotate(-9deg)}button:focus-visible{outline:3px solid #fff1b8;outline-offset:3px}@keyframes stamp{from{opacity:0;transform:scale(1.8) rotate(-9deg)}to{opacity:1;transform:scale(1) rotate(-9deg)}}@media(prefers-reduced-motion:reduce){.stamp{animation:none}}

  .avatar-ring { position: relative; flex-shrink: 0; width: 48px; height: 48px; display: grid !important; place-items: center; border-radius: 50%; padding: 3px; }
  .avatar-ring.active { background: conic-gradient(#f4cd80 calc(var(--remaining)*360deg),#491a21 0); }
  .avatar-ring .avatar { width: 40px; height: 40px; border-radius: 50%; object-position: 50% 20%; }
  .own-avatar { display: grid; place-items: center; font-size: 24px; color: #edcf87; background: #1b0e13; }
  .pot { position: relative; }
  .pot-chips { position: absolute; left: 50%; top: 50%; display: flex; gap: 4px; pointer-events: none; }
  .pot-chips i { width: 15px; height: 8px; border: 2px dashed #edd59f; border-radius: 50%; background: #ac343e; box-shadow: 0 2px #53171c; animation: intoPot 460ms ease-out both; }
  .pot-chips i:nth-child(2) { animation-delay: 60ms; }
  .pot-chips i:nth-child(3) { animation-delay: 120ms; }
  .table { gap: 12px; min-height: 310px; padding: 18px 12px; background: radial-gradient(ellipse at center,#45232de6,#120b11 85%); }
  .hand, .board { perspective: 850px; }
  .actions { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); }
  .actions button { min-height: 48px; padding: 6px 3px; border: 1px solid #f0aaad88; border-radius: 12px; transform: none; background: linear-gradient(#7a1525,#340d16); box-shadow: inset 0 1px #ffd4d52e,0 0 18px #ff2e6020; font-size: 13px; font-weight: 750; transition: transform .18s ease,opacity .18s ease; }
  .actions button:hover:not(:disabled) { transform: translateY(-2px); }
  .actions button:active:not(:disabled) { transform: scale(.96); }
  .raise { padding: 10px; border: 1px solid #c9a24a66; border-radius: 14px; background: #180d15e8; }
  .result { border-radius: 16px; border: 1px solid #e8c682aa; background: linear-gradient(120deg,#fae9bf,#d8c49b); }
  .turn b { background: none; width: auto; height: auto; }
  @keyframes intoPot { from { opacity: 0; transform: translate(-20px,80px) scale(.7); } 25% { opacity: 1; } to { opacity: 0; transform: translate(-20px,0) scale(1); } }
  @media(prefers-reduced-motion:reduce) { .pot-chips { display: none; } .actions button { transition: none; } }


</style>
